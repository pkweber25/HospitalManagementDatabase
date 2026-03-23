import mysql.connector
import tkinter as tk
from tkinter import ttk, messagebox
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# ---------------- DATABASE CONNECTION ----------------
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
cursor = conn.cursor()

# ---------------- AUTO RESIZE ----------------
def auto_resize_columns(tree):
    for col in tree["columns"]:
        max_width = 100

        header_width = len(col) * 10
        if header_width > max_width:
            max_width = header_width

        for row in tree.get_children():
            cell_value = str(tree.set(row, col))
            cell_width = len(cell_value) * 10
            if cell_width > max_width:
                max_width = cell_width

        tree.column(col, width=max(max_width, 120))


# ---------------- ROOT ----------------
root = tk.Tk()
root.title("Hospital Management System")
root.geometry("1400x800")

tab_control = ttk.Notebook(root)

# =====================================================
# ================= PATIENT TAB ========================
# =====================================================
patient_tab = ttk.Frame(tab_control)
tab_control.add(patient_tab, text="Patient")

def insert_patient():
    try:
        cursor.execute("""
        INSERT INTO Patient VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            p_id.get(), p_fn.get(), p_ln.get(), p_dob.get(),
            p_gender.get(), p_phone.get(), p_addr.get(), p_ins.get()
        ))
        conn.commit()
        show_patients()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def update_patient():
    cursor.execute("""
    UPDATE Patient SET FirstName=%s, LastName=%s, DOB=%s, Gender=%s,
    Phone=%s, Address=%s, InsuranceProvider=%s WHERE PatientID=%s
    """, (
        p_fn.get(), p_ln.get(), p_dob.get(), p_gender.get(),
        p_phone.get(), p_addr.get(), p_ins.get(), p_id.get()
    ))
    conn.commit()
    show_patients()

def delete_patient():
    cursor.execute("DELETE FROM Patient WHERE PatientID=%s", (p_id.get(),))
    conn.commit()
    show_patients()

def clear_patient():
    for entry in [p_id,p_fn,p_ln,p_dob,p_gender,p_phone,p_addr,p_ins]:
        entry.delete(0, tk.END)

def show_patients():
    for row in patient_table.get_children():
        patient_table.delete(row)

    cursor.execute("SELECT * FROM Patient")
    for row in cursor.fetchall():
        patient_table.insert("", "end", values=row)

    auto_resize_columns(patient_table)

labels = ["ID","First","Last","DOB","Gender","Phone","Address","Insurance"]
entries = []

for i,text in enumerate(labels):
    tk.Label(patient_tab,text=text).grid(row=i,column=0,padx=5,pady=5)
    e = tk.Entry(patient_tab)
    e.grid(row=i,column=1,padx=5,pady=5)
    entries.append(e)

p_id,p_fn,p_ln,p_dob,p_gender,p_phone,p_addr,p_ins = entries

tk.Button(patient_tab,text="Insert",command=insert_patient).grid(row=0,column=2)
tk.Button(patient_tab,text="Update",command=update_patient).grid(row=1,column=2)
tk.Button(patient_tab,text="Delete",command=delete_patient).grid(row=2,column=2)
tk.Button(patient_tab,text="Clear",command=clear_patient).grid(row=3,column=2)

# TABLE + SCROLL
frame_p = tk.Frame(patient_tab)
frame_p.grid(row=10,column=0,columnspan=4)

scroll_x_p = tk.Scrollbar(frame_p, orient="horizontal")
scroll_y_p = tk.Scrollbar(frame_p, orient="vertical")

patient_table = ttk.Treeview(frame_p, columns=labels, show="headings",
                             xscrollcommand=scroll_x_p.set,
                             yscrollcommand=scroll_y_p.set)

scroll_x_p.config(command=patient_table.xview)
scroll_y_p.config(command=patient_table.yview)

scroll_x_p.pack(side="bottom", fill="x")
scroll_y_p.pack(side="right", fill="y")
patient_table.pack(fill="both", expand=True)

for col in labels:
    patient_table.heading(col,text=col)

show_patients()

# =====================================================
# ================= DOCTOR TAB =========================
# =====================================================
doctor_tab = ttk.Frame(tab_control)
tab_control.add(doctor_tab, text="Doctor")

def insert_doctor():
    cursor.execute("INSERT INTO Doctor VALUES (%s,%s,%s,%s,%s,%s)",
                   (d_id.get(),d_fn.get(),d_ln.get(),d_spec.get(),d_phone.get(),d_dept.get()))
    conn.commit()
    show_doctors()

def update_doctor():
    cursor.execute("""
    UPDATE Doctor SET FirstName=%s,LastName=%s,Specialty=%s,Phone=%s,Department=%s
    WHERE DoctorID=%s
    """,(d_fn.get(),d_ln.get(),d_spec.get(),d_phone.get(),d_dept.get(),d_id.get()))
    conn.commit()
    show_doctors()

def delete_doctor():
    cursor.execute("DELETE FROM Doctor WHERE DoctorID=%s",(d_id.get(),))
    conn.commit()
    show_doctors()

def clear_doctor():
    for entry in [d_id,d_fn,d_ln,d_spec,d_phone,d_dept]:
        entry.delete(0, tk.END)

def show_doctors():
    for row in doctor_table.get_children():
        doctor_table.delete(row)

    cursor.execute("SELECT * FROM Doctor")
    for row in cursor.fetchall():
        doctor_table.insert("", "end", values=row)

    auto_resize_columns(doctor_table)

labels_d = ["ID","First","Last","Specialty","Phone","Dept"]
entries_d = []

for i,text in enumerate(labels_d):
    tk.Label(doctor_tab,text=text).grid(row=i,column=0,padx=5,pady=5)
    e = tk.Entry(doctor_tab)
    e.grid(row=i,column=1,padx=5,pady=5)
    entries_d.append(e)

d_id,d_fn,d_ln,d_spec,d_phone,d_dept = entries_d

tk.Button(doctor_tab,text="Insert",command=insert_doctor).grid(row=0,column=2)
tk.Button(doctor_tab,text="Update",command=update_doctor).grid(row=1,column=2)
tk.Button(doctor_tab,text="Delete",command=delete_doctor).grid(row=2,column=2)
tk.Button(doctor_tab,text="Clear",command=clear_doctor).grid(row=3,column=2)

# TABLE + SCROLL
frame_d = tk.Frame(doctor_tab)
frame_d.grid(row=10,column=0,columnspan=4)

scroll_x_d = tk.Scrollbar(frame_d, orient="horizontal")
scroll_y_d = tk.Scrollbar(frame_d, orient="vertical")

doctor_table = ttk.Treeview(frame_d, columns=labels_d, show="headings",
                            xscrollcommand=scroll_x_d.set,
                            yscrollcommand=scroll_y_d.set)

scroll_x_d.config(command=doctor_table.xview)
scroll_y_d.config(command=doctor_table.yview)

scroll_x_d.pack(side="bottom", fill="x")
scroll_y_d.pack(side="right", fill="y")
doctor_table.pack(fill="both", expand=True)

for col in labels_d:
    doctor_table.heading(col,text=col)

show_doctors()

# =====================================================
# ================= APPOINTMENT TAB ====================
# =====================================================
appt_tab = ttk.Frame(tab_control)
tab_control.add(appt_tab, text="Appointment")

def insert_appt():
    cursor.execute("""
    INSERT INTO Appointment VALUES (%s,%s,%s,%s,%s,%s,%s)
    """,(a_id.get(),a_pid.get(),a_did.get(),a_date.get(),a_time.get(),a_status.get(),a_purpose.get()))
    conn.commit()
    show_appts()

def update_appt():
    cursor.execute("""
    UPDATE Appointment SET PatientID=%s,DoctorID=%s,AppointmentDate=%s,
    AppointmentTime=%s,Status=%s,Purpose=%s WHERE AppointmentID=%s
    """,(a_pid.get(),a_did.get(),a_date.get(),a_time.get(),a_status.get(),a_purpose.get(),a_id.get()))
    conn.commit()
    show_appts()

def delete_appt():
    cursor.execute("DELETE FROM Appointment WHERE AppointmentID=%s",(a_id.get(),))
    conn.commit()
    show_appts()

def clear_appt():
    for entry in [a_id,a_pid,a_did,a_date,a_time,a_status,a_purpose]:
        entry.delete(0, tk.END)

def show_appts():
    for row in appt_table.get_children():
        appt_table.delete(row)

    cursor.execute("SELECT * FROM Appointment")
    for row in cursor.fetchall():
        appt_table.insert("", "end", values=row)

    auto_resize_columns(appt_table)

labels_a = ["ID","PatientID","DoctorID","Date","Time","Status","Purpose"]
entries_a = []

for i,text in enumerate(labels_a):
    tk.Label(appt_tab,text=text).grid(row=i,column=0,padx=5,pady=5)
    e = tk.Entry(appt_tab)
    e.grid(row=i,column=1,padx=5,pady=5)
    entries_a.append(e)

a_id,a_pid,a_did,a_date,a_time,a_status,a_purpose = entries_a

tk.Button(appt_tab,text="Insert",command=insert_appt).grid(row=0,column=2)
tk.Button(appt_tab,text="Update",command=update_appt).grid(row=1,column=2)
tk.Button(appt_tab,text="Delete",command=delete_appt).grid(row=2,column=2)
tk.Button(appt_tab,text="Clear",command=clear_appt).grid(row=3,column=2)

# TABLE + SCROLL
frame_a = tk.Frame(appt_tab)
frame_a.grid(row=10,column=0,columnspan=4)

scroll_x_a = tk.Scrollbar(frame_a, orient="horizontal")
scroll_y_a = tk.Scrollbar(frame_a, orient="vertical")

appt_table = ttk.Treeview(frame_a, columns=labels_a, show="headings",
                          xscrollcommand=scroll_x_a.set,
                          yscrollcommand=scroll_y_a.set)

scroll_x_a.config(command=appt_table.xview)
scroll_y_a.config(command=appt_table.yview)

scroll_x_a.pack(side="bottom", fill="x")
scroll_y_a.pack(side="right", fill="y")
appt_table.pack(fill="both", expand=True)

for col in labels_a:
    appt_table.heading(col,text=col)

show_appts()

# =====================================================
tab_control.pack(expand=1, fill="both")
root.mainloop()