from flask import Flask, request, jsonify, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
import os
import decimal
import secrets
import string

ALLOWED_ROLES = ['admin', 'doctor', 'receptionist', 'patient', 'nurse']

load_dotenv()

app = Flask(__name__, static_folder=None)
CORS(app)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
JWT_SECRET   = os.getenv("JWT_SECRET", "SECRET_KEY")
JWT_ALGO     = os.getenv("JWT_ALGO",   "HS256")


def dec(v):
    return float(v) if isinstance(v, decimal.Decimal) else v

def serialize_rows(rows):
    return [{k: dec(v) for k, v in row.items()} for row in rows]


# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def _safe_alter(conn, sql):
    """Run an ALTER TABLE; swallow duplicate-column errors silently."""
    c = conn.cursor()
    try:
        c.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()


def ensure_users_table():
    conn   = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id                INT          AUTO_INCREMENT PRIMARY KEY,
        username          VARCHAR(255) NOT NULL UNIQUE,
        password_hash     VARCHAR(255) NOT NULL,
        role              VARCHAR(50)  NOT NULL,
        full_name         VARCHAR(255),
        patient_record_id INT          NULL,
        linked_record_id  INT          NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    conn.commit()
    cursor.close()

    # Idempotent migrations for tables that existed before these columns
    _safe_alter(conn, "ALTER TABLE Users ADD COLUMN patient_record_id INT NULL")
    _safe_alter(conn, "ALTER TABLE Users ADD COLUMN linked_record_id INT NULL")
    _safe_alter(conn, "ALTER TABLE Appointment ADD COLUMN NurseID INT NULL")

    # Admin: always upsert so password is guaranteed correct after restart
    admin_username  = os.getenv('ADMIN_USERNAME',  'admin')
    admin_password  = os.getenv('ADMIN_PASSWORD',  'admin123')
    admin_full_name = os.getenv('ADMIN_FULL_NAME', 'System Administrator')
    if not admin_password:
        admin_password = ''.join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(12)
        )
        print(f"[startup] Generated admin password: {admin_password}")

    admin_hash = generate_password_hash(admin_password)
    ac = conn.cursor()
    try:
        ac.execute("""
            INSERT INTO Users (username, password_hash, role, full_name)
            VALUES (%s, %s, 'admin', %s)
            ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), role = 'admin'
        """, (admin_username, admin_hash, admin_full_name))
        conn.commit()
        print(f"[startup] Admin ready — username='{admin_username}' password='{admin_password}'")
    except Exception as e:
        print(f"[startup] Admin upsert error: {e}")
    finally:
        ac.close()

    # Default staff seeds (INSERT IGNORE — skip if username already exists)
    def seed_staff(username, password, role, full_name, linked_id):
        ph = generate_password_hash(password)
        sc = conn.cursor()
        try:
            sc.execute("""
                INSERT IGNORE INTO Users
                    (username, password_hash, role, full_name, linked_record_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, ph, role, full_name, linked_id))
            conn.commit()
            if sc.rowcount > 0:
                print(f"[startup] Seeded {role} — username='{username}' password='{password}'")
        except Exception as e:
            print(f"[startup] Seed {role} '{username}' error: {e}")
        finally:
            sc.close()

    # DoctorID 1 = Gregory House, NurseID 1 = Carla Espinosa (from sample data)
    seed_staff("doctor", "doctor123", "doctor", "Gregory House",  1)
    seed_staff("nurse",  "nurse123",  "nurse",  "Carla Espinosa", 1)

    conn.close()


try:
    print("Initialising Users table...")
    ensure_users_table()
    print("Users table ready.")
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: {e}")


# ══════════════════════════════════════════════════════════════
#  AUTH DECORATORS
# ══════════════════════════════════════════════════════════════
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token  = None
        header = request.headers.get('Authorization')
        if header and header.startswith('Bearer '):
            token = header.split(' ', 1)[1]
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            g.current_user = {
                'id':               payload.get('user_id'),
                'username':         payload.get('username'),
                'role':             payload.get('role'),
                'linked_record_id': payload.get('linked_record_id'),
            }
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Invalid token: ' + str(e)}), 401
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


# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/register', methods=['POST'])
def register():
    data      = request.json or {}
    username  = data.get('username') or data.get('Username')
    password  = data.get('password') or data.get('Password')
    full_name = data.get('full_name') or data.get('FullName') or None
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    role          = 'patient'
    password_hash = generate_password_hash(password)

    if full_name:
        parts      = full_name.strip().split(' ', 1)
        first_name = parts[0]
        last_name  = parts[1] if len(parts) > 1 else ''
    else:
        first_name = username
        last_name  = ''

    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Users (username, password_hash, role, full_name) VALUES (%s,%s,%s,%s)",
            (username, password_hash, role, full_name),
        )
        user_id = cursor.lastrowid

        cursor.execute("SELECT COALESCE(MAX(PatientID), 0) + 1 FROM Patient")
        new_pid = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO Patient (PatientID, FirstName, LastName) VALUES (%s, %s, %s)",
            (new_pid, first_name, last_name),
        )
        cursor.execute(
            "UPDATE Users SET patient_record_id=%s WHERE id=%s", (new_pid, user_id)
        )
        conn.commit()
        return jsonify({'message': 'User registered', 'role': role}), 201
    except Exception as e:
        conn.rollback()
        if any(k in str(e) for k in ('Duplicate', 'duplicate', '1062')):
            return jsonify({'error': 'Username already exists'}), 400
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data     = request.json or {}
    username = data.get('username') or data.get('Username')
    password = data.get('password') or data.get('Password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE username=%s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    # Resolve the record ID used for filtering (patient_record_id for patients, linked_record_id for staff)
    linked_id = user.get('linked_record_id') or user.get('patient_record_id')

    payload = {
        'user_id':          user['id'],
        'username':         user['username'],
        'role':             user['role'],
        'linked_record_id': linked_id,
        'exp':              datetime.utcnow() + timedelta(hours=8),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return jsonify({
        'token':            token,
        'role':             user['role'],
        'username':         user['username'],
        'linked_record_id': linked_id,
    })


# ══════════════════════════════════════════════════════════════
#  USER MANAGEMENT (admin)
# ══════════════════════════════════════════════════════════════
@app.route('/api/users', methods=['GET'])
@token_required
@require_role('admin')
def list_users():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, role, full_name, patient_record_id, linked_record_id FROM Users"
    )
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(users)


@app.route('/api/users', methods=['POST'])
@token_required
@require_role('admin')
def admin_create_user():
    """
    Create a system login. For doctor/nurse roles, also creates the
    Doctor/Nurse record and stores the link in linked_record_id.
    """
    data      = request.json or {}
    username  = data.get('username')
    password  = data.get('password')
    role      = data.get('role') or 'patient'
    full_name = data.get('full_name') or ''
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    if role not in ALLOWED_ROLES:
        return jsonify({'error': 'Invalid role'}), 400

    ph     = generate_password_hash(password)
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    linked_id = None

    try:
        if role == 'doctor':
            parts = full_name.strip().split(' ', 1)
            cursor.execute("SELECT COALESCE(MAX(DoctorID), 0) + 1 AS nid FROM Doctor")
            linked_id = cursor.fetchone()['nid']
            cursor.execute(
                "INSERT INTO Doctor (DoctorID, FirstName, LastName, Specialty, Phone, DepartmentID) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (linked_id, parts[0], parts[1] if len(parts) > 1 else '',
                 data.get('specialty', ''), data.get('phone', ''),
                 data.get('department_id') or None),
            )

        elif role == 'nurse':
            parts = full_name.strip().split(' ', 1)
            cursor.execute("SELECT COALESCE(MAX(NurseID), 0) + 1 AS nid FROM Nurse")
            linked_id = cursor.fetchone()['nid']
            cursor.execute(
                "INSERT INTO Nurse (NurseID, FirstName, LastName, Certification, Phone, DepartmentID) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (linked_id, parts[0], parts[1] if len(parts) > 1 else '',
                 data.get('certification', ''), data.get('phone', ''),
                 data.get('department_id') or None),
            )

        cursor.execute(
            "INSERT INTO Users (username, password_hash, role, full_name, linked_record_id) "
            "VALUES (%s,%s,%s,%s,%s)",
            (username, ph, role, full_name, linked_id),
        )
        conn.commit()
        return jsonify({'message': 'User created', 'linked_record_id': linked_id}), 201

    except Exception as e:
        conn.rollback()
        if any(k in str(e) for k in ('Duplicate', 'duplicate', '1062')):
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
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE Users SET password_hash=%s WHERE id=%s",
            (generate_password_hash(new_password), user_id)
        )
        conn.commit()
        return jsonify({'message': 'Password updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/users/<int:user_id>/role', methods=['PUT'])
@token_required
@require_role('admin')
def admin_change_user_role(user_id):
    data     = request.json or {}
    new_role = data.get('role')
    if not new_role or new_role not in ALLOWED_ROLES:
        return jsonify({'error': 'Invalid role'}), 400
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM Users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        return jsonify({'error': 'User not found'}), 404
    if user.get('role') == 'admin' and new_role != 'admin':
        cursor.execute("SELECT COUNT(*) as cnt FROM Users WHERE role='admin'")
        if cursor.fetchone().get('cnt', 0) <= 1:
            cursor.close(); conn.close()
            return jsonify({'error': 'Cannot remove role from last admin'}), 400
    try:
        uc = conn.cursor()
        uc.execute("UPDATE Users SET role=%s WHERE id=%s", (new_role, user_id))
        conn.commit()
        uc.close()
        return jsonify({'message': 'Role updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@token_required
@require_role('admin')
def admin_delete_user(user_id):
    if g.current_user and g.current_user.get('id') == user_id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM Users WHERE id=%s", (user_id,))
    target = cursor.fetchone()
    if not target:
        cursor.close(); conn.close()
        return jsonify({'error': 'User not found'}), 404
    if target.get('role') == 'admin':
        cursor.execute("SELECT COUNT(*) as cnt FROM Users WHERE role='admin'")
        if cursor.fetchone().get('cnt', 0) <= 1:
            cursor.close(); conn.close()
            return jsonify({'error': 'Cannot delete last admin'}), 400
    try:
        dc = conn.cursor()
        dc.execute("DELETE FROM Users WHERE id=%s", (user_id,))
        conn.commit()
        dc.close()
        return jsonify({'message': 'User deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/users/me', methods=['GET'])
@token_required
def get_my_profile():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, role, full_name, patient_record_id, linked_record_id FROM Users WHERE id=%s",
        (g.current_user.get('id'),),
    )
    user = cursor.fetchone()
    cursor.close(); conn.close()
    return jsonify(user or {})


@app.route('/api/users/me/password', methods=['PUT'])
@token_required
def change_own_password():
    data             = request.json or {}
    current_password = data.get('current_password')
    new_password     = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({'error': 'current_password and new_password required'}), 400
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE id=%s", (g.current_user.get('id'),))
    user = cursor.fetchone()
    if not user or not check_password_hash(user.get('password_hash', ''), current_password):
        cursor.close(); conn.close()
        return jsonify({'error': 'Invalid current password'}), 401
    try:
        uc = conn.cursor()
        uc.execute(
            "UPDATE Users SET password_hash=%s WHERE id=%s",
            (generate_password_hash(new_password), g.current_user.get('id'))
        )
        conn.commit()
        uc.close()
        return jsonify({'message': 'Password updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  PATIENT ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/patients/me', methods=['GET'])
@token_required
@require_role('patient')
def get_my_patient_record():
    """Return the Patient row linked to the current patient login."""
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT patient_record_id FROM Users WHERE id=%s", (g.current_user.get('id'),)
        )
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
        cursor.close(); conn.close()


@app.route('/api/patients', methods=['POST'])
@token_required
@require_role('admin', 'receptionist')
def add_patient():
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        patient_id = data.get('PatientID')
        if not patient_id:
            cursor.execute("SELECT COALESCE(MAX(PatientID), 0) + 1 AS nid FROM Patient")
            patient_id = cursor.fetchone()['nid']
        cursor.execute("""
            INSERT INTO Patient
                (PatientID, FirstName, LastName, DOB, Gender, Phone, Address, ProviderID)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            patient_id, data.get('FirstName'), data.get('LastName'), data.get('DOB'),
            data.get('Gender'), data.get('Phone'), data.get('Address'), data.get('ProviderID'),
        ))
        conn.commit()
        return jsonify({"message": "Patient added", "PatientID": patient_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/patients', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'nurse')
def get_patients():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Patient")
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/patients/<int:patient_id>', methods=['PUT'])
@token_required
@require_role('admin', 'receptionist')
def update_patient(patient_id):
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Patient
               SET FirstName=%s, LastName=%s, DOB=%s, Gender=%s,
                   Phone=%s, Address=%s, ProviderID=%s
             WHERE PatientID=%s
        """, (
            data.get('FirstName'), data.get('LastName'), data.get('DOB'),
            data.get('Gender'), data.get('Phone'), data.get('Address'),
            data.get('ProviderID'), patient_id,
        ))
        conn.commit()
        return jsonify({'message': 'Patient updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/patients/<int:patient_id>', methods=['DELETE'])
@token_required
@require_role('admin', 'receptionist')
def delete_patient(patient_id):
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Patient WHERE PatientID=%s", (patient_id,))
        conn.commit()
        return jsonify({'message': 'Patient deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  DOCTOR ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/doctors', methods=['POST'])
@token_required
@require_role('admin')
def add_doctor():
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        doctor_id = data.get('DoctorID')
        if not doctor_id:
            cursor.execute("SELECT COALESCE(MAX(DoctorID), 0) + 1 AS nid FROM Doctor")
            doctor_id = cursor.fetchone()['nid']
        cursor.execute("""
            INSERT INTO Doctor (DoctorID, FirstName, LastName, Specialty, Phone, DepartmentID)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            doctor_id, data.get('FirstName'), data.get('LastName'),
            data.get('Specialty'), data.get('Phone'), data.get('DepartmentID'),
        ))
        conn.commit()
        return jsonify({"message": "Doctor added", "DoctorID": doctor_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/doctors', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'nurse', 'patient')
def get_doctors():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Doctor")
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/doctors/<int:doctor_id>', methods=['PUT'])
@token_required
@require_role('admin')
def update_doctor(doctor_id):
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Doctor
               SET FirstName=%s, LastName=%s, Specialty=%s, Phone=%s, DepartmentID=%s
             WHERE DoctorID=%s
        """, (
            data.get('FirstName'), data.get('LastName'), data.get('Specialty'),
            data.get('Phone'), data.get('DepartmentID'), doctor_id,
        ))
        conn.commit()
        return jsonify({'message': 'Doctor updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/doctors/<int:doctor_id>', methods=['DELETE'])
@token_required
@require_role('admin')
def delete_doctor(doctor_id):
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Doctor WHERE DoctorID=%s", (doctor_id,))
        conn.commit()
        return jsonify({'message': 'Doctor deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  NURSE ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/nurses', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'nurse', 'patient')
def get_nurses():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Nurse")
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  APPOINTMENT ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/appointments', methods=['POST'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'patient')
def add_appointment():
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Always auto-generate to prevent collisions
        cursor.execute("SELECT COALESCE(MAX(AppointmentID), 0) + 1 AS nid FROM Appointment")
        appt_id = cursor.fetchone()['nid']

        user   = getattr(g, 'current_user', {})
        role   = user.get('role')
        status = data.get('Status', 'Scheduled')

        if role == 'patient':
            # Force PatientID from their own linked record; override status to Requested
            pc = conn.cursor(dictionary=True)
            pc.execute("SELECT patient_record_id FROM Users WHERE id=%s", (user.get('id'),))
            pr = pc.fetchone()
            pc.close()
            patient_id = pr.get('patient_record_id') if pr else None
            if not patient_id:
                return jsonify({'error': 'Patient record not found for this account'}), 400
            status = 'Requested'
        else:
            patient_id = data.get('PatientID')

        cursor.execute("""
            INSERT INTO Appointment
                (AppointmentID, PatientID, DoctorID, NurseID,
                 AppointmentDate, AppointmentTime, Status, Purpose)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            appt_id, patient_id,
            data.get('DoctorID'),        data.get('NurseID'),
            data.get('AppointmentDate'), data.get('AppointmentTime'),
            status,                      data.get('Purpose'),
        ))
        conn.commit()
        return jsonify({"message": "Appointment added", "AppointmentID": appt_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/appointments', methods=['GET'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'nurse', 'patient')
def get_appointments():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        user = getattr(g, 'current_user', {})
        role = user.get('role')
        lid  = user.get('linked_record_id')  # DoctorID or NurseID for staff

        if role == 'patient':
            # Re-read patient_record_id from DB to be safe
            pc = conn.cursor(dictionary=True)
            pc.execute("SELECT patient_record_id FROM Users WHERE id=%s", (user.get('id'),))
            pr = pc.fetchone()
            pc.close()
            pid = pr.get('patient_record_id') if pr else None
            if pid:
                cursor.execute(
                    "SELECT * FROM Appointment WHERE PatientID=%s "
                    "ORDER BY AppointmentDate DESC, AppointmentTime DESC", (pid,)
                )
            else:
                cursor.execute("SELECT * FROM Appointment WHERE 1=0")

        elif role == 'doctor' and lid:
            cursor.execute(
                "SELECT * FROM Appointment WHERE DoctorID=%s "
                "ORDER BY AppointmentDate DESC, AppointmentTime DESC", (lid,)
            )

        elif role == 'nurse' and lid:
            cursor.execute(
                "SELECT * FROM Appointment WHERE NurseID=%s "
                "ORDER BY AppointmentDate DESC, AppointmentTime DESC", (lid,)
            )

        else:
            cursor.execute(
                "SELECT * FROM Appointment ORDER BY AppointmentDate DESC, AppointmentTime DESC"
            )

        appointments = cursor.fetchall()
        for appt in appointments:
            if appt.get('AppointmentDate'):
                appt['AppointmentDate'] = str(appt['AppointmentDate'])
            if appt.get('AppointmentTime'):
                appt['AppointmentTime'] = str(appt['AppointmentTime'])
        return jsonify(appointments), 200
    except Exception as e:
        print(f"Appointment GET Error: {e}")
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/appointments/<int:appt_id>', methods=['PUT'])
@token_required
@require_role('admin', 'receptionist', 'doctor', 'patient')
def update_appointment(appt_id):
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        user = getattr(g, 'current_user', {})
        if user.get('role') == 'patient':
            cursor.execute(
                "UPDATE Appointment SET Status=%s WHERE AppointmentID=%s",
                (data.get('Status'), appt_id),
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
                data.get('Purpose'),         appt_id,
            ))
        conn.commit()
        return jsonify({'message': 'Appointment updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/appointments/<int:appt_id>', methods=['DELETE'])
@token_required
@require_role('admin', 'receptionist', 'doctor')
def delete_appointment(appt_id):
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Appointment WHERE AppointmentID=%s", (appt_id,))
        conn.commit()
        return jsonify({'message': 'Appointment deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  TREATMENT ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/treatments', methods=['GET'])
@token_required
@require_role('admin', 'doctor', 'receptionist', 'nurse')
def get_treatments():
    appt_id = request.args.get('appointment_id')
    conn    = get_db_connection()
    cursor  = conn.cursor(dictionary=True)
    try:
        if appt_id:
            cursor.execute("""
                SELECT t.*, d.DiagnosisName
                  FROM Treatment t
                  LEFT JOIN Diagnosis d ON d.DiagnosisID = t.DiagnosisID
                 WHERE t.AppointmentID = %s
            """, (appt_id,))
        else:
            cursor.execute("""
                SELECT t.*, d.DiagnosisName
                  FROM Treatment t
                  LEFT JOIN Diagnosis d ON d.DiagnosisID = t.DiagnosisID
            """)
        return jsonify(serialize_rows(cursor.fetchall())), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/treatments', methods=['POST'])
@token_required
@require_role('admin', 'doctor')
def add_treatment():
    data  = request.json or {}
    items = data if isinstance(data, list) else [data]
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        inserted_ids = []
        appt_ids     = set()
        for item in items:
            appt_id = item.get('AppointmentID')
            if not appt_id:
                return jsonify({'error': 'AppointmentID is required'}), 400
            cursor.execute("SELECT COALESCE(MAX(TreatmentID), 0) + 1 AS nid FROM Treatment")
            treat_id = cursor.fetchone()['nid']
            cursor.execute("""
                INSERT INTO Treatment
                    (TreatmentID, DiagnosisID, AppointmentID,
                     TreatmentName, Description, TreatmentCost)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                treat_id, item.get('DiagnosisID'), appt_id,
                item.get('TreatmentName'), item.get('Description'),
                item.get('TreatmentCost', 0.00),
            ))
            inserted_ids.append(treat_id)
            appt_ids.add(int(appt_id))
        conn.commit()
        for aid in appt_ids:
            cursor.callproc('generate_billing', [aid])
            conn.commit()
        return jsonify({'message': f'{len(inserted_ids)} treatment(s) added', 'TreatmentIDs': inserted_ids}), 201
    except Exception as e:
        print(f"Treatment POST Error: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/treatments/<int:treatment_id>', methods=['DELETE'])
@token_required
@require_role('admin', 'doctor')
def delete_treatment(treatment_id):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT AppointmentID FROM Treatment WHERE TreatmentID=%s", (treatment_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Treatment not found'}), 404
        appt_id = row['AppointmentID']
        cursor.execute("DELETE FROM Treatment WHERE TreatmentID=%s", (treatment_id,))
        conn.commit()
        cursor.callproc('generate_billing', [appt_id])
        conn.commit()
        return jsonify({'message': 'Treatment deleted and billing updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  BILLING ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/billing', methods=['GET'])
@token_required
def get_billing():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        user = getattr(g, 'current_user', {})
        if user.get('role') == 'patient':
            pc = conn.cursor(dictionary=True)
            pc.execute("SELECT patient_record_id FROM Users WHERE id=%s", (user.get('id'),))
            pr = pc.fetchone()
            pc.close()
            pid = pr.get('patient_record_id') if pr else None
            if pid:
                cursor.execute("""
                    SELECT b.*, p.FirstName, p.LastName
                      FROM BillingRecord b
                      JOIN Patient p ON p.PatientID = b.PatientID
                     WHERE b.PatientID = %s
                     ORDER BY b.BillingDate DESC
                """, (pid,))
            else:
                cursor.execute("SELECT * FROM BillingRecord WHERE 1=0")
        else:
            cursor.execute("""
                SELECT b.*, p.FirstName, p.LastName
                  FROM BillingRecord b
                  LEFT JOIN Patient p ON p.PatientID = b.PatientID
                 ORDER BY b.BillingDate DESC
            """)
        rows   = cursor.fetchall()
        result = []
        for row in rows:
            clean = {}
            for k, v in row.items():
                if isinstance(v, decimal.Decimal):
                    clean[k] = float(v)
                elif hasattr(v, 'isoformat'):
                    clean[k] = v.isoformat()
                else:
                    clean[k] = v
            result.append(clean)
        return jsonify(result), 200
    except Exception as e:
        print(f"Billing GET Error: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/billing/<int:billing_id>', methods=['PUT'])
@token_required
def update_billing(billing_id):
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM BillingRecord WHERE BillingID=%s", (billing_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({'error': 'Billing record not found'}), 404

        amount_paid    = data.get('AmountPaid')
        payment_method = data.get('PaymentMethod') or record.get('PaymentMethod')
        payment_status = data.get('PaymentStatus')

        if amount_paid is not None:
            amount_paid    = float(amount_paid)
            amount_owed    = float(record.get('AmountOwed', 0))
            payment_status = ('Paid' if amount_paid >= amount_owed
                              else ('Partial' if amount_paid > 0 else 'Unpaid'))
        else:
            amount_paid    = record.get('AmountPaid', 0)
            if payment_status is None:
                payment_status = record.get('PaymentStatus', 'Unpaid')

        uc = conn.cursor()
        uc.execute("""
            UPDATE BillingRecord
               SET AmountPaid=%s, PaymentStatus=%s, PaymentMethod=%s
             WHERE BillingID=%s
        """, (amount_paid, payment_status, payment_method, billing_id))
        conn.commit()
        uc.close()
        return jsonify({'message': 'Billing updated', 'PaymentStatus': payment_status, 'AmountPaid': amount_paid}), 200
    except Exception as e:
        print(f"Billing PUT Error: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/billing/regenerate/<int:appt_id>', methods=['POST'])
@token_required
@require_role('admin')
def regenerate_billing(appt_id):
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.callproc('generate_billing', [appt_id])
        conn.commit()
        return jsonify({'message': f'Billing regenerated for appointment {appt_id}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  HOSPITAL ADMIN ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/api/admins', methods=['GET'])
@token_required
@require_role('admin')
def get_hospital_admins():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM HospitalAdmin")
    admins = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(admins)


@app.route('/api/admins', methods=['POST'])
@token_required
@require_role('admin')
def add_hospital_admin():
    data   = request.json or {}
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        admin_id = data.get('AdminID')
        if not admin_id:
            cursor.execute("SELECT COALESCE(MAX(AdminID), 0) + 1 AS nid FROM HospitalAdmin")
            admin_id = cursor.fetchone()['nid']
        cursor.execute("""
            INSERT INTO HospitalAdmin (AdminID, FirstName, LastName, Email, Role)
            VALUES (%s,%s,%s,%s,%s)
        """, (admin_id, data.get('FirstName'), data.get('LastName'),
               data.get('Email'), data.get('Role')))
        conn.commit()
        return jsonify({"message": "Admin added", "AdminID": admin_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


@app.route('/api/admins/<admin_id>', methods=['DELETE'])
@token_required
@require_role('admin')
def delete_hospital_admin(admin_id):
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM HospitalAdmin WHERE AdminID=%s", (admin_id,))
        conn.commit()
        return jsonify({"message": "Admin deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  REPORTS
# ══════════════════════════════════════════════════════════════
@app.route('/api/reports', methods=['GET'])
@token_required
@require_role('admin')
def get_reports():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        reports = {}

        cursor.execute("""
            SELECT b.PaymentStatus,
                COUNT(*)                         AS TotalRecords,
                SUM(b.TotalCost)                 AS TotalBilled,
                SUM(b.InsuranceCoverage)         AS TotalCovered,
                SUM(b.AmountOwed)                AS TotalOwed,
                SUM(b.AmountPaid)                AS TotalCollected,
                SUM(b.AmountOwed - b.AmountPaid) AS OutstandingBalance,
                AVG(b.TotalCost)                 AS AvgCost,
                MIN(b.TotalCost)                 AS MinCost,
                MAX(b.TotalCost)                 AS MaxCost
            FROM BillingRecord b
            GROUP BY b.PaymentStatus
            ORDER BY TotalBilled DESC
        """)
        reports['billing_by_status'] = serialize_rows(cursor.fetchall())

        cursor.execute("""
            SELECT d.DepartmentName,
                COUNT(a.AppointmentID)                    AS TotalAppointments,
                SUM(a.Status = 'Completed')               AS Completed,
                SUM(a.Status IN ('Scheduled','Requested')) AS Scheduled,
                SUM(a.Status = 'Canceled')                AS Canceled,
                MIN(a.AppointmentDate)                    AS EarliestAppt,
                MAX(a.AppointmentDate)                    AS LatestAppt
            FROM Department d
            LEFT JOIN Doctor      doc ON doc.DepartmentID = d.DepartmentID
            LEFT JOIN Appointment a   ON a.DoctorID       = doc.DoctorID
            GROUP BY d.DepartmentID, d.DepartmentName
            ORDER BY TotalAppointments DESC
        """)
        reports['appointments_by_dept'] = serialize_rows(cursor.fetchall())

        cursor.execute("""
            SELECT dep.DepartmentName,
                COUNT(t.TreatmentID) AS TotalTreatments,
                SUM(t.TreatmentCost) AS TotalCost,
                AVG(t.TreatmentCost) AS AvgCost,
                MIN(t.TreatmentCost) AS MinCost,
                MAX(t.TreatmentCost) AS MaxCost
            FROM Treatment t
            JOIN Appointment a   ON a.AppointmentID = t.AppointmentID
            JOIN Doctor      doc ON doc.DoctorID    = a.DoctorID
            JOIN Department  dep ON dep.DepartmentID = doc.DepartmentID
            GROUP BY dep.DepartmentID, dep.DepartmentName
            ORDER BY TotalCost DESC
        """)
        reports['treatment_by_dept'] = serialize_rows(cursor.fetchall())

        cursor.execute("""
            SELECT CONCAT(doc.FirstName,' ',doc.LastName) AS DoctorName,
                doc.Specialty, dep.DepartmentName,
                COUNT(a.AppointmentID)          AS TotalAppointments,
                COALESCE(SUM(b.TotalCost),0)    AS TotalRevenue,
                COALESCE(AVG(b.TotalCost),0)    AS AvgRevenue,
                COALESCE(MIN(b.TotalCost),0)    AS MinBill,
                COALESCE(MAX(b.TotalCost),0)    AS MaxBill,
                MIN(a.AppointmentDate)          AS EarliestAppt,
                MAX(a.AppointmentDate)          AS LatestAppt
            FROM Doctor doc
            LEFT JOIN Department    dep ON dep.DepartmentID = doc.DepartmentID
            LEFT JOIN Appointment   a   ON a.DoctorID       = doc.DoctorID
            LEFT JOIN BillingRecord b   ON b.AppointmentID  = a.AppointmentID
            GROUP BY doc.DoctorID, doc.FirstName, doc.LastName, doc.Specialty, dep.DepartmentName
            ORDER BY TotalAppointments DESC
        """)
        reports['doctor_workload'] = serialize_rows(cursor.fetchall())

        cursor.execute("""
            SELECT ip.ProviderName, ip.CoveragePercent,
                COUNT(DISTINCT p.PatientID)           AS TotalPatients,
                COUNT(b.BillingID)                    AS TotalClaims,
                COALESCE(SUM(b.TotalCost),0)          AS TotalBilled,
                COALESCE(SUM(b.InsuranceCoverage),0)  AS TotalCovered,
                COALESCE(SUM(b.AmountOwed),0)         AS TotalPatientOwe,
                COALESCE(AVG(b.InsuranceCoverage),0)  AS AvgCoverage,
                COALESCE(MIN(b.InsuranceCoverage),0)  AS MinCoverage,
                COALESCE(MAX(b.InsuranceCoverage),0)  AS MaxCoverage
            FROM InsuranceProvider ip
            LEFT JOIN Patient       p ON p.ProviderID  = ip.ProviderID
            LEFT JOIN BillingRecord b ON b.PatientID   = p.PatientID
            GROUP BY ip.ProviderID, ip.ProviderName, ip.CoveragePercent
            ORDER BY TotalCovered DESC
        """)
        reports['insurance_analysis'] = serialize_rows(cursor.fetchall())

        cursor.execute("""
            SELECT COUNT(b.BillingID)            AS TotalBillings,
                SUM(b.TotalCost)                 AS TotalBilled,
                AVG(b.TotalCost)                 AS AvgBill,
                MIN(b.TotalCost)                 AS MinBill,
                MAX(b.TotalCost)                 AS MaxBill,
                SUM(b.InsuranceCoverage)         AS TotalInsuranceCoverage,
                SUM(b.AmountOwed)                AS TotalOwed,
                SUM(b.AmountPaid)                AS TotalCollected,
                SUM(b.AmountOwed - b.AmountPaid) AS OutstandingBalance
            FROM BillingRecord b
        """)
        reports['billing_summary'] = serialize_rows(cursor.fetchall())

        return jsonify(reports)
    except Exception as e:
        print(f"Reports Error: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()


# ══════════════════════════════════════════════════════════════
#  STATIC FILES
# ══════════════════════════════════════════════════════════════
@app.route('/', methods=['GET'])
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/static/<path:filename>', methods=['GET'])
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == '__main__':
    app.run(debug=True, port=5000)