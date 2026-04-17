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
JWT_SECRET = os.getenv("JWT_SECRET", "SECRET_KEY")
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
        full_name VARCHAR(255)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    conn.commit()
    # Seed a single admin if no users exist
    try:
        cursor.execute("SELECT COUNT(*) FROM Users")
        row = cursor.fetchone()
        count = 0
        if row:
            # cursor.fetchone() may return tuple
            if isinstance(row, tuple):
                count = row[0]
            elif isinstance(row, dict):
                # some libraries may return dict
                count = row.get('COUNT(*)', 0)
            else:
                try:
                    count = int(row)
                except Exception:
                    count = 0
        if count == 0:
            admin_username = os.getenv('ADMIN_USERNAME', 'admin')
            admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
            admin_full_name = os.getenv('ADMIN_FULL_NAME', 'System Administrator')
            generated = False
            if not admin_password:
                admin_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                generated = True
            password_hash = generate_password_hash(admin_password)
            try:
                cursor.execute("INSERT INTO Users (username,password_hash,role,full_name) VALUES (%s,%s,%s,%s)",
                               (admin_username, password_hash, 'admin', admin_full_name))
                conn.commit()
                if generated:
                    print(f"Seeded admin user: username='{admin_username}', password='{admin_password}'")
                else:
                    print(f"Seeded admin user: username='{admin_username}' (password from ADMIN_PASSWORD env)")
            except Exception as e:
                print('Failed to seed admin user:', e)
    except Exception as e:
        print('ensure_users_table: count check failed:', e)
    finally:
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
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Users (username,password_hash,role,full_name) VALUES (%s,%s,%s,%s)", (username, password_hash, role, full_name))
        conn.commit()
        return jsonify({'message': 'User registered', 'role': role}), 201
    except Exception as e:
        # handle duplicate username gracefully
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
@require_role('admin', 'receptionist', 'doctor')
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
@require_role('admin','receptionist','doctor')
def add_appointment():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO Appointment (AppointmentID, PatientID, DoctorID, NurseID, AppointmentDate, AppointmentTime, Status, Purpose)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get('AppointmentID'), data.get('PatientID'), data.get('DoctorID'), data.get('NurseID'),
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
@require_role('admin', 'receptionist', 'doctor')
def get_appointments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Appointment")
        appointments = cursor.fetchall()
        return jsonify(appointments), 200
    except Exception as e:
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

if __name__ == '__main__':
    # Runs the server on localhost port 5000
    app.run(debug=True, port=5000)