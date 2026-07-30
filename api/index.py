import os
from flask import Flask, request, jsonify
import psycopg2

app = Flask(__name__)

# ከ Vercel Environment Variable የሚወሰድ የዳታቤዝ ግንኙነት
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

@app.route('/api/checkin', methods=['POST'])
def check_in():
    data = request.json
    employee_id = data.get('employee_id')
    
    if not employee_id:
        return jsonify({"error": "Employee ID is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # የዛሬውን ቀን check-in መመዝገብ
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

if __name__ == '__main__':
    app.run(debug=True)
