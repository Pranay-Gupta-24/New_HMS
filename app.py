from flask import Flask, render_template, request, redirect, session
from flask import flash
import sqlite3

app = Flask(__name__)
app.secret_key = "secret"

def get_db():
    return sqlite3.connect("hospital.db")

# Create tables
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT,
        role TEXT,
        doctor_id INTEGER,
        patient_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY,
        name TEXT,
        specialization TEXT,
        fees INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER,
        sex TEXT,
        address TEXT,
        phone TEXT,
        blood_group TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY,
        patient_id INTEGER,
        doctor_id INTEGER,
        date TEXT,
        time TEXT,
        status TEXT
    )
    """)

    # default admin
    cur.execute("INSERT OR IGNORE INTO users (id,username,password,role) VALUES (1,'admin','admin123','admin')")

    conn.commit()
    conn.close()

init_db()
def require_role(role):
    if "role" not in session or session["role"] != role:
        return False
    return True

@app.route("/", methods=["GET", "POST"])
def login():
    conn = get_db()
    cur = conn.cursor()

    # stats for UI
    cur.execute("SELECT COUNT(*) FROM patients")
    patients = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctors")
    doctors = cur.fetchone()[0]

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        # prevent crash if empty
        if not username or not password or not role:
            flash("All fields required", "error")
            return redirect("/")

        cur.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND role=?",
            (username, password, role)
        )
        user = cur.fetchone()

        if user:
            session.clear()
            session["username"] = user[1]   # FIXED
            session["role"] = user[3]       # FIXED

            # correct indexes
            if role == "doctor":
                session["doctor_id"] = user[4]
            elif role == "patient":
                session["patient_id"] = user[5]

            # redirect
            if role == "admin":
                return redirect("/dashboard")
            elif role == "doctor":
                return redirect("/doctor_dashboard")
            elif role == "patient":
                return redirect("/patient_dashboard")

        else:
            flash("Invalid credentials", "error")
            return redirect("/")

    return render_template("login.html", patients=patients, doctors=doctors)


# ================= GUEST =================
@app.route("/guest")
def guest():
    session.clear()
    session["role"] = "guest"
    session["username"] = "Guest"
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cur = conn.cursor()

    # counts
    cur.execute("SELECT COUNT(*) FROM patients")
    patients = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctors")
    doctors = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM appointments")
    appointments = cur.fetchone()[0]

    # specialization chart
    cur.execute("""
        SELECT specialization, COUNT(*) 
        FROM doctors 
        GROUP BY specialization
    """)
    data = cur.fetchall()

    spec_labels = [row[0] for row in data]
    spec_values = [row[1] for row in data]

    return render_template(
        "dashboard.html",
        patients=patients,
        doctors=doctors,
        appointments=appointments,
        spec_labels=spec_labels,   # ✅ REQUIRED
        spec_values=spec_values    # ✅ REQUIRED
    )

@app.route("/doctor_dashboard")
def doctor_dashboard():
    if session.get("role") != "doctor":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    # Get doctor name
    username = session["username"]
    # get doctor_id
    cur.execute("SELECT doctor_id FROM users WHERE username=?", (username,)) 
    doctor_id = cur.fetchone()[0]
    # appointments 
    cur.execute(""" SELECT a.id, p.name, a.date, a.status 
                FROM appointments a JOIN patients p ON a.patient_id = p.id WHERE a.doctor_id = ? 
                """, (doctor_id,)) 
    appts = cur.fetchall()

    # patients 
    cur.execute(""" SELECT DISTINCT p.name 
                FROM appointments a JOIN patients p ON a.patient_id = p.id WHERE a.doctor_id = ? 
                """, (doctor_id,)) 
    patients = cur.fetchall()

    return render_template("doctor_dashboard.html",
                           appts=appts,
                           patients=patients,
                           doctor=username)

@app.route("/mark_done/<int:id>", methods=["POST"])
def mark_done(id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE appointments SET status='Completed' WHERE id=?", (id,))
    conn.commit()

    return redirect("/doctor_dashboard")
    

    return redirect("/doctor_dashboard")

@app.route("/doctors", methods=["GET","POST"])
def doctors():
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        spec = request.form["spec"]
        fees = request.form["fees"]
        username = request.form["username"]
        password = request.form["password"]

        # ✅ CHECK INSIDE POST ONLY
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        if cur.fetchone():
            return "Username already exists"

        cur.execute("INSERT INTO doctors (name,specialization,fees) VALUES (?,?,?)",
                    (name,spec,fees))

        doctor_id = cur.lastrowid

        cur.execute("""
        INSERT INTO users (username,password,role,doctor_id)
        VALUES (?,?,?,?)
        """, (username,password,"doctor",doctor_id))

        conn.commit()

    # ✅ ALWAYS OUTSIDE POST
    cur.execute("SELECT * FROM doctors")
    data = cur.fetchall()

    return render_template("doctors.html", doctors=data)

@app.route("/doctor_profile", methods=["GET", "POST"])
def doctor_profile():
    if session.get("role") != "doctor":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    username = session["username"]

    # get doctor_id
    cur.execute("SELECT doctor_id FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row or not row[0]:
        return "Doctor not linked"

    doctor_id = row[0]

    if request.method == "POST":
        name = request.form["name"]
        spec = request.form["spec"]
        fees = request.form["fees"]

        cur.execute("""
            UPDATE doctors
            SET name=?, specialization=?, fees=?
            WHERE id=?
        """, (name, spec, fees, doctor_id))
          
        conn.commit()
        flash("Profile updated successfully!", "success")
        return redirect("/doctor_profile")

    # GET: load current data
    cur.execute("SELECT name, specialization, fees FROM doctors WHERE id=?", (doctor_id,))
    doctor = cur.fetchone()

    return render_template("doctor_profile.html", doctor=doctor)

@app.route("/delete_doctor/<int:id>")
def delete_doctor(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM doctors WHERE id=?", (id,))
    conn.commit()

    return redirect("/doctors")

@app.route("/patient_dashboard")
def patient_dashboard():
    if session.get("role") != "patient":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    username = session["username"]

    # get patient_id
    cur.execute("SELECT patient_id FROM users WHERE username=?", (username,))
    patient_id = cur.fetchone()[0]

    # appointments
    cur.execute("""
    SELECT d.name, a.date, a.status
    FROM appointments a
    JOIN doctors d ON a.doctor_id = d.id
    WHERE a.patient_id = ?
    """, (patient_id,))

    appts = cur.fetchall()

    return render_template("patient_dashboard.html",
                           appts=appts,
                           user=username)

@app.route("/patients", methods=["GET","POST"])
def patients():
    if not require_role("admin"):
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        age = request.form["age"]
        sex = request.form["sex"]
        address = request.form["address"]
        phone = request.form["phone"]
        blood = request.form["blood"]

        username = request.form["username"]
        password = request.form["password"]

        # check duplicate username
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        if cur.fetchone():
            return "Username exists"

        # insert patient
        cur.execute("""
        INSERT INTO patients (name,age,sex,address,phone,blood_group)
        VALUES (?,?,?,?,?,?)
        """, (name,age,sex,address,phone,blood))

        patient_id = cur.lastrowid

        # create login
        cur.execute("""
        INSERT INTO users (username,password,role,patient_id)
        VALUES (?,?,?,?)
        """, (username,password,"patient",patient_id))

        conn.commit()

        return redirect("/patients")   # ✅ VERY IMPORTANT

    # GET request
    cur.execute("SELECT * FROM patients")
    data = cur.fetchall()

    return render_template("patients.html", patients=data)
@app.route("/patient_profile", methods=["GET","POST"])
def patient_profile():
    if session.get("role") != "patient":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    username = session["username"]

    cur.execute("SELECT patient_id FROM users WHERE username=?", (username,))
    patient_id = cur.fetchone()[0]

    if request.method == "POST":
        name = request.form["name"]
        age = request.form["age"]
        sex = request.form["sex"]
        address = request.form["address"]
        phone = request.form["phone"]
        blood = request.form["blood"]

        cur.execute("""
        UPDATE patients
        SET name=?, age=?, sex=?, address=?, phone=?, blood_group=?
        WHERE id=?
        """, (name,age,sex,address,phone,blood,patient_id))

        conn.commit()
        flash("Profile updated successfully!", "success")
        return redirect("/patient_profile")

    cur.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    patient = cur.fetchone()

    return render_template("patient_profile.html", patient=patient)

@app.route("/edit_doctor/<int:id>", methods=["GET", "POST"])
def edit_doctor(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    # UPDATE
    if request.method == "POST":
        name = request.form["name"]
        spec = request.form["spec"]
        fees = request.form["fees"]

        cur.execute("""
            UPDATE doctors
            SET name=?, specialization=?, fees=?
            WHERE id=?
        """, (name, spec, fees, id))

        conn.commit()
        return redirect("/doctors")

    # GET existing data
    cur.execute("SELECT * FROM doctors WHERE id=?", (id,))
    doctor = cur.fetchone()

    return render_template("edit_doctor.html", doctor=doctor)

@app.route("/edit_patient/<int:id>", methods=["GET", "POST"])
def edit_patient(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        age = request.form["age"]
        sex = request.form["sex"]
        address = request.form["address"]
        phone = request.form["phone"]
        blood = request.form["blood"]

        cur.execute("""
            UPDATE patients
            SET name=?, age=?, sex=?, address=?, phone=?, blood_group=?
            WHERE id=?
        """, (name, age, sex, address, phone, blood, id))

        conn.commit()
        return redirect("/patients")

    cur.execute("SELECT * FROM patients WHERE id=?", (id,))
    patient = cur.fetchone()

    return render_template("edit_patient.html", patient=patient)

@app.route("/delete_patient/<int:id>")
def delete_patient(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM patients WHERE id=?", (id,))
    conn.commit()

    return redirect("/patients")


@app.route("/appointments", methods=["GET","POST"])
def appointments():
    if "role" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    # Fetch doctors and patients for dropdown
    cur.execute("SELECT id, name, fees FROM doctors")
    doctors = cur.fetchall()

    cur.execute("SELECT id, name FROM patients")
    patients = cur.fetchall()

    if request.method == "POST":
     patient_id = request.form["patient"]
     doctor_id = request.form["doctor"]
     date = request.form["date"]
     time = request.form["time"]
     status = request.form["status"]

     cur.execute("""
        INSERT INTO appointments (patient_id, doctor_id, date,time, status)
        VALUES (?, ?,?, ?, ?)""", (patient_id, doctor_id, date,time, status))

     conn.commit()

    # JOIN (IMPORTANT) 
    cur.execute(""" SELECT a.id, p.name, d.name, a.date,a.time, a.status 
                FROM appointments a 
                JOIN patients p ON a.patient_id = p.id 
                JOIN doctors d ON a.doctor_id = d.id 
                """)
    appts = cur.fetchall()

    return render_template("appointments.html",
                           appts=appts,
                           doctors=doctors,
                           patients=patients)

@app.route("/edit_appointment/<int:id>", methods=["GET", "POST"])
def edit_appointment(id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        date = request.form["date"]
        time = request.form["time"]
        status = request.form["status"]

        cur.execute("""
            UPDATE appointments
            SET date=?,time=?, status=?
            WHERE id=?
        """, (date,time,status, id))

        conn.commit()
        return redirect("/appointments")

    cur.execute("SELECT * FROM appointments WHERE id=?", (id,))
    appointment = cur.fetchone()

    return render_template("edit_appointment.html", appointment=appointment)
@app.route("/delete_appointment/<int:id>")
def delete_appointment(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM appointments WHERE id=?", (id,))
    conn.commit()

    return redirect("/appointments")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

app.run(debug=True)