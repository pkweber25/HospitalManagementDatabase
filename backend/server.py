from flask import Flask, request, jsonify, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
import os
import secrets, string
ALLOWED_ROLES = ['admin','doctor','receptionist','patient']

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder=None)
CORS(app) # Allows local HTML file to fetch data from this API

# Project paths and JWT config
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-this-in-production-12345678")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")

# ---------------- DATABASE CONNECTION ----------------
def get_db_connection():
    # open a fresh connection per request in a web app
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# Helpers for auth

def ensure_users_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL,
        full_name VARCHAR(255),
        patient_record_id INT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    conn.commit()
    # Helper: safely add a column to an existing table, no-op if it already exists.
    def safe_add_column(table, column, definition):
        c = conn.cursor()
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            c.close()

    safe_add_column("Users",       "patient_record_id", "INT NULL")
    safe_add_column("Appointment", "NurseID",           "INT NULL")

    # Always ensure the admin account exists.
    # INSERT IGNORE is a no-op if the username already exists, so this is safe on every restart.
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    admin_full_name = os.getenv('ADMIN_FULL_NAME', 'System Administrator')
    if not admin_password:
        admin_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        print(f"[startup] Generated admin password: {admin_password}")
    password_hash = generate_password_hash(admin_password)
    admin_cursor = conn.cursor()
    try:
        admin_cursor.execute(
            "INSERT IGNORE INTO Users (username, password_hash, role, full_name) VALUES (%s,%s,'admin',%s)",
            (admin_username, password_hash, admin_full_name)
        )
        conn.commit()
        if admin_cursor.rowcount > 0:
            print(f"[startup] Admin account created — username='{admin_username}' password='{admin_password}'")
        else:
            print(f"[startup] Admin account already exists — username='{admin_username}'")
    except Exception as e:
        print(f"[startup] Failed to ensure admin account: {e}")
    finally:
        admin_cursor.close()
        cursor.close()
        conn.close()

# create users table on startup (silent if DB not configured yet)
try:
    print("Attempting to initialize Users table...")
    ensure_users_table()
    print("Users table check complete.")
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: {e}")

# Decorators for token verification and role checks

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            g.current_user = {'id': payload.get('user_id'), 'username': payload.get('username'), 'role': payload.get('role')}
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Invalid token: '+str(e)}), 401
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    def wrapper(f):
        @wraps(f)
        def inner(*args, **kwargs):
            user = getattr(g, 'current_user', None)
            if not user:
                return jsonify({'error': 'Authentication required'}), 401
            if user.get('role') not in roles:
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return inner
    return wrapper



