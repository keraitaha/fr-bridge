import sqlite3
import json
import datetime
import time
import schedule
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import argparse
import uuid
import requests

# CONFIGURATION
class Config:
    # Database configuration (change to real path later)
    DB_PATH = "mock.db"
    
    # Sync intervals (in seconds)
    SYNC_USERS_INTERVAL = 300
    SYNC_LOGS_INTERVAL = 86400
    
    # Sync settings
    MAX_RECORDS_PER_SYNC = 100

# DATA MODELS
@dataclass
class User:
    id: int
    name: str
    role: str
    photoPath: str
    cardNumber: Optional[str] = None
    registrationDate: str = None

@dataclass
class FaceTemplate:
    userId: int
    userName: str
    faceTemplate: str
    photoData: str
    enrollmentDate: str
    syncedToDevices: List[str] = None
    
    def __post_init__(self):
        if self.syncedToDevices is None:
            self.syncedToDevices = []

@dataclass
class AccessLog:
    id: int
    userId: Optional[int]
    accessMethod: str
    result: str
    timestamp: str
    deviceId: str

# DATABASE MANAGER
class DatabaseManager:
    def __init__(self, dbPath: str = Config.DB_PATH):
        self.dbPath = dbPath
        self.initDatabase()
    
    def initDatabase(self):
        # Initialize the SQLite database with required tables
        conn = sqlite3.connect(self.dbPath)
        cursor = conn.cursor()
        
        # Student table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_uat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                matrix_no TEXT NOT NULL,
                registration_date TEXT NOT NULL
            )
        ''')

        # Employee table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_employee_uat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                empid TEXT NOT NULL,
                joining_date TEXT NOT NULL
            )
        ''')
        
        # Pic tables should exist in real scenario
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_pic_2002 (
                id bigint(11) NOT NULL default '0',
                matrix_no varchar(20) NOT NULL default '',
                pic_name varchar(50) default NULL,
                mime_type varchar(150) default NULL,
                mime_name varchar(30) default NULL,
                pic_contents longblob
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_employee_pic_2004 (
                id bigint(11) NOT NULL default '0',
                empid varchar(20) NOT NULL default '',
                pic_name varchar(50) default NULL,
                mime_type varchar(150) default NULL,
                mime_name varchar(30) default NULL,
                pic_contents longblob
            )
        ''')

        # Face templates table - tracking synced status
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faceTemplates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId INTEGER NOT NULL,
                userType TEXT NOT NULL, 
                tableYear TEXT NOT NULL,
                syncedDevices TEXT DEFAULT '[]'
            )
        ''')
        
        # Access logs table (accesslogs_uat)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accesslogs_uat (
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

        # Terminals table (terminalsa_uat)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS terminalsa_uat (
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
        
        # Sync log table
        cursor.execute('''
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
        
        conn.commit()
        conn.close()
    
    def getUnsyncedUsers(self) -> List[Dict]:
        # Get users from both student_uat and new_employee_uat
        conn = sqlite3.connect(self.dbPath)
        cursor = conn.cursor()
        
        users = []
        
        # 1. Fetch Students
        try:
            cursor.execute('''
                SELECT id, name, matrix_no, registration_date
                FROM student_uat
            ''')
            for row in cursor.fetchall():
                users.append({
                    "id": row[0],
                    "name": row[1],
                    "role": "student",
                    "photoPath": "", # Dynamically determined later
                    "cardNumber": row[2], # matrix_no
                    "registrationDate": row[3]
                })
        except sqlite3.OperationalError:
            pass # Table might not exist yet
            
        # 2. Fetch Employees
        try:
            cursor.execute('''
                SELECT id, name, empid, joining_date
                FROM new_employee_uat
            ''')
            for row in cursor.fetchall():
                users.append({
                    "id": row[0],
                    "name": row[1],
                    "role": "employee",
                    "photoPath": "",
                    "cardNumber": row[2], # empid
                    "registrationDate": row[3] # joining_date
                })
        except sqlite3.OperationalError:
            pass
        
        conn.close()
        return users
    
    def getUnsyncedFaceTemplates(self) -> List[Dict]:
        # Get face templates for all users by querying the appropriate year-based tables
        conn = sqlite3.connect(self.dbPath)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        templates = []
        
        # Get all users first to know where to look
        # (In a highly scaled system, we would not load all into memory, but for bridge sync it's okay)
        all_users = self.getUnsyncedUsers()
        
        for user in all_users:
            user_role = user["role"]
            reg_date = user["registrationDate"]
            
            # Determine Year
            try:
                # Expecting YYYY-MM-DD or similar. Parse first 4 chars.
                year = reg_date.strip()[:4]
                if not year.isdigit():
                    continue
            except:
                continue
                
            photo_data = None
            
            # Determine Table Name
            if user_role == "student":
                table_name = f"student_pic_{year}"
                id_col = "matrix_no"
            else:
                table_name = f"new_employee_pic_{year}"
                id_col = "empid"
                
            try:
                query = f"SELECT pic_contents FROM {table_name} WHERE {id_col} = ?"
                cursor.execute(query, (user["cardNumber"],))
                row = cursor.fetchone()
                if row:
                    photo_data = row['pic_contents']
            except sqlite3.OperationalError:
                # Table for that year might not exist
                continue
                
            if photo_data:
                # Check sync status in faceTemplates table
                # We use a composite key of userId + userType because IDs might collide between tables
                cursor.execute('''
                    SELECT id, syncedDevices FROM faceTemplates 
                    WHERE userId = ? AND userType = ?
                ''', (user["id"], user_role))
                
                status_row = cursor.fetchone()
                
                synced_devices = []
                template_id = None
                
                if status_row:
                    template_id = status_row['id']
                    synced_devices = json.loads(status_row['syncedDevices']) if status_row['syncedDevices'] else []
                else:
                    # Insert new tracking record
                    cursor.execute('''
                        INSERT INTO faceTemplates (userId, userType, tableYear, syncedDevices)
                        VALUES (?, ?, ?, ?)
                    ''', (user["id"], user_role, year, '[]'))
                    template_id = cursor.lastrowid
                    conn.commit()
                
                # Convert blob to base64 string for the device client if needed, 
                # or pass raw bytes if the client handles it. 
                # Original code used strings for photoData. We'll assume base64 encoding needed or handled.
                # For simplicity here, let's assume the blob is what we want.
                # But JSON serialization might fail if it's raw bytes.
                import base64
                if isinstance(photo_data, bytes):
                    photo_data_str = base64.b64encode(photo_data).decode('utf-8')
                else:
                    photo_data_str = str(photo_data)

                templates.append({
                    "id": template_id, # ID from faceTemplates tracking table
                    "userId": user["id"],
                    "userName": user["name"],
                    "faceTemplate": "", # Not used in this logic, assuming photo matches
                    "photoData": photo_data_str,
                    "enrollmentDate": user["registrationDate"],
                    "syncedDevices": synced_devices
                })

        conn.close()
        return templates

    def getDevices(self) -> List[Dict]:
        # Get active devices from terminalsa_uat
        conn = sqlite3.connect(self.dbPath)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM terminalsa_uat WHERE active = '1'
        ''')
        
        devices = []
        for row in cursor.fetchall():
            devices.append(dict(row))
            
        conn.close()
        return devices
    
    def markFaceTemplateSynced(self, templateId: int, deviceName: str):
        # Mark a face template as synced to a specific device
        conn = sqlite3.connect(self.dbPath)
        cursor = conn.cursor()
        
        # Get current synced devices
        cursor.execute('SELECT syncedDevices FROM faceTemplates WHERE id = ?', (templateId,))
        row = cursor.fetchone()
        
        if row:
            syncedDevices = json.loads(row[0]) if row[0] else []
            if deviceName not in syncedDevices:
                syncedDevices.append(deviceName)
                
                cursor.execute('''
                    UPDATE faceTemplates 
                    SET syncedDevices = ?
                    WHERE id = ?
                ''', (json.dumps(syncedDevices), templateId))
                
                conn.commit()
        
        conn.close()
    
    def saveDeviceAccessLogs(self, deviceClient: Any, logs: List[Dict]):
        # Save access logs retrieved from devices into accesslogs_uat
        if not logs:
            return 0
        
        conn = sqlite3.connect(self.dbPath)
        cursor = conn.cursor()
        
        savedCount = 0
        for log in logs:
            try:
                # Convert timestamp to datetime string
                create_time = log.get('CreateTime')
                if create_time:
                    dt_str = datetime.datetime.fromtimestamp(int(create_time)).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    dt_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Map fields
                log_id = str(uuid.uuid4())
                card_id = log.get('CardNo', '')
                terminal_id = deviceClient.terminalId
                terminal_ip = deviceClient.ip
                door_id = str(log.get('Door', ''))
                term_door = f"{terminal_id}:{door_id}"
                
                # Map Type (Entry/Exit) to in_out (1/2) - Assumption
                log_type = log.get('Type', '')
                in_out = 1 if log_type == 'Entry' else 2 if log_type == 'Exit' else 0
                
                verify_source = int(log.get('Method', 0))
                verify_status = int(log.get('Status', 0))
                user_id = log.get('UserID', '')

                # Check for duplicates based on terminalid and datetime
                cursor.execute('''
                    SELECT id FROM accesslogs_uat 
                    WHERE terminalid = ? AND datetime = ? AND cardid = ?
                ''', (terminal_id, dt_str, card_id))
                
                if cursor.fetchone():
                    continue

                cursor.execute('''
                    INSERT INTO accesslogs_uat 
                    (id, cardid, datetime, terminalid, terminalip, doorid, termdoor, 
                     in_out, verifysource, funckey, verifystatus, eventcode, userid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    log_id,
                    card_id,
                    dt_str,
                    terminal_id,
                    terminal_ip,
                    door_id,
                    term_door,
                    in_out,
                    verify_source,
                    0, # funckey
                    verify_status,
                    '', # eventcode
                    user_id
                ))
                
                if cursor.rowcount > 0:
                    savedCount += 1
                    
            except Exception as e:
                print(f"Error saving log: {e}")
        
        conn.commit()
        conn.close()
        return savedCount
    
    def getLastSyncedLogTime(self, terminalId: str) -> Optional[int]:
        # Get the last datetime synced from a device and convert to timestamp
        conn = sqlite3.connect(self.dbPath)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MAX(datetime) 
            FROM accesslogs_uat 
            WHERE terminalid = ?
        ''', (terminalId,))
        
        result = cursor.fetchone()[0]
        conn.close()
        
        if result and result != '0000-00-00 00:00:00':
            try:
                dt = datetime.datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
                return int(dt.timestamp())
            except:
                return None
        return None
    
    def logSyncOperation(self, syncType: str, deviceName: Optional[str], 
                        recordsSynced: int, status: str, errorMessage: Optional[str] = None):
        # Log a sync operation
        conn = sqlite3.connect(self.dbPath)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO syncLogs (syncType, deviceName, recordsSynced, status, errorMessage, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            syncType,
            deviceName,
            recordsSynced,
            status,
            errorMessage,
            datetime.datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()

# DEVICE CLIENT
class DeviceClient:
    # Client for interacting with devices via their APIs
    
    def __init__(self, deviceConfig: Dict):
        self.name = deviceConfig.get("terminalname", "Unknown")
        self.terminalId = deviceConfig.get("terminalid", "")
        self.ip = deviceConfig.get("ip", "")
        self.port = deviceConfig.get("portno", "80")
        self.username = deviceConfig.get("username", "admin")
        self.password = deviceConfig.get("password", "password")
        
        self.baseUrl = f"http://{self.ip}:{self.port}"
        self.auth = (self.username, self.password)
    
    def enrollUser(self, userData: Dict) -> bool:
        # Enroll a user on the device
        try:
            # Convert user data to format
            payload = {
                "CardName": userData["name"],
                "CardNo": userData["cardNumber"] or "",
                "UserID": str(userData["id"]),
                "CardStatus": 0,
                "CardType": 0,
                "Password": "",
                "Doors": [1],
                "TimeSections": [1],
                "ValidDateStart": datetime.datetime.now().strftime("%Y%m%d %H%M%S"),
                "ValidDateEnd": (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%Y%m%d %H%M%S")
            }
            
            # Construct URL with key=value format
            params = f"action=insert&name=AccessControlCard"
            for key, value in payload.items():
                if isinstance(value, list):
                    for i, item in enumerate(value):
                        params += f"&{key}[{i}]={item}"
                else:
                    params += f"&{key}={value}"
            
            url = f"{self.baseUrl}/cgi-bin/recordUpdater.cgi?{params}"
            
            # In real implementation, this would be an actual HTTP request
            # For mock, we'll simulate success
            print(f"  → Enrolling user {userData['name']} on {self.name}")
            
            # Call API
            response = self.apiCall(url)
            
            if response:
                print(f"  User enrolled successfully on {self.name}")
                return True
            else:
                print(f"  Failed to enroll user on {self.name}")
                return False
                
        except Exception as e:
            print(f"  Error enrolling user on {self.name}: {e}")
            return False
    
    def enrollFaceTemplate(self, faceTemplate: Dict) -> bool:
        # Enroll a face template on the device
        try:
            url = f"{self.baseUrl}/cgi-bin/FaceInfoManager.cgi?action=add"
            
            # Prepare payload
            payload = {
                "UserID": str(faceTemplate["userId"]),
                "Info": {
                    "UserName": faceTemplate["userName"],
                    "FaceData": [faceTemplate["faceTemplate"]] if faceTemplate.get("faceTemplate") else [],
                    "PhotoData": [faceTemplate["photoData"]] if faceTemplate.get("photoData") else []
                }
            }
            
            print(f"  → Enrolling face template for user {faceTemplate['userName']} on {self.name}")
            
            # Call API
            response = self.apiCall(url, method="POST", json=payload)
            
            if response:
                print(f" Face template enrolled successfully on {self.name}")
                return True
            else:
                print(f" Failed to enroll face template on {self.name}")
                return False
                
        except Exception as e:
            print(f" Error enrolling face template on {self.name}: {e}")
            return False
    
    def getOfflineAccessLogs(self, startTime: Optional[int] = None, endTime: Optional[int] = None) -> List[Dict]:
        # Get offline access logs from device
        try:
            params = "action=find&name=AccessControlCardRec"
            params += f"&count={Config.MAX_RECORDS_PER_SYNC}"
            
            if startTime:
                params += f"&StartTime={startTime}"
            if endTime:
                params += f"&EndTime={endTime}"
            
            url = f"{self.baseUrl}/cgi-bin/recordFinder.cgi?{params}"
            
            print(f" Fetching offline access logs from {self.name}")
            print(f" Time range: {startTime} to {endTime}")
            
            # Call API
            response = self.apiCall(url)
            
            if response:
                # Parse key=value response into list of dictionaries
                logs = self._parseKeyValueResponse(response)
                print(f" Retrieved {len(logs)} logs from {self.name}")
                return logs
            else:
                print(f" Failed to retrieve logs from {self.name}")
                return []
                
        except Exception as e:
            print(f" Error fetching logs from {self.name}: {e}")
            return []
    
    def apiCall(self, url: str, method: str = "GET", json: Optional[Dict] = None) -> Any:
        # Actual implementation to be used later:
        # try:
        #     if method == "GET":
        #         response = requests.get(url, auth=self.auth, timeout=10)
        #     elif method == "POST":
        #         response = requests.post(url, auth=self.auth, json=json, timeout=10)
        #     
        #     if response.status_code == 200:
        #         return response.text
        #     return None
        # except Exception as e:
        #     print(f"Request failed: {e}")
        #     return None
        return self._mockApiCall(url, method, json)

    def _mockApiCall(self, url: str, method: str = "GET", json: Optional[Dict] = None) -> Any:
        # Simulate network delay
        time.sleep(0.1)
        
        # For GET requests to recordFinder, return mock data
        if "recordFinder.cgi" in url:
            return self._generateMockLogs()
        # For other requests, simulate success
        else:
            return "OK"
    
    def _generateMockLogs(self) -> str:
        # Generate mock device logs
        import random
        
        logs = []
        for i in range(random.randint(5, 15)):
            logs.extend([
                f"records[{i}].RecNo={1000 + i}",
                f"records[{i}].CreateTime={int(time.time()) - random.randint(0, 86400)}",
                f"records[{i}].CardNo=CARD{random.randint(100, 999)}",
                f"records[{i}].CardName=User{random.randint(1, 50)}",
                f"records[{i}].UserID=User{random.randint(1, 50)}",
                f"records[{i}].Type={'Entry' if random.random() > 0.3 else 'Exit'}",
                f"records[{i}].Status={1 if random.random() > 0.1 else 0}",
                f"records[{i}].Method={15 if random.random() > 0.5 else 1}",
                f"records[{i}].Door=1",
                f"records[{i}].ReaderID=reader{random.randint(1, 3)}"
            ])
        
        response = [
            f"totalCount={len(logs)//10}",
            f"found={len(logs)//10}"
        ]
        response.extend(logs)
        
        return "\n".join(response)
    
    def _parseKeyValueResponse(self, response: str) -> List[Dict]:
        # Parse key=value response format into list of dictionaries
        lines = response.strip().split('\n')
        
        # Parse records
        records = {}
        for line in lines:
            if '=' in line:
                key, value = line.split('=', 1)
                
                # Parse array indices like records[0].RecNo
                if key.startswith('records[') and '].' in key:
                    # Extract index and field name
                    start_idx = key.find('[') + 1
                    end_idx = key.find(']')
                    record_idx = int(key[start_idx:end_idx])
                    field_name = key.split('.', 1)[1]
                    
                    # Initialize record if not exists
                    if record_idx not in records:
                        records[record_idx] = {}
                    
                    # Store value
                    records[record_idx][field_name] = value
        
        # Convert to list
        return list(records.values())

# SYNC MANAGER
class SyncManager:
    # Manages synchronization between database and devices
    
    def __init__(self):
        self.dbManager = DatabaseManager()
        self.deviceClients = [] # Will be loaded dynamically
        self.running = False
    
    def start(self):
        # Start the sync manager
        self.running = True
        print("Starting Device Bridge Sync Manager")
        print(f"Database: {Config.DB_PATH}")
        
        # Load devices
        self.refreshDevices()
        print(f"Devices: {len(self.deviceClients)}")
        print(f"Sync intervals: Users every {Config.SYNC_USERS_INTERVAL}s, Logs every {Config.SYNC_LOGS_INTERVAL}s")
        print("=" * 60)
        
        # Schedule jobs -- SYNC_USERS_INTERVAL 300
        schedule.every(Config.SYNC_USERS_INTERVAL).seconds.do(self.syncUsersToDevices)
        schedule.every(Config.SYNC_LOGS_INTERVAL).seconds.do(self.syncLogsFromDevices)
        
        # Run initial sync
        print("\nRunning initial sync...")
        self.syncUsersToDevices()
        self.syncLogsFromDevices()
        
        # Keep running
        while self.running:
            schedule.run_pending()
            time.sleep(1)
            
    def refreshDevices(self):
        # Refresh device list from database
        devices = self.dbManager.getDevices()
        self.deviceClients = [DeviceClient(d) for d in devices]
    
    def stop(self):
        # Stop the sync manager
        self.running = False
        print("\nStopping sync manager...")
    
    def syncUsersToDevices(self):
        # Sync users and face templates to all devices
        print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Syncing users to devices...")
        
        try:
            # Get unsynced users and face templates
            users = self.dbManager.getUnsyncedUsers()
            faceTemplates = self.dbManager.getUnsyncedFaceTemplates()
            
            totalUsersSynced = 0
            totalTemplatesSynced = 0
            
            # Refresh devices to ensure we have latest config
            self.refreshDevices()
            
            # Sync to each device
            for deviceClient in self.deviceClients:
                print(f"\nSyncing to device: {deviceClient.name}")
                
                # Sync users
                usersSynced = 0
                for user in users:
                    if deviceClient.enrollUser(user):
                        usersSynced += 1
                
                # Sync face templates
                templatesSynced = 0
                for template in faceTemplates:
                    if deviceClient.name not in template["syncedDevices"]:
                        if deviceClient.enrollFaceTemplate(template):
                            self.dbManager.markFaceTemplateSynced(template["id"], deviceClient.name)
                            templatesSynced += 1
                
                totalUsersSynced += usersSynced
                totalTemplatesSynced += templatesSynced
                
                print(f" Device {deviceClient.name}: {usersSynced} users, {templatesSynced} face templates")
            
            # Log sync operation
            self.dbManager.logSyncOperation(
                syncType="users_to_devices",
                deviceName=None,
                recordsSynced=totalUsersSynced + totalTemplatesSynced,
                status="success"
            )
            
            print(f"\nSync completed: {totalUsersSynced} users, {totalTemplatesSynced} face templates")
            
        except Exception as e:
            errorMsg = str(e)
            print(f"Error during user sync: {errorMsg}")
            self.dbManager.logSyncOperation(
                syncType="users_to_devices",
                deviceName=None,
                recordsSynced=0,
                status="error",
                errorMessage=errorMsg
            )
    
    def syncLogsFromDevices(self):
        # Sync access logs from all devices
        print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Syncing logs from devices...")
        
        totalLogsSaved = 0
        
        # Refresh devices
        self.refreshDevices()
        
        for deviceClient in self.deviceClients:
            print(f"\nSyncing logs from device: {deviceClient.name}")
            
            try:
                # Get last synced time
                lastSyncedTime = self.dbManager.getLastSyncedLogTime(deviceClient.terminalId)
                currentTime = int(time.time())
                
                # Fetch logs from device
                logs = deviceClient.getOfflineAccessLogs(
                    startTime=lastSyncedTime,
                    endTime=currentTime
                )
                
                # Save logs to database
                if logs:
                    savedCount = self.dbManager.saveDeviceAccessLogs(deviceClient, logs)
                    totalLogsSaved += savedCount
                    
                    # Log sync operation
                    self.dbManager.logSyncOperation(
                        syncType="logs_from_device",
                        deviceName=deviceClient.name,
                        recordsSynced=savedCount,
                        status="success"
                    )
                    
                    print(f" Saved {savedCount} new logs from {deviceClient.name}")
                else:
                    print(f" No new logs from {deviceClient.name}")
                    
            except Exception as e:
                errorMsg = str(e)
                print(f" Error syncing logs from {deviceClient.name}: {errorMsg}")
                self.dbManager.logSyncOperation(
                    syncType="logs_from_device",
                    deviceName=deviceClient.name,
                    recordsSynced=0,
                    status="error",
                    errorMessage=errorMsg
                )
        
        print(f"\nLog sync completed: {totalLogsSaved} total logs saved")

# CLI APPLICATION
class BridgeCLI:
    # Command Line Interface for the Bridge
    
    def __init__(self):
        self.syncManager = SyncManager()
        self.dbManager = DatabaseManager()
        
    def run(self):
        # Run the CLI application
        parser = argparse.ArgumentParser(description='Device Bridge - Sync between database and devices')
        parser.add_argument('command', choices=['start', 'stop', 'status', 'sync-users', 'sync-logs', 'test'], help='Command to execute')
        parser.add_argument('--device', help='Specific device name for sync operations')
        
        args = parser.parse_args()
        
        if args.command == 'start':
            self.start_sync_service()
        elif args.command == 'stop':
            self.stop_sync_service()
        elif args.command == 'status':
            self.show_status()
        elif args.command == 'sync-users':
            self.manual_sync_users(args.device)
        elif args.command == 'sync-logs':
            self.manual_sync_logs(args.device)
        elif args.command == 'test':
            self.test_connections()
    
    def start_sync_service(self):
        # Start the sync service
        print("Starting Bridge Sync Service...")
        
        # Run in background thread
        def run_sync_manager():
            self.syncManager.start()
        
        thread = threading.Thread(target=run_sync_manager, daemon=True)
        thread.start()
        
        print("Sync service started. Press Ctrl+C to stop.")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.syncManager.stop()
            print("\nSync service stopped.")
    
    def stop_sync_service(self):
        # Stop the sync service
        self.syncManager.stop()
    
    def show_status(self):
        # Show current status
        conn = sqlite3.connect(Config.DB_PATH)
        cursor = conn.cursor()
        
        # Count records
        cursor.execute('SELECT COUNT(*) FROM users')
        userCount = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM faceTemplates')
        templateCount = cursor.fetchone()[0]
        
        # Check if accesslogs_uat exists
        try:
            cursor.execute('SELECT COUNT(*) FROM accesslogs_uat')
            logCount = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            logCount = "N/A (table missing)"
        
        cursor.execute('SELECT COUNT(*) FROM syncLogs')
        syncCount = cursor.fetchone()[0]
        
        cursor.execute('SELECT syncType, status, COUNT(*) FROM syncLogs GROUP BY syncType, status')
        syncStats = cursor.fetchall()
        
        conn.close()
        
        print("=" * 60)
        print("BRIDGE STATUS")
        print("=" * 60)
        print(f"Database Statistics:")
        print(f" Users: {userCount}")
        print(f" Face Templates: {templateCount}")
        print(f" Access Logs: {logCount}")
        print(f" Sync Operations: {syncCount}")
        
        # Refresh devices
        self.syncManager.refreshDevices()
        print(f"\nConfigured Devices: {len(self.syncManager.deviceClients)}")
        for client in self.syncManager.deviceClients:
            print(f" - {client.name} ({client.ip})")
        
        print(f"\nSync Intervals:")
        print(f" Users to Devices: Every {Config.SYNC_USERS_INTERVAL} seconds")
        print(f" Logs from Devices: Every {Config.SYNC_LOGS_INTERVAL} seconds")
        
        if syncStats:
            print(f"\nSync Statistics:")
            for syncType, status, count in syncStats:
                print(f" {syncType}: {status} ({count} times)")
    
    def manual_sync_users(self, deviceName: Optional[str] = None):
        # Manually sync users to devices
        print("Manually syncing users to devices...")
        
        if deviceName:
            # Sync to specific device
            self.syncManager.refreshDevices()
            deviceClient = next((d for d in self.syncManager.deviceClients if d.name == deviceName), None)
            if deviceClient:
                # Get users and sync
                users = self.dbManager.getUnsyncedUsers()
                faceTemplates = self.dbManager.getUnsyncedFaceTemplates()
                
                for user in users:
                    deviceClient.enrollUser(user)
                
                for template in faceTemplates:
                    if deviceName not in template["syncedDevices"]:
                        deviceClient.enrollFaceTemplate(template)
                        self.dbManager.markFaceTemplateSynced(template["id"], deviceName)
                
                print(f"Manual sync to {deviceName} completed.")
            else:
                print(f"Device {deviceName} not found.")
        else:
            # Sync to all devices
            self.syncManager.syncUsersToDevices()
    
    def manual_sync_logs(self, deviceName: Optional[str] = None):
        # Manually sync logs from devices
        print("Manually syncing logs from devices...")
        
        if deviceName:
            # Sync from specific device
            self.syncManager.refreshDevices()
            deviceClient = next((d for d in self.syncManager.deviceClients if d.name == deviceName), None)
            if deviceClient:
                lastSyncedTime = self.dbManager.getLastSyncedLogTime(deviceClient.terminalId)
                currentTime = int(time.time())
                
                logs = deviceClient.getOfflineAccessLogs(
                    startTime=lastSyncedTime,
                    endTime=currentTime
                )
                
                if logs:
                    savedCount = self.dbManager.saveDeviceAccessLogs(deviceClient, logs)
                    print(f"Saved {savedCount} logs from {deviceName}.")
                else:
                    print(f"No new logs from {deviceName}.")
            else:
                print(f"Device {deviceName} not found.")
        else:
            # Sync from all devices
            self.syncManager.syncLogsFromDevices()
    
    def test_connections(self):
        # Test connections to devices
        print("Testing connections to devices...")
        
        self.syncManager.refreshDevices()
        for client in self.syncManager.deviceClients:
            print(f"\nTesting {client.name} ({client.ip}):")
            
            try:
                # Try to connect (in real implementation, this would be an HTTP request)
                url = f"http://{client.ip}:{client.port}"
                print(f" Connecting to {url}...")
                
                # Simulate connection test
                time.sleep(0.5)
                
                # Mock response
                print(f" Connection successful")
                print(f" Authentication: {client.username}/{'*' * len(client.password)}")
                
            except Exception as e:
                print(f" Connection failed: {e}")

# MAIN ENTRY POINT
if __name__ == "__main__":
    cli = BridgeCLI()
    cli.run()