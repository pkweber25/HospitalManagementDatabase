from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app) # Allows local HTML file to fetch data from this API

# ---------------- DATABASE CONNECTION ----------------
def get_db_connection():
    # open a fresh connection per request in a web app
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# =====================================================
# ================= PATIENT ROUTES ====================
# =====================================================

# From old show_patients()
@app.route('/api/patients', methods=['GET'])
def get_patients():
    conn = get_db_connection()
    # dictionary=True makes it easy to convert the rows to JSON
    cursor = conn.cursor(dictionary=True) 
    cursor.execute("SELECT * FROM Patient")
    patients = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return jsonify(patients)

# From old insert_patient()
@app.route('/api/patients', methods=['POST'])
def add_patient():
    data = request.json # Get the data sent from the web frontend
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        INSERT INTO Patient VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data['PatientID'], data['FirstName'], data['LastName'], data['DOB'],
            data['Gender'], data['Phone'], data['Address'], data['InsuranceProvider']
        ))
        conn.commit()
        return jsonify({"message": "Patient added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

# add similar routes for DELETE and PUT (Update) here

if __name__ == '__main__':
    # Runs the server on localhost port 5000
    app.run(debug=True, port=5000)