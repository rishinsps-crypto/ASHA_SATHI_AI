from datetime import date
from functools import wraps
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_db, seed_admin
import os

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "development-only-change-this-secret")
init_db()
seed_admin()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("worker_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access is required.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.before_request
def load_user():
    g.worker = None
    if session.get("worker_id"):
        db = get_db()
        g.worker = db.execute("SELECT * FROM asha_workers WHERE id=?", (session["worker_id"],)).fetchone()
        db.close()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        required = ["full_name", "worker_code", "mobile", "password", "state", "district", "block", "village", "phc"]
        if any(not f.get(k, "").strip() for k in required):
            flash("Please complete all required fields.", "error")
        elif len(f["password"]) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            db = get_db()
            try:
                db.execute("""INSERT INTO asha_workers
                    (full_name,worker_code,mobile,email,password_hash,state,district,block,village,phc,status,role)
                    VALUES (?,?,?,?,?,?,?,?,?,?, 'Pending','worker')""",
                    (f["full_name"].strip(), f["worker_code"].strip().upper(), f["mobile"].strip(),
                     f.get("email","").strip(), generate_password_hash(f["password"]),
                     f["state"].strip(), f["district"].strip(), f["block"].strip(),
                     f["village"].strip(), f["phc"].strip()))
                db.commit()
                flash("Registration submitted. An administrator must approve your account before login.", "success")
                return redirect(url_for("login"))
            except Exception:
                db.rollback()
                flash("Registration could not be saved. Check whether this Worker ID or mobile number is already registered.", "error")
            finally:
                db.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity","").strip()
        password = request.form.get("password","")
        db = get_db()
        worker = db.execute("SELECT * FROM asha_workers WHERE worker_code=? OR mobile=?", (identity.upper(), identity)).fetchone()
        db.close()
        if not worker or not check_password_hash(worker["password_hash"], password):
            flash("Incorrect Worker ID/mobile or password.", "error")
        elif worker["status"] != "Approved":
            flash("Your account is pending admin approval." if worker["status"] == "Pending" else "Your account is not active. Contact the administrator.", "error")
        else:
            session.clear()
            session["worker_id"] = worker["id"]
            session["role"] = worker["role"]
            session["worker_name"] = worker["full_name"]
            return redirect(url_for("admin_dashboard" if worker["role"] == "admin" else "dashboard"))
    return render_template("login.html")

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        db = get_db()
        worker = db.execute("SELECT * FROM asha_workers WHERE worker_code=? AND role='admin'", (username.upper(),)).fetchone()
        db.close()
        if worker and check_password_hash(worker["password_hash"], password):
            session.clear()
            session["worker_id"] = worker["id"]
            session["role"] = "admin"
            session["worker_name"] = worker["full_name"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("admin_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    pending = db.execute("SELECT * FROM asha_workers WHERE role='worker' AND status='Pending' ORDER BY id").fetchall()
    workers = db.execute("SELECT * FROM asha_workers WHERE role='worker' ORDER BY id DESC").fetchall()
    area_load = db.execute("""
        SELECT district, block, village, COUNT(*) AS request_count,
               SUM(CASE WHEN status='Open' THEN 1 ELSE 0 END) AS open_count
        FROM service_requests GROUP BY district, block, village
        ORDER BY open_count DESC, request_count DESC
    """).fetchall()
    all_requests = db.execute("""
        SELECT r.*, w.full_name, w.worker_code FROM service_requests r
        JOIN asha_workers w ON w.id=r.worker_id
        ORDER BY CASE r.priority WHEN 'Urgent' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, r.id DESC
    """).fetchall()
    db.close()
    return render_template("admin.html", pending=pending, workers=workers,
                           area_load=area_load, all_requests=all_requests)

@app.route("/admin/worker-status", methods=["POST"])
@admin_required
def worker_status():
    worker_id = request.form.get("worker_id")
    status = request.form.get("status")
    if status in ("Approved", "Rejected", "Suspended"):
        db = get_db()
        db.execute("UPDATE asha_workers SET status=? WHERE id=? AND role='worker'", (status, worker_id))
        db.commit()
        db.close()
        flash(f"Worker account marked {status.lower()}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/")
@login_required
def dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    wid = session["worker_id"]
    db = get_db()
    patients = db.execute("SELECT * FROM patients WHERE worker_id=? ORDER BY id DESC", (wid,)).fetchall()
    today = db.execute("""SELECT COUNT(*) n FROM visits v JOIN patients p ON p.id=v.patient_db_id
        WHERE p.worker_id=? AND v.visit_date=?""", (wid, date.today().isoformat())).fetchone()["n"]
    pending = db.execute("""SELECT COUNT(*) n FROM ehr_drafts d JOIN patients p ON p.id=d.patient_db_id
        WHERE p.worker_id=? AND d.status='Pending'""", (wid,)).fetchone()["n"]
    recent = db.execute("""SELECT v.*,p.patient_id,p.name FROM visits v JOIN patients p ON p.id=v.patient_db_id
        WHERE p.worker_id=? ORDER BY v.id DESC LIMIT 6""", (wid,)).fetchall()
    db.close()
    return render_template("dashboard.html", patients=patients, visits_today=today, pending=pending, recent_visits=recent)

@app.route("/patients", methods=["GET", "POST"])
@login_required
def patients():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    wid = session["worker_id"]
    if request.method == "POST":
        f = request.form
        try:
            db = get_db()
            db.execute("""INSERT INTO patients
                (patient_id,name,age,gender,village,contact,consent,worker_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (f["patient_id"].strip(), f["name"].strip(), int(f["age"]), f["gender"],
                 f["village"].strip(), f.get("contact","").strip(), f["consent"], wid))
            db.commit()
            flash("Patient registered successfully.", "success")
        except Exception:
            db.rollback()
            flash("Could not save patient. Check whether Patient ID already exists.", "error")
        finally:
            db.close()
        return redirect(url_for("patients"))
    db = get_db()
    rows = db.execute("SELECT * FROM patients WHERE worker_id=? ORDER BY id DESC", (wid,)).fetchall()
    db.close()
    return render_template("patients.html", patients=rows)

@app.route("/visits", methods=["GET", "POST"])
@login_required
def visits():
    wid = session["worker_id"]
    db = get_db()
    if request.method == "POST":
        try:
            owner = db.execute("SELECT id FROM patients WHERE id=? AND worker_id=?",
                               (request.form["patient_db_id"], wid)).fetchone()
            if not owner:
                flash("Selected patient is not assigned to your account.", "error")
            else:
                db.execute("""INSERT INTO visits
                    (visit_code,patient_db_id,visit_date,visit_type,symptoms,duration,notes)
                    VALUES (?,?,?,?,?,?,?)""",
                    ("VIS-"+uuid4().hex[:8].upper(), owner["id"], request.form["visit_date"],
                     request.form["visit_type"], request.form.get("symptoms",""),
                     request.form.get("duration",""), request.form.get("notes","")))
                db.commit()
                flash("Visit saved successfully.", "success")
        except Exception:
            db.rollback()
            flash("Visit could not be saved. Please check the details.", "error")
        finally:
            db.close()
        return redirect(url_for("visits"))
    people = db.execute("SELECT id,patient_id,name FROM patients WHERE worker_id=? ORDER BY name", (wid,)).fetchall()
    history = db.execute("""SELECT v.*,p.patient_id,p.name FROM visits v JOIN patients p ON p.id=v.patient_db_id
        WHERE p.worker_id=? ORDER BY v.id DESC""", (wid,)).fetchall()
    db.close()
    return render_template("visits.html", patients=people, visits=history)

@app.route("/studio", methods=["GET", "POST"])
@login_required
def studio():
    wid = session["worker_id"]
    db = get_db()
    if request.method == "POST":
        pid = request.form.get("patient_db_id")
        patient = db.execute("SELECT id,consent FROM patients WHERE id=? AND worker_id=?", (pid,wid)).fetchone()
        transcript = request.form.get("transcript","").strip()
        if not patient:
            flash("Patient not found in your records.", "error")
        elif patient["consent"] != "Granted":
            flash("Patient consent must be Granted before saving a draft.", "error")
        elif not transcript:
            flash("Please enter a transcript.", "error")
        else:
            db.execute("""INSERT INTO ehr_drafts (draft_code,patient_db_id,language,transcript,structured_text,status)
                VALUES (?,?,?,?,?,'Pending')""",
                ("DRAFT-"+uuid4().hex[:8].upper(), pid, request.form.get("language","Hindi"),
                 transcript, request.form.get("structured_text","").strip()))
            db.commit()
            flash("Draft saved for human review.", "success")
        db.close()
        return redirect(url_for("studio"))
    people = db.execute("SELECT id,patient_id,name FROM patients WHERE worker_id=? ORDER BY name", (wid,)).fetchall()
    db.close()
    return render_template("studio.html", patients=people)

@app.route("/reviews", methods=["GET", "POST"])
@login_required
def reviews():
    wid = session["worker_id"]
    db = get_db()
    if request.method == "POST":
        db.execute("""UPDATE ehr_drafts SET status=? WHERE id=? AND status='Pending'
            AND patient_db_id IN (SELECT id FROM patients WHERE worker_id=?)""",
            (request.form.get("status"), request.form.get("draft_id"), wid))
        db.commit()
        db.close()
        return redirect(url_for("reviews"))
    drafts = db.execute("""SELECT d.*,p.patient_id,p.name FROM ehr_drafts d JOIN patients p ON p.id=d.patient_db_id
        WHERE p.worker_id=? ORDER BY d.id DESC""", (wid,)).fetchall()
    db.close()
    return render_template("reviews.html", drafts=drafts)

@app.route("/history")
@login_required
def history():
    wid = session["worker_id"]
    db = get_db()
    people = db.execute("SELECT id,patient_id,name FROM patients WHERE worker_id=? ORDER BY name", (wid,)).fetchall()
    selected = request.args.get("patient_id","")
    rows = []
    if selected:
        rows = db.execute("""SELECT v.*,p.patient_id,p.name FROM visits v JOIN patients p ON p.id=v.patient_db_id
            WHERE p.id=? AND p.worker_id=? ORDER BY v.visit_date DESC""", (selected,wid)).fetchall()
    db.close()
    return render_template("history.html", patients=people, visits=rows, selected=selected)

@app.route("/reports")
@login_required
def reports():
    wid = session["worker_id"]
    db = get_db()
    patients = db.execute("SELECT * FROM patients WHERE worker_id=? ORDER BY id DESC", (wid,)).fetchall()
    visits = db.execute("""SELECT v.*,p.patient_id,p.name FROM visits v JOIN patients p ON p.id=v.patient_db_id
        WHERE p.worker_id=? ORDER BY v.id DESC""", (wid,)).fetchall()
    db.close()
    return render_template("reports.html", patients=patients, visits=visits)


@app.route("/requests", methods=["GET", "POST"])
@login_required
def service_requests():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    wid = session["worker_id"]
    db = get_db()
    if request.method == "POST":
        try:
            worker = db.execute("SELECT district,block,village FROM asha_workers WHERE id=?", (wid,)).fetchone()
            patient_id = request.form.get("patient_db_id") or None
            if patient_id:
                patient = db.execute("SELECT id FROM patients WHERE id=? AND worker_id=?", (patient_id,wid)).fetchone()
                if not patient:
                    raise ValueError("Patient is not assigned to your account.")
            db.execute("""INSERT INTO service_requests
                (request_code,worker_id,patient_db_id,request_type,priority,description,village,block,district)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                ("REQ-"+uuid4().hex[:8].upper(), wid, patient_id,
                 request.form["request_type"], request.form["priority"],
                 request.form["description"].strip(), worker["village"], worker["block"], worker["district"]))
            db.commit()
            flash("Area request submitted to the admin queue.", "success")
        except Exception as exc:
            db.rollback()
            flash(f"Request could not be saved: {exc}", "error")
        finally:
            db.close()
        return redirect(url_for("service_requests"))
    people = db.execute("SELECT id,patient_id,name FROM patients WHERE worker_id=? ORDER BY name", (wid,)).fetchall()
    rows = db.execute("SELECT * FROM service_requests WHERE worker_id=? ORDER BY id DESC", (wid,)).fetchall()
    db.close()
    return render_template("requests.html", patients=people, requests=rows)

@app.route("/admin/request-status", methods=["POST"])
@admin_required
def request_status():
    status = request.form.get("status")
    if status in ("Open", "In Progress", "Resolved"):
        db = get_db()
        db.execute("UPDATE service_requests SET status=? WHERE id=?", (status, request.form.get("request_id")))
        db.commit()
        db.close()
        flash("Request status updated.", "success")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
