import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

# api/ ፎልደር ውስጥ ስላለ አባሪ ፋይሎችን ለማግኘት ከፍ ብሎ እንዲፈልግ (..) ተደርጓል
app = Flask(__name__, static_folder='../public', template_folder='../public')
CORS(app)

# Database Connection Helper
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable is missing!")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

# ---------------------------------------------------------
# Page Routes (Frontend Rendering)
# ---------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

# 1. Register New Employee
@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.get_json() or {}
    full_name = data.get('full_name')
    department = data.get('department')
    phone = data.get('phone')
    telegram_id = data.get('telegram_id')

    if not full_name or not phone:
        return jsonify({"error": "Full name and phone are required!"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO employees (full_name, department, phone, telegram_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (full_name, department, phone, telegram_id)
        )
        new_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Employee registered successfully", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 2. Employee Check-In
@app.route('/api/checkin', methods=['POST'])
def checkin():
    data = request.get_json() or {}
    emp_id = data.get('employee_id')

    if not emp_id:
        return jsonify({"error": "Employee ID is required!"}), 400

    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now().isoformat()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM employees WHERE id = %s;", (emp_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "የገባው ሰራተኛ ID አልተገኘም!"}), 404

        cur.execute(
            "SELECT id FROM attendance WHERE employee_id = %s AND date = %s;",
            (emp_id, today)
        )
        existing = cur.fetchone()

        if existing:
            cur.close()
            conn.close()
            return jsonify({"error": "ለዛሬ አስቀድመው Check-In አድርገዋል!"}), 400

        cur.execute(
            """
            INSERT INTO attendance (employee_id, date, check_in, status)
            VALUES (%s, %s, %s, 'Present');
            """,
            (emp_id, today, now)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Check-In በተሳካ ሁኔታ ተመዝግቧል!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 3. Employee Check-Out
@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.get_json() or {}
    emp_id = data.get('employee_id')

    if not emp_id:
        return jsonify({"error": "Employee ID is required!"}), 400

    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now().isoformat()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, check_out FROM attendance WHERE employee_id = %s AND date = %s;",
            (emp_id, today)
        )
        record = cur.fetchone()

        if not record:
            cur.close()
            conn.close()
            return jsonify({"error": "ዛሬ ምንም Check-In አልተመዘገበም!"}), 400

        if record['check_out']:
            cur.close()
            conn.close()
            return jsonify({"error": "ለዛሬ አስቀድመው Check-Out አድርገዋል!"}), 400

        cur.execute(
            "UPDATE attendance SET check_out = %s WHERE id = %s;",
            (now, record['id'])
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Check-Out በተሳካ ሁኔታ ተመዝግቧል!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 4. Admin Report
@app.route('/api/report', methods=['GET'])
def get_report():
    today = datetime.now().strftime('%Y-%m-%d')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
            SELECT 
                e.id, 
                e.full_name, 
                e.department, 
                a.check_in, 
                a.check_out, 
                COALESCE(a.status, 'Absent') AS status
            FROM employees e
            LEFT JOIN attendance a ON e.id = a.employee_id AND a.date = %s
            ORDER BY e.id ASC;
        """
        cur.execute(query, (today,))
        report = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(report), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 5. Delete Employee
@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM attendance WHERE employee_id = %s;", (emp_id,))
        cur.execute("DELETE FROM employees WHERE id = %s;", (emp_id,))

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": f"Employee {emp_id} deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ለ Vercel አፕሊኬሽኑን ማቅረቢያ (app.run አያስፈልግም)
