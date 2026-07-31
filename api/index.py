import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app) # ከሁሉም ገጽ የሚመጡ ጥያቄዎችን እንዲቀበል ይፈቅዳል

# Vercel POSTGRES_URL ወይም DATABASE_URL ን ይጠቀማል
DB_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DB_URL)
    return conn

# 1. አዲስ ሰራተኛ መመዝገቢያ (Register Employee)
@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json or {}
    full_name = data.get('full_name')
    department = data.get('department')
    phone = data.get('phone')

    if not full_name:
        return jsonify({"error": "Full name is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employees (full_name, department, phone) 
            VALUES (%s, %s, %s) RETURNING id;
        """, (full_name, department, phone))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Successfully registered!", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. የዕለት መግቢያ (Check-in)
@app.route('/api/checkin', methods=['POST'])
def check_in():
    data = request.json or {}
    employee_id = data.get('employee_id')
    
    if not employee_id:
        return jsonify({"error": "Employee ID is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO attendance (employee_id, att_date, check_in, status)
            VALUES (%s, CURRENT_DATE, CURRENT_TIME, 'Present')
            ON CONFLICT (employee_id, att_date) 
            DO UPDATE SET check_in = CURRENT_TIME;
        """, (employee_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Check-in successfully recorded!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. የዕለት መውጫ (Check-out)
@app.route('/api/checkout', methods=['POST'])
def check_out():
    data = request.json or {}
    employee_id = data.get('employee_id')
    
    if not employee_id:
        return jsonify({"error": "Employee ID is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE attendance 
            SET check_out = CURRENT_TIME 
            WHERE employee_id = %s AND att_date = CURRENT_DATE;
        """, (employee_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Check-out successfully recorded!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. የዛሬ ሪፖርት ማውጫ (Daily Report)
@app.route('/api/report', methods=['GET'])
def get_report():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.full_name, e.department, a.check_in, a.check_out, a.status 
            FROM attendance a 
            JOIN employees e ON a.employee_id = e.id 
            WHERE a.att_date = CURRENT_DATE;
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
                "status": row[5]
            })
        cur.close()
        conn.close()
        return jsonify(report_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ለ Vercel Serverless Function አስፈላጊ ነው
app = app

if __name__ == '__main__':
    app.run(debug=True)