# ---------------- AUTH ----------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username') or data.get('Username')
    password = data.get('password') or data.get('Password')
    full_name = data.get('full_name') or data.get('FullName') or None
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    # Self-registration is only for patients
    role = 'patient'
    password_hash = generate_password_hash(password)
    # Split full_name into first/last; fall back to username if omitted
    if full_name:
        parts = full_name.strip().split(' ', 1)
        first_name = parts[0]
        last_name  = parts[1] if len(parts) > 1 else ''
    else:
        first_name = username
        last_name  = ''
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Insert the login account
        cursor.execute(
            'INSERT INTO Users (username,password_hash,role,full_name) VALUES (%s,%s,%s,%s)',
            (username, password_hash, role, full_name)
        )
        user_id = cursor.lastrowid
        # Auto-create a linked Patient record so the portal works immediately
        cursor.execute('SELECT COALESCE(MAX(PatientID), 0) + 1 FROM Patient')
        new_patient_id = cursor.fetchone()[0]
        cursor.execute(
            'INSERT INTO Patient (PatientID, FirstName, LastName) VALUES (%s, %s, %s)',
            (new_patient_id, first_name, last_name)
        )
        cursor.execute(
            'UPDATE Users SET patient_record_id=%s WHERE id=%s',
            (new_patient_id, user_id)
        )
        conn.commit()
        return jsonify({'message': 'User registered', 'role': role}), 201
    except Exception as e:
        conn.rollback()
        if 'Duplicate' in str(e) or 'duplicate' in str(e) or '1062' in str(e):
            return jsonify({'error': 'Username already exists'}), 400
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username') or data.get('Username')
    password = data.get('password') or data.get('Password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE username=%s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401
    payload = {'user_id': user['id'], 'username': user['username'], 'role': user['role'], 'exp': datetime.utcnow() + timedelta(hours=8)}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    # pyjwt may return bytes
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return jsonify({'token': token, 'role': user['role'], 'username': user['username']})

# ---------------- USER MANAGEMENT ----------------
@app.route('/api/users', methods=['GET'])
@token_required
@require_role('admin')
def list_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, role, full_name FROM Users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(users)


# Admin create user
@app.route('/api/users', methods=['POST'])
@token_required
@require_role('admin')
def admin_create_user():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    role = data.get('role') or 'patient'
    full_name = data.get('full_name')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    if role not in ALLOWED_ROLES:
        return jsonify({'error': 'Invalid role'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO Users (username,password_hash,role,full_name) VALUES (%s,%s,%s,%s)", (username, password_hash, role, full_name))
        conn.commit()
        return jsonify({'message': 'User created'}), 201
    except Exception as e:
        if 'Duplicate' in str(e) or 'duplicate' in str(e) or '1062' in str(e):
            return jsonify({'error': 'Username already exists'}), 400
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/api/users/<int:user_id>/password', methods=['PUT'])
@token_required
@require_role('admin')
def admin_change_user_password(user_id):
    data = request.json or {}
    new_password = data.get('new_password')
    if not new_password:
        return jsonify({'error': 'new_password required'}), 400
    new_hash = generate_password_hash(new_password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Users SET password_hash=%s WHERE id=%s", (new_hash, user_id))
        conn.commit()
        return jsonify({'message': 'Password updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/api/users/<int:user_id>/role', methods=['PUT'])
@token_required
@require_role('admin')
def admin_change_user_role(user_id):
    data = request.json or {}
    new_role = data.get('role')
    if not new_role:
        return jsonify({'error': 'role required'}), 400
    if new_role not in ALLOWED_ROLES:
        return jsonify({'error': 'Invalid role'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM Users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    old_role = user.get('role')
    # prevent removing last admin
    if old_role == 'admin' and new_role != 'admin':
        cursor.execute("SELECT COUNT(*) as cnt FROM Users WHERE role='admin'")
        cnt_row = cursor.fetchone()
        cnt = cnt_row.get('cnt') if isinstance(cnt_row, dict) else cnt_row[0]
        if cnt <= 1:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Cannot remove role from last admin'}), 400
    try:
        update_cursor = conn.cursor()
        update_cursor.execute("UPDATE Users SET role=%s WHERE id=%s", (new_role, user_id))
        conn.commit()
        update_cursor.close()
        return jsonify({'message': 'Role updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@token_required
@require_role('admin')
def admin_delete_user(user_id):
    # Prevent admin from deleting themselves
    if g.current_user and g.current_user.get('id') == user_id:
        return jsonify({'error': "Cannot delete yourself"}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM Users WHERE id=%s", (user_id,))
    target = cursor.fetchone()
    if not target:
        cursor.close()
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    if target.get('role') == 'admin':
        cursor.execute("SELECT COUNT(*) as cnt FROM Users WHERE role='admin'")
        cnt_row = cursor.fetchone()
        cnt = cnt_row.get('cnt') if isinstance(cnt_row, dict) else cnt_row[0]
        if cnt <= 1:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Cannot delete last admin'}), 400
    try:
        del_cursor = conn.cursor()
        del_cursor.execute("DELETE FROM Users WHERE id=%s", (user_id,))
        conn.commit()
        del_cursor.close()
        return jsonify({'message':'User deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


# Self endpoints
@app.route('/api/users/me', methods=['GET'])
@token_required
def get_my_profile():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, role, full_name FROM Users WHERE id=%s", (g.current_user.get('id'),))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(user or {})


@app.route('/api/users/me/password', methods=['PUT'])
@token_required
def change_own_password():
    data = request.json or {}
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({'error': 'current_password and new_password required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE id=%s", (g.current_user.get('id'),))
    user = cursor.fetchone()
    if not user or not check_password_hash(user.get('password_hash', ''), current_password):
        cursor.close()
        conn.close()
        return jsonify({'error': 'Invalid current password'}), 401
    try:
        new_hash = generate_password_hash(new_password)
        update_cursor = conn.cursor()
        update_cursor.execute("UPDATE Users SET password_hash=%s WHERE id=%s", (new_hash, g.current_user.get('id')))
        conn.commit()
        update_cursor.close()
        return jsonify({'message': 'Password updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


# ---------------- PATIENT SELF-LOOKUP ----------------
@app.route('/api/patients/me', methods=['GET'])
@token_required
@require_role('patient')
def get_my_patient_record():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT patient_record_id FROM Users WHERE id=%s", (g.current_user.get('id'),))
        row = cursor.fetchone()
        pid = row.get('patient_record_id') if row else None
        if not pid:
            return jsonify({'error': 'No patient record linked to this account'}), 404
        cursor.execute("SELECT * FROM Patient WHERE PatientID=%s", (pid,))
        patient = cursor.fetchone()
        if not patient:
            return jsonify({'error': 'Patient record not found'}), 404
        return jsonify(patient), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ---------------- PATIENT ROUTES ----------------
@app.route('/api/patients', methods=['POST'])
@token_required
@require_role('admin','receptionist')
def add_patient():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO Patient (PatientID, FirstName, LastName, DOB, Gender, Phone, Address, ProviderID)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get('PatientID'), data.get('FirstName'), data.get('LastName'), data.get('DOB'),
            data.get('Gender'), data.get('Phone'), data.get('Address'), data.get('ProviderID')
        ))
        conn.commit()
        return jsonify({"message": "Patient added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/patients', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor') # Added doctor so they can view patients
def get_patients():
    conn = get_db_connection()
    # Using a dictionary cursor (if supported by your DB driver) makes JSONifying much easier.
    # If you are using psycopg2, it's cursor_factory=RealDictCursor
    # If you are using mysql-connector, it's dictionary=True
    cursor = conn.cursor(dictionary=True) 
    try:
        cursor.execute("SELECT * FROM Patient")
        patients = cursor.fetchall()
        return jsonify(patients), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ---------------- DOCTOR ROUTES ----------------
@app.route('/api/doctors', methods=['POST'])
@token_required
@require_role('admin')
def add_doctor():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO Doctor (DoctorID, FirstName, LastName, Specialty, Phone, DepartmentID)
        VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            data.get('DoctorID'), data.get('FirstName'), data.get('LastName'),
            data.get('Specialty'), data.get('Phone'), data.get('DepartmentID')
        ))
        conn.commit()
        return jsonify({"message": "Doctor added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/doctors', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'patient')
def get_doctors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Doctor")
        doctors = cursor.fetchall()
        return jsonify(doctors), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ---------------- APPOINTMENT ROUTES ----------------
@app.route('/api/appointments', methods=['POST'])
@token_required
@require_role('admin','receptionist','doctor','patient')
def add_appointment():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Auto-generate AppointmentID if not supplied (patient portal never sends one)
        appt_id = data.get('AppointmentID') or None
        if not appt_id:
            cursor.execute("SELECT COALESCE(MAX(AppointmentID), 0) + 1 FROM Appointment")
            appt_id = cursor.fetchone()[0]
        cursor.execute("""
        INSERT INTO Appointment (AppointmentID, PatientID, DoctorID, NurseID, AppointmentDate, AppointmentTime, Status, Purpose)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            appt_id, data.get('PatientID'), data.get('DoctorID'), data.get('NurseID'),
            data.get('AppointmentDate'), data.get('AppointmentTime'), data.get('Status'), data.get('Purpose')
        ))
        conn.commit()
        return jsonify({"message": "Appointment added"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/appointments', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'patient')
def get_appointments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        user = getattr(g, 'current_user', {})
        if user.get('role') == 'patient':
            # Look up the patient's linked PatientID from the Users table
            pid_cursor = conn.cursor(dictionary=True)
            pid_cursor.execute('SELECT patient_record_id FROM Users WHERE id=%s', (user.get('id'),))
            pid_row = pid_cursor.fetchone()
            pid_cursor.close()
            pid = pid_row.get('patient_record_id') if pid_row else None
            if pid:
                cursor.execute('SELECT * FROM Appointment WHERE PatientID=%s', (pid,))
            else:
                cursor.execute('SELECT * FROM Appointment WHERE 1=0')  # no linked record
        else:
            cursor.execute("SELECT * FROM Appointment")
        appointments = cursor.fetchall()
        
        # FIX: Convert dates and times to strings so Flask can jsonify them
        for appt in appointments:
            if appt.get('AppointmentDate'):
                appt['AppointmentDate'] = str(appt['AppointmentDate'])
            if appt.get('AppointmentTime'):
                appt['AppointmentTime'] = str(appt['AppointmentTime'])

        return jsonify(appointments), 200
    except Exception as e:
        # Pro-tip: Print the error to your terminal so you can see exactly what failed!
        print(f"Appointment GET Error: {e}") 
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ---------------- HOSPITAL ADMIN ROUTES ----------------
@app.route('/api/admins', methods=['GET'])
@token_required
@require_role('admin')
def get_hospital_admins():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM HospitalAdmin")
    admins = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(admins)

@app.route('/api/admins', methods=['POST'])
@token_required
@require_role('admin')
def add_hospital_admin():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO HospitalAdmin (AdminID, FirstName, LastName, Email, Role)
        VALUES (%s,%s,%s,%s,%s)
        """, (data.get('AdminID'), data.get('FirstName'), data.get('LastName'),
              data.get('Email'), data.get('Role')))
        conn.commit()
        return jsonify({"message": "Hospital Admin added"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admins/<admin_id>', methods=['DELETE'])
@token_required
@require_role('admin')
def delete_hospital_admin(admin_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM HospitalAdmin WHERE AdminID=%s", (admin_id,))
        conn.commit()
        return jsonify({"message": "Hospital Admin deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# ---------------- STATIC FILES ----------------
@app.route('/', methods=['GET'])
def serve_index():
    # Serve index.html placed in the repository root
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/static/<path:filename>', methods=['GET'])
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ============================================================
# PATIENT  –  update + delete
# ============================================================

@app.route('/api/patients/<int:patient_id>', methods=['PUT'])
@token_required
@require_role('admin', 'receptionist')
def update_patient(patient_id):
    data = request.json or {}
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Patient
               SET FirstName=%s, LastName=%s, DOB=%s, Gender=%s,
                   Phone=%s, Address=%s, ProviderID=%s
             WHERE PatientID=%s
        """, (
            data.get('FirstName'), data.get('LastName'), data.get('DOB'),
            data.get('Gender'),    data.get('Phone'),    data.get('Address'),
            data.get('ProviderID'), patient_id
        ))
        conn.commit()
        return jsonify({'message': 'Patient updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/api/patients/<int:patient_id>', methods=['DELETE'])
@token_required
@require_role('admin', 'receptionist')
def delete_patient(patient_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Patient WHERE PatientID=%s", (patient_id,))
        conn.commit()
        return jsonify({'message': 'Patient deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


# ============================================================
# DOCTOR  –  update + delete
# ============================================================

@app.route('/api/doctors/<int:doctor_id>', methods=['PUT'])
@token_required
@require_role('admin')
def update_doctor(doctor_id):
    data = request.json or {}
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Doctor
               SET FirstName=%s, LastName=%s, Specialty=%s,
                   Phone=%s, DepartmentID=%s
             WHERE DoctorID=%s
        """, (
            data.get('FirstName'), data.get('LastName'), data.get('Specialty'),
            data.get('Phone'), data.get('DepartmentID'), doctor_id
        ))
        conn.commit()
        return jsonify({'message': 'Doctor updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/api/doctors/<int:doctor_id>', methods=['DELETE'])
@token_required
@require_role('admin')
def delete_doctor(doctor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Doctor WHERE DoctorID=%s", (doctor_id,))
        conn.commit()
        return jsonify({'message': 'Doctor deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


# ============================================================
# NURSE  –  GET
# ============================================================

@app.route('/api/nurses', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'nurse', 'patient')
def get_nurses():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Nurse")
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


# ============================================================
# APPOINTMENT  –  update + delete
# ============================================================

@app.route('/api/appointments/<int:appt_id>', methods=['PUT'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'patient')
def update_appointment(appt_id):
    data = request.json or {}
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Patients may only update Status (to cancel their own)
        if hasattr(g, 'current_user') and g.current_user.get('role') == 'patient':
            cursor.execute(
                "UPDATE Appointment SET Status=%s WHERE AppointmentID=%s",
                (data.get('Status'), appt_id)
            )
        else:
            cursor.execute("""
                UPDATE Appointment
                   SET PatientID=%s, DoctorID=%s, NurseID=%s,
                       AppointmentDate=%s, AppointmentTime=%s,
                       Status=%s, Purpose=%s
                 WHERE AppointmentID=%s
            """, (
                data.get('PatientID'),       data.get('DoctorID'),
                data.get('NurseID'),         data.get('AppointmentDate'),
                data.get('AppointmentTime'), data.get('Status'),
                data.get('Purpose'),         appt_id
            ))
        conn.commit()
        # Serialize dates/times for the response
        return jsonify({'message': 'Appointment updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/api/appointments/<int:appt_id>', methods=['DELETE'])
@token_required
@require_role('admin', 'receptionist', 'doctor')
def delete_appointment(appt_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Appointment WHERE AppointmentID=%s", (appt_id,))
        conn.commit()
        return jsonify({'message': 'Appointment deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    # Runs the server on localhost port 5000
    app.run(debug=True, port=5000)