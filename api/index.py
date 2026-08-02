import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

DB_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEB_APP_URL = os.environ.get('VERCEL_URL', 'https://melatrack-tan.vercel.app')

if WEB_APP_URL and not WEB_APP_URL.startswith('http'):
    WEB_APP_URL = f"https://{WEB_APP_URL}"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

def get_db_connection():
    if not DB_URL:
        raise Exception("Database connection URL is not set in Environment Variables!")
    return psycopg2.connect(DB_URL)

def send_telegram_message(chat_id, text, reply_markup=None):
    if not TELEGRAM_API:
        return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

# --- TELEGRAM WEBHOOK ROUTE ---
@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    data = request.json or {}
    
    # Inline Button Click Handling
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        cb_data = cb["data"]
        
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Search employee by telegram_id or system ID
            if cb_data.startswith("checkin_"):
                emp_id = cb_data.split("_")[1]
                cur.execute("""
                    INSERT INTO attendance (employee_id, att_date, check_in, status)
                    VALUES (%s, CURRENT_DATE, CURRENT_TIME, 'Present')
                    ON CONFLICT (employee_id, att_date) 
                    DO UPDATE SET check_in = CURRENT_TIME;
                """, (emp_id,))
                conn.commit()
                send_telegram_message(chat_id, "✅ <b>Check-in ተመዝግቧል!</b> መልካም የስራ ቀን።")
                
            elif cb_data.startswith("checkout_"):
                emp_id = cb_data.split("_")[1]
                cur.execute("""
                    UPDATE attendance 
                    SET check_out = CURRENT_TIME 
                    WHERE employee_id = %s AND att_date = CURRENT_DATE;
                """, (emp_id,))
                conn.commit()
                send_telegram_message(chat_id, "👋 <b>Check-out ተመዝግቧል!</b> ደህና አምሹ።")
                
            cur.close()
        except Exception as e:
            if conn: conn.rollback()
            send_telegram_message(chat_id, f"⚠️ ስህተት አጋጥሟል፦ {str(e)}")
        finally:
            if conn: conn.close()
            
        return jsonify({"status": "ok"}), 200

    # Message Handling
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text == "/start":
            welcome_text = (
                "👋 <b>እንኳን ወደ MelaTrack Attendance Bot በደህና መጡ!</b>\n\n"
                "ከታች ያሉትን አማራጮች በመጠቀም መግቢያ/መውጫ ያስመዝግቡ ወይም Admin Dashboard ይክፈቱ።"
            )
            
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📊 Admin Dashboard (Web App)", "web_app": {"url": f"{WEB_APP_URL}/admin"}}
                    ]
                ]
            }
            send_telegram_message(chat_id, welcome_text, reply_markup=keyboard)

    return jsonify({"status": "ok"}), 200

# --- REST API FOR ADMIN WEB APP ---
@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json or {}
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employees (full_name, department, phone) 
            VALUES (%s, %s, %s) RETURNING id;
        """, (data.get('full_name'), data.get('department'), data.get('phone')))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return jsonify({"message": "Successfully registered!", "id": new_id}), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/report', methods=['GET'])
def get_report():
    conn = None
    try:
        conn = get_db_connection()
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
        return jsonify(report_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    app.run(debug=True)
