import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

# Environment Variables
DB_URL = (
    os.environ.get('PRISMA_DATABASE_URL') or 
    os.environ.get('POSTGRES_URL') or 
    os.environ.get('DATABASE_URL')
)
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEB_APP_URL = os.environ.get('WEB_APP_URL', "https://melatrack-tan.vercel.app")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

def get_db_connection():
    if not DB_URL:
        raise Exception("Database Connection URL አልተገኘም! Vercel Environment Variables ላይ PRISMA_DATABASE_URL መኖሩን ያረጋግጡ።")
    return psycopg2.connect(DB_URL)

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

# 1. Database Init (ቴብሎች ከሌሉ በራሱ ይፈጥራል)
def init_db():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                department VARCHAR(50),
                phone VARCHAR(20) UNIQUE,
                telegram_id VARCHAR(50) UNIQUE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
                att_date DATE NOT NULL,
                check_in TIME,
                check_out TIME,
                status VARCHAR(20) DEFAULT 'Present',
                UNIQUE(employee_id, att_date)
            );
        """)
        conn.commit()
        cur.close()
    except Exception as e:
        print("DB Init Error:", e)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

# አፕሊኬሽኑ ሲነሳ ቴብሎቹን ይፈትሻል
init_db()

# 2. Telegram Webhook (ቦቱ ምላሽ እንዲሰጥ)
@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "").strip()

            if text == "/start":
                welcome_text = (
                    "👋 <b>እንኳን ወደ MelaTrack Attendance Bot በደህና መጡ!</b>\n\n"
                    "ከታች ካሉት አማራጮች አንዱን ይምረጡ፡"
                )
                keyboard = {
                    "keyboard": [
                        [{"text": "📥 Check In"}, {"text": "📤 Check Out"}],
                        [{"text": "📊 Admin Dashboard", "web_app": {"url": f"{WEB_APP_URL}/admin"}}]
                    ],
                    "resize_keyboard": True
                }
                send_telegram_message(chat_id, welcome_text, reply_markup=keyboard)

            elif text == "📥 Check In":
                process_tg_attendance(chat_id, action="check_in")

            elif text == "📤 Check Out":
                process_tg_attendance(chat_id, action="check_out")

    except Exception as e:
        print("Webhook Error:", e)
        
    return jsonify({"status": "ok"}), 200

def process_tg_attendance(telegram_id, action):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, full_name FROM employees WHERE telegram_id = %s OR phone = %s;", (str(telegram_id), str(telegram_id)))
        emp = cur.fetchone()

        if not emp:
            send_telegram_message(telegram_id, "⚠️ <b>አልተመዘገቡም!</b>\nእባክዎን መጀመሪያ በአድሚን ገጽ መመዝገብዎን ያረጋግጡ።")
            return

        emp_id, full_name = emp[0], emp[1]

        if action == "check_in":
            cur.execute("""
                INSERT INTO attendance (employee_id, att_date, check_in, status)
                VALUES (%s, (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::DATE, (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::TIME, 'Present')
                ON CONFLICT (employee_id, att_date) 
                DO UPDATE SET check_in = COALESCE(attendance.check_in, EXCLUDED.check_in), status = 'Present';
            """, (emp_id,))
            conn.commit()
            send_telegram_message(telegram_id, f"✅ <b>{full_name}</b>፣ Check-In ተመዝግቧል!")

        elif action == "check_out":
            cur.execute("""
                UPDATE attendance 
                SET check_out = (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::TIME
                WHERE employee_id = %s AND att_date = (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::DATE;
            """, (emp_id,))
            conn.commit()
            send_telegram_message(telegram_id, f"👋 <b>{full_name}</b>፣ Check-Out ተመዝግቧል!")

    except Exception as e:
        print(f"Attendance TG Error ({action}):", e)
        send_telegram_message(telegram_id, "❌ ስህተት አጋጥሟል! እባክዎ ድጋሚ ይሞክሩ።")
    finally:
        if conn: conn.close()

# 3. Web App APIs (ለ Mini App እና Dashboard)
@app.route('/api/employees', methods=['GET', 'POST'])
def manage_employees():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if request.method == 'POST':
            data = request.json or {}
            cur.execute("""
                INSERT INTO employees (full_name, department, phone, telegram_id) 
                VALUES (%s, %s, %s, %s) RETURNING id;
            """, (
                data.get('full_name'), 
                data.get('department'), 
                data.get('phone'), 
                data.get('telegram_id') or data.get('phone')
            ))
            new_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            return jsonify({"message": "Successfully registered!", "id": new_id}), 201

        elif request.method == 'GET':
            cur.execute("SELECT id, full_name, department, phone, telegram_id FROM employees ORDER BY id ASC;")
            rows = cur.fetchall()
            employees = [
                {"id": r[0], "full_name": r[1], "department": r[2], "phone": r[3], "telegram_id": r[4]} 
                for r in rows
            ]
            cur.close()
            return jsonify(employees), 200

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/checkin', methods=['POST'])
def check_in():
    data = request.json or {}
    employee_id = data.get('employee_id')
    if not employee_id:
        return jsonify({"error": "Employee ID ያስፈልጋል!"}), 400
        
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO attendance (employee_id, att_date, check_in, status)
            VALUES (%s, (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::DATE, (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::TIME, 'Present')
            ON CONFLICT (employee_id, att_date) 
            DO UPDATE SET check_in = COALESCE(attendance.check_in, EXCLUDED.check_in), status = 'Present';
        """, (employee_id,))
        conn.commit()
        cur.close()
        return jsonify({"message": f"ID {employee_id}: Check-in ተመዝግቧል!"}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/checkout', methods=['POST'])
def check_out():
    data = request.json or {}
    employee_id = data.get('employee_id')
    if not employee_id:
        return jsonify({"error": "Employee ID ያስፈልጋል!"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE attendance 
            SET check_out = (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::TIME 
            WHERE employee_id = %s AND att_date = (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::DATE;
        """, (employee_id,))
        conn.commit()
        cur.close()
        return jsonify({"message": f"ID {employee_id}: Check-out ተመዝግቧል!"}), 200
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
            LEFT JOIN attendance a 
              ON e.id = a.employee_id 
             AND a.att_date = (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::DATE
            ORDER BY e.id ASC;
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
