from flask import Flask, render_template, url_for, request, flash, redirect
from flask_frozen import Freezer
from flask_flatpages import FlatPages
import requests
import pandas as pd
import os

app = Flask(__name__)
app.config.from_object(__name__)
app.config['FLATPAGES_EXTENSION'] = '.md'
app.secret_key = 'super_secret_key_lea_web' # Cần thiết cho flash messages

# Đường dẫn lưu file tạm
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

pages = FlatPages(app)
freezer = Freezer(app)

# CẤU HÌNH TELEGRAM (BẠN HÃY THAY ĐỔI THÔNG TIN Ở ĐÂY)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # Lấy từ biến môi trường
TELEGRAM_CHAT_ID =  os.getenv('TELEGRAM_CHAT_ID')      # Lấy từ biến môi trường

def send_message_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Lỗi gửi tin nhắn Telegram: {e}")

def send_document_telegram(file_path):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        data = {'chat_id': TELEGRAM_CHAT_ID}
        with open(file_path, 'rb') as f:
            files = {'document': f}
            response = requests.post(url, data=data, files=files)
            print(f"Gửi file status: {response.status_code}")
    except Exception as e:
        print(f"Lỗi gửi file Telegram: {e}")

import json # Import thêm JSON

# CẤU HÌNH GEMINI (THAY KEY CỦA BẠN)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Lấy từ biến môi trường

def call_gemini_suggest(description):
    try:
        if not description: return None
        
        # Danh sách chart type có sẵn trong hệ thống của bạn
        available_charts = [
            "Area Chart", "Bar Chart", "Box Plot", "Bubble Chart", "Candle Stick",
            "Density Plot", "Heatmap", "Histogram", "Line Chart", "Lollipop Chart",
            "Parallel Coordinates", "Pie Chart", "Radar Chart", "Scatter Plot",
            "Sunburst Chart", "Tree Map", "Waterfall Chart"
        ]
        
        prompt = f"""
        You are a Data Analyst Expert. Based on this project description: "{description}", 
        please suggest 3 important KPIs and 3 relevant Charts used in Data Analysis.
        
        Strictly follow this JSON format (no markdown code blocks, just raw JSON):
        {{
            "kpis": ["KPI 1 Name", "KPI 2 Name", "KPI 3 Name"],
            "charts": [
                {{"desc": "Description of chart 1", "type": "Exact Chart Type from list"}},
                {{"desc": "Description of chart 2", "type": "Exact Chart Type from list"}},
                {{"desc": "Description of chart 3", "type": "Exact Chart Type from list"}}
            ]
        }}
        
        You must ONLY choose "type" from this list: {', '.join(available_charts)}.
        """
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": {"parts": [{"text": prompt}]}}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            try:
                ai_text = result['candidates'][0]['content']['parts'][0]['text']
                # Clean markdown if any
                if "```json" in ai_text: 
                    ai_text = ai_text.split("```json")[1].split("```")[0]
                elif "```" in ai_text: 
                    ai_text = ai_text.split("```")[1].split("```")[0]
                
                return json.loads(ai_text)
            except Exception as e:
                print(f"Lỗi Parse JSON từ AI: {e}")
                print(f"Raw AI Text: {ai_text}") # In ra để debug xem AI trả về cái gì
        else:
            print(f"Lỗi API Gemini: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Lỗi kết nối AI: {e}")
    return None

@app.route('/')
def home():
    return render_template('./pages/home.html')

@app.route('/portfolio/')
def portfolio():
    return render_template('pages/portfolio.html')

