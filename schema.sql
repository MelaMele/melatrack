-- 1. የሰራተኞች መረጃ ቴብል (Employees Table)
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    phone VARCHAR(20),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Africa/Addis_Ababa')
);

-- 2. የዕለት መግቢያ እና መውጫ መቆጣጠሪያ ቴብል (Attendance Table)
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    att_date DATE NOT NULL DEFAULT (CURRENT_DATE AT TIME ZONE 'Africa/Addis_Ababa')::DATE,
    check_in TIME WITHOUT TIME ZONE,
    check_out TIME WITHOUT TIME ZONE,
    status VARCHAR(20) DEFAULT 'Present',
    CONSTRAINT unique_emp_daily_att UNIQUE (employee_id, att_date)
);

-- 3. ፈጣን ፍለጋ ለማድረግ የሚረዱ የፍለጋ መላክያዎች (Indexes)
-- ማሳሰቢያ፡ (employee_id, att_date) በ UNIQUE constraint ስለተሸፈነ እዚህ ጋር ሁለተኛ index አያስፈልግም።
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(att_date);
CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department); -- በየዲፓርትመንቱ ለመለየት ይረዳል
