import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

DB_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEB_APP_URL = "https://melatrack-tan.vercel.app"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

def get_db_connection():
    if not DB_URL:
        return None
    try:
        return psycopg2.connect(DB_URL)
    except Exception as e:
        print("DB Connection Error:", e)
        return None

def send_telegram_message(chat_id, text, reply_markup=None):
    if not TELEGRAM_API:
        return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=5)
    except Exception as e:
        print("Telegram Send Error:", e)

@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}
        
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")

            if text == "/start":
                welcome_text = (
                    "👋 <b>እንኳን ወደ MelaTrack Attendance Bot በደህና መጡ!</b>\n\n"
                    "ከታች ያለውን Button በመጫን Admin Dashboard መክፈት ይችላሉ።"
                )
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "📊 Admin Dashboard (Web App)", "web_app": {"url": f"{WEB_APP_URL}/admin"}}
                        ]
                    ]
                }
                send_telegram_message(chat_id, welcome_text, reply_markup=keyboard)
    except Exception as e:
        print("Webhook Processing Error:", e)
        
    return jsonify({"status": "ok"}), 200

@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json or {}
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employees (full_name, department, phone) 
            VALUES (%s, %s, %s) RETURNING id;
        """, (data.get('full_name'), data.get('department'), data.get('phone')))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Successfully registered!", "id": new_id}), 201
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/report', methods=['GET'])
def get_report():
    conn = get_db_connection()
    if not conn:
        return jsonify([]), 200
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.full_name, e.department, a.check_in, a.check_out, a.status 
            FROM employees e
            LEFT JOIN attendance a ON e.id = a.employee_id AND a.att_date = CURRENT_DATE;
        """)
        rows = cur.fetchall()
        report_data = []
        for row in rows:
            report_data.append({
                "id": row[0],
                "full_name": row[1],
                "department": row[2],
                "check_in": str(row[3]) if row[3] else "-",
                "check_out": str(row[4]) if row[4] else "-",
                "status": row[5] if row[5] else "Absent"
            })
        cur.close()
        conn.close()
        return jsonify(report_data), 200
    except Exception as e:
        if conn: conn.close()
        return jsonify([]), 200

if __name__ == '__main__':
    app.run(debug=True)