@app.route('/contact/', methods=['GET', 'POST'])
def contact():
    # Khởi tạo giá trị mặc định
    form_data = {}
    show_preview = False
    charts_top = []
    charts_bottom = []

    if request.method == 'POST':
        try:
            # Lấy dữ liệu cơ bản
            fullname = request.form.get('fullname')
            email = request.form.get('email')
            dashboard_name = request.form.get('dashboard_name')
            description = request.form.get('description')
            action = request.form.get('action')

            # Lấy list dynamic hiện tại
            kpi_list = request.form.getlist('kpis[]')
            graph_descs = request.form.getlist('graph_desc[]')
            graph_types = request.form.getlist('graph_type[]')

            # XỬ LÝ NÚT AI SUGGEST
            if action == 'suggest_ai':
                suggestion = call_gemini_suggest(description)
                if suggestion:
                    # Ghi đè hoặc thêm vào list hiện tại
                    kpi_list = suggestion.get('kpis', [])
                    graph_descs = [c['desc'] for c in suggestion.get('charts', [])]
                    graph_types = [c['type'] for c in suggestion.get('charts', [])]
                    flash("✨ AI đã điền gợi ý cho bạn!", "info")
                else:
                    flash("⚠️ Không thể lấy gợi ý AI (Kiểm tra API Key hoặc Description)", "error")

            # Lưu data để điền lại vào form
            form_data = {
                'fullname': fullname,
                'email': email,
                'dashboard_name': dashboard_name,
                'description': description,
                'kpis': kpi_list,
                'graph_descs': graph_descs,
                'graph_types': graph_types
            }

            # XỬ LÝ PREVIEW
            if action == 'preview':
                show_preview = True
                charts_data = []
                if graph_descs and graph_types:
                    for desc, gtype in zip(graph_descs, graph_types):
                        if desc.strip(): 
                            charts_data.append({'desc': desc, 'type': gtype})
                
                # Logic chia Layout (2n+1 -> Top: n, Bottom: n+1)
                total_charts = len(charts_data)
                if total_charts > 0:
                    if total_charts % 2 == 0: mid = total_charts // 2
                    else: mid = (total_charts - 1) // 2
                    charts_top = charts_data[:mid]
                    charts_bottom = charts_data[mid:]

                flash("Đã tạo bản xem trước Dashboard bên dưới 👇", "info")
                return render_template('pages/contact.html', 
                                     form_data=form_data, 
                                     show_preview=show_preview, 
                                     charts_top=charts_top,
                                     charts_bottom=charts_bottom)

            elif action == 'send':
                # ... (Giữ nguyên logic gửi Telegram) ...
                kpis_str = ""
                if kpi_list:
                    for i, kpi in enumerate(kpi_list, 1):
                        kpis_str += f"{i}. {kpi}\n"
                
                graphs_str = ""
                if graph_descs and graph_types:
                    for i, (desc, gtype) in enumerate(zip(graph_descs, graph_types), 1):
                        graphs_str += f"{i}. [{gtype}] {desc}\n"

                msg_content = (
                    f"<b>📩 New Project Inquiry from LeaWeb</b>\n\n"
                    f"👤 <b>Name:</b> {fullname}\n"
                    f"📧 <b>Email:</b> {email}\n\n"
                    f"🖥 <b>Dashboard Name:</b> {dashboard_name}\n\n"
                    f"📝 <b>Description:</b>\n{description}\n\n"
                    f"🎯 <b>Required KPIs:</b>\n{kpis_str}\n\n"
                    f"📊 <b>Required Graphs:</b>\n{graphs_str}"
                )
                send_message_telegram(msg_content)

                # Xử lý file (Giữ nguyên)
                file = request.files.get('sample_data')
                if file and file.filename != '':
                    filename = file.filename
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    try:
                        if filename.endswith('.csv'): df = pd.read_csv(filepath)
                        elif filename.endswith(('.xls', '.xlsx')): df = pd.read_excel(filepath)
                        else: df = None
                        
                        if df is not None:
                            df_head = df.head(10)
                            preview_filename = f"PREVIEW_10_ROWS_{filename}.csv"
                            preview_path = os.path.join(app.config['UPLOAD_FOLDER'], preview_filename)
                            df_head.to_csv(preview_path, index=False)
                            send_document_telegram(preview_path)
                            os.remove(preview_path)
                    except Exception as e:
                        print(f"Lỗi đọc file: {e}")
                        send_message_telegram(f"⚠️ Lỗi file: {str(e)}")
                    os.remove(filepath)

                flash("Cảm ơn! Thông tin của bạn đã được gửi thành công.")
                return redirect(url_for('contact'))
            
            # Nếu chỉ là suggest_ai thì render lại form với dữ liệu mới
            return render_template('pages/contact.html', form_data=form_data)

        except Exception as e:
            print(f"Lỗi chung: {e}")
            flash("Có lỗi xảy ra. Vui lòng thử lại.")

    return render_template('pages/contact.html', form_data=form_data)

@app.route('/blog/')
def blog():
    return render_template('pages/blog.html')

if __name__ == '__main__':
    app.run(debug=True, port=8000)
