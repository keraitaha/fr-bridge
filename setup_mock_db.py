import sqlite3
import random

DB_PATH = "mock.db"

def setup_db():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing tables
    tables = [
        "terminalsa_uat", "student_uat", "new_employee_uat", 
        "student_pic_2002", "new_employee_pic_2004", "faceTemplates"
    ]
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"Cleared {table}.")
        except sqlite3.OperationalError:
            print(f"Table {table} does not exist yet.")

    # Insert mock terminals
    terminals = [
        (1, "Device_001", "TERM001", "192.168.1.100", "80", "1", "admin", "password"),
        (2, "Device_002", "TERM002", "192.168.1.101", "80", "1", "admin", "password")
    ]

    print("Inserting mock terminals...")
    try:
        cursor.executemany('''
            INSERT INTO terminalsa_uat (id, terminalname, terminalid, ip, portno, active, username, password)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', terminals)
        print(f"Inserted {cursor.rowcount} terminals.")
    except sqlite3.OperationalError:
        print("Error inserting terminals. Run bridge.py first to create tables.")

    # Insert Random Students (Year 2002)
    num_students = random.randint(5, 15)
    print(f"Inserting {num_students} random students...")
    student_data = []
    student_pics = []
    for i in range(num_students):
        name = f"Student_{i+1}_{random.randint(1000, 9999)}"
        matrix_no = f"MAT{i+1:03d}"
        reg_date = f"2002-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        student_data.append((name, matrix_no, reg_date))
        student_pics.append((matrix_no, b"fake_photo_blob_student_" + str(i).encode()))

    try:
        cursor.executemany('''
            INSERT INTO student_uat (name, matrix_no, registration_date)
            VALUES (?, ?, ?)
        ''', student_data)
        
        cursor.executemany('''
            INSERT INTO student_pic_2002 (matrix_no, pic_contents)
            VALUES (?, ?)
        ''', student_pics)
        print(f"Inserted {num_students} students and photos.")
    except sqlite3.OperationalError as e:
        print(f"Error inserting student data: {e}")

    # Insert Random Employees (Year 2004)
    num_employees = random.randint(5, 15)
    print(f"Inserting {num_employees} random employees...")
    employee_data = []
    employee_pics = []
    for i in range(num_employees):
        name = f"Employee_{i+1}_{random.randint(1000, 9999)}"
        empid = f"EMP{i+1:03d}"
        join_date = f"2004-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        employee_data.append((name, empid, join_date))
        employee_pics.append((empid, b"fake_photo_blob_employee_" + str(i).encode()))

    try:
        cursor.executemany('''
            INSERT INTO new_employee_uat (name, empid, joining_date)
            VALUES (?, ?, ?)
        ''', employee_data)
        
        cursor.executemany('''
            INSERT INTO new_employee_pic_2004 (empid, pic_contents)
            VALUES (?, ?)
        ''', employee_pics)
        print(f"Inserted {num_employees} employees and photos.")
    except sqlite3.OperationalError as e:
        print(f"Error inserting employee data: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_db()