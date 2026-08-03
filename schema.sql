-- 1. የሰራተኞች መረጃ ቴብል (Employees Table)
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Africa/Addis_Ababa')
);

-- 2. የዕለት መግቢያ እና መውጫ መቆጣጠሪያ ቴብል (Attendance Table)
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    att_date DATE NOT NULL DEFAULT (NOW() AT TIME ZONE 'Africa/Addis_Ababa')::DATE,
    check_in TIME,
    check_out TIME,
    status VARCHAR(20) DEFAULT 'Present',
    UNIQUE (employee_id, att_date) -- አንድ ሰራተኛ በቀን ከአንድ ጊዜ በላይ እንዳይመዘገብ ይከላከላል
);

-- 3. ፈጣን ፍለጋ ለማድረግ የሚረዱ የፍለጋ መላክያዎች (Indexes)
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(att_date);
CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance(employee_id, att_date);
