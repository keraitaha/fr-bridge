import sqlite3
import datetime
import os
import configparser
import random

def setup_mock_db():
    print("Setting up mock databases...")

    # Load Config to get paths
    config = configparser.ConfigParser()
    if os.path.exists('config.ini'):
        config.read('config.ini')
        noble_path = config.get('Database.Noble', 'Path', fallback='noble_mock.db')
        cms_path = config.get('Database.CMS', 'Path', fallback='cms_mock.db')
    else:
        print("config.ini not found. Using default paths.")
        noble_path = 'noble_mock.db' # Default fallback
        cms_path = 'cms_mock.db'     # Default fallback

    print(f"Noble DB Path: {noble_path}")
    print(f"CMS DB Path: {cms_path}")

    # Remove existing files to start fresh
    if os.path.exists(noble_path):
        try:
            os.remove(noble_path)
            print(f"Removed existing {noble_path}")
        except Exception as e:
            print(f"Could not remove {noble_path}: {e}")
            
    if os.path.exists(cms_path):
        try:
            os.remove(cms_path)
            print(f"Removed existing {cms_path}")
        except Exception as e:
            print(f"Could not remove {cms_path}: {e}")

    # --- Setup Noble Database (Terminals, Logs) ---
    print(f"Creating Noble DB at {noble_path}...")
    conn_noble = sqlite3.connect(noble_path)
    cursor_noble = conn_noble.cursor()

    # Terminal Table
    cursor_noble.execute('''
        CREATE TABLE IF NOT EXISTS terminalsa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            terminalname VARCHAR(255) NOT NULL DEFAULT '',
            terminalid VARCHAR(8) NOT NULL DEFAULT '',
            ip VARCHAR(16) NOT NULL DEFAULT '',
            portno VARCHAR(8) NOT NULL DEFAULT '2000',
            active CHAR(1) NOT NULL DEFAULT '1',
            proctime DATETIME NOT NULL DEFAULT '0000-00-00 00:00:00',
            model VARCHAR(16) NOT NULL DEFAULT 'E1080',
            fwver VARCHAR(32) NOT NULL DEFAULT '0.00',
            macaddr VARCHAR(24) NOT NULL DEFAULT '',
            doorno VARCHAR(24) NOT NULL DEFAULT '',
            doorstatus INTEGER DEFAULT 0,
            doorstatussince DATETIME NOT NULL DEFAULT '0000-00-00 00:00:00',
            users INTEGER NOT NULL DEFAULT 0,
            logcount INTEGER NOT NULL DEFAULT 0,
            netstatus CHAR(1) NOT NULL DEFAULT 0,
            owner VARCHAR(50) DEFAULT NULL,
            logtotal INTEGER DEFAULT NULL,
            relaystatus INTEGER DEFAULT -1,
            username VARCHAR(50) DEFAULT 'admin',
            password VARCHAR(50) DEFAULT 'password'
        )
    ''')

    # Access Logs Table
    cursor_noble.execute('''
        CREATE TABLE IF NOT EXISTS accesslogs (
            id VARCHAR(48) NOT NULL PRIMARY KEY,
            cardid VARCHAR(16) NOT NULL DEFAULT '',
            datetime DATETIME NOT NULL DEFAULT '0000-00-00 00:00:00',
            terminalid VARCHAR(8) NOT NULL DEFAULT '',
            terminalip VARCHAR(24) DEFAULT NULL,
            doorid VARCHAR(8) NOT NULL DEFAULT '',
            termdoor VARCHAR(24) DEFAULT NULL,
            in_out INTEGER NOT NULL DEFAULT 0,
            verifysource INTEGER NOT NULL DEFAULT 0,
            funckey INTEGER NOT NULL DEFAULT 0,
            verifystatus INTEGER NOT NULL DEFAULT 0,
            eventcode VARCHAR(32) DEFAULT NULL,
            userid VARCHAR(16) DEFAULT NULL
        )
    ''')
    
    # Sync Log Table
    cursor_noble.execute('''
        CREATE TABLE IF NOT EXISTS syncLogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            syncType TEXT NOT NULL,
            deviceName TEXT,
            recordsSynced INTEGER,
            status TEXT NOT NULL,
            errorMessage TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    # Insert Mock Terminals
    terminals = [
        (1, "Main Entrance", "1001", "192.168.1.201", "80", "1", "admin", "password"),
        (2, "Server Room", "1002", "192.168.1.202", "80", "1", "admin", "password"),
        (3, "Back Office", "1003", "192.168.1.203", "80", "0", "admin", "password"), # Inactive
    ]
    try:
        cursor_noble.executemany('''
            INSERT INTO terminalsa (id, terminalname, terminalid, ip, portno, active, username, password)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', terminals)
        print(f"Inserted {cursor_noble.rowcount} terminals into Noble DB.")
    except Exception as e:
        print(f"Error inserting terminals: {e}")

    conn_noble.commit()
    conn_noble.close()

    # --- Setup CMS Database (Users, Employees, Photos) ---
    print(f"Creating CMS DB at {cms_path}...")
    conn_cms = sqlite3.connect(cms_path)
    cursor_cms = conn_cms.cursor()

    # Student Table
    cursor_cms.execute('''
        CREATE TABLE IF NOT EXISTS student (
            matrix_no VARCHAR(20) NOT NULL PRIMARY KEY,
            name TEXT NOT NULL,
            registration_date TEXT NOT NULL
        )
    ''')

    # Employee Table
    cursor_cms.execute('''
        CREATE TABLE IF NOT EXISTS new_employee (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            empid TEXT NOT NULL,
            app_date TEXT NOT NULL
        )
    ''')
    
    # Photo Tables
    cursor_cms.execute('''
        CREATE TABLE IF NOT EXISTS student_pic_2002 (
            id bigint(11) NOT NULL default '0',
            matrix_no varchar(20) NOT NULL default '',
            pic_name varchar(50) default NULL,
            mime_type varchar(150) default NULL,
            mime_name varchar(30) default NULL,
            pic_contents longblob
        )
    ''')

    cursor_cms.execute('''
        CREATE TABLE IF NOT EXISTS new_employee_pic_2004 (
            id bigint(11) NOT NULL default '0',
            empid varchar(20) NOT NULL default '',
            pic_name varchar(50) default NULL,
            mime_type varchar(150) default NULL,
            mime_name varchar(30) default NULL,
            pic_contents longblob
        )
    ''')

    # Face Templates Table
    cursor_cms.execute('''
        CREATE TABLE IF NOT EXISTS faceTemplates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userId TEXT NOT NULL,
            userType TEXT NOT NULL, 
            tableYear TEXT NOT NULL,
            syncedDevices TEXT DEFAULT '[]'
        )
    ''')

    # Insert Random Students (Year 2002)
    num_students = random.randint(5, 10)
    print(f"Inserting {num_students} random students...")
    student_data = []
    student_pics = []
    
    # Add a few fixed ones for easier testing
    fixed_students = [
        ("Alice Smith", "U2002001", "2002-01-15"),
        ("Bob Jones", "U2002002", "2002-02-20")
    ]
    for s in fixed_students:
        student_data.append(s)
        student_pics.append((s[1], b"fake_photo_blob_" + s[1].encode()))

    for i in range(num_students):
        name = f"Student_{i+1}_{random.randint(1000, 9999)}"
        matrix_no = f"U2002{i+10:03d}"
        reg_date = f"2002-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        student_data.append((name, matrix_no, reg_date))
        student_pics.append((matrix_no, b"fake_photo_blob_" + matrix_no.encode()))

    try:
        cursor_cms.executemany('''
            INSERT INTO student (name, matrix_no, registration_date)
            VALUES (?, ?, ?)
        ''', student_data)
        
        cursor_cms.executemany('''
            INSERT INTO student_pic_2002 (matrix_no, pic_contents)
            VALUES (?, ?)
        ''', student_pics)
        print(f"Inserted {len(student_data)} students into CMS DB.")
    except Exception as e:
        print(f"Error inserting students: {e}")

    # Insert Random Employees (Year 2004)
    num_employees = random.randint(3, 8)
    print(f"Inserting {num_employees} random employees...")
    employee_data = []
    employee_pics = []
    
    fixed_employees = [
        ("David Wilson", "E1001", "2004-05-01"),
    ]
    for e in fixed_employees:
        employee_data.append(e)
        employee_pics.append((e[1], b"fake_photo_blob_" + e[1].encode()))

    for i in range(num_employees):
        name = f"Employee_{i+1}_{random.randint(1000, 9999)}"
        empid = f"E10{i+10:02d}"
        join_date = f"2004-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        employee_data.append((name, empid, join_date))
        employee_pics.append((empid, b"fake_photo_blob_" + empid.encode()))

    try:
        cursor_cms.executemany('''
            INSERT INTO new_employee (name, empid, app_date)
            VALUES (?, ?, ?)
        ''', employee_data)
        
        cursor_cms.executemany('''
            INSERT INTO new_employee_pic_2004 (empid, pic_contents)
            VALUES (?, ?)
        ''', employee_pics)
        print(f"Inserted {len(employee_data)} employees into CMS DB.")
    except Exception as e:
        print(f"Error inserting employees: {e}")

    conn_cms.commit()
    conn_cms.close()
    
    print("Mock databases setup complete.")

if __name__ == "__main__":
    setup_mock_db()
