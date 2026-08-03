import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

DB_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DB_URL:
        raise Exception("Database connection URL is not set in Environment Variables!")
    conn = psycopg2.connect(DB_URL)
    return conn

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
        return jsonify({"error": "Employee ID is required"}), 400
        
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
        return jsonify({"error": "Employee ID is required"}), 400

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

# For local development
if __name__ == '__main__':
    app.run(debug=True)
