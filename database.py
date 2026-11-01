import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash
from config import ADMIN_USERNAME, ADMIN_PASSWORD

DB_PATH = Path(__file__).resolve().parent / "data" / "asha_sathi.db"
DB_PATH.parent.mkdir(exist_ok=True)

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS asha_workers (
      id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
      worker_code TEXT NOT NULL UNIQUE, mobile TEXT NOT NULL UNIQUE,
      email TEXT, password_hash TEXT NOT NULL, state TEXT NOT NULL,
      district TEXT NOT NULL, block TEXT NOT NULL, village TEXT NOT NULL,
      phc TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
      role TEXT NOT NULL DEFAULT 'worker', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS patients (
      id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL, age INTEGER NOT NULL, gender TEXT NOT NULL,
      village TEXT NOT NULL, contact TEXT, consent TEXT NOT NULL DEFAULT 'Pending',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, worker_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS visits (
      id INTEGER PRIMARY KEY AUTOINCREMENT, visit_code TEXT NOT NULL UNIQUE,
      patient_db_id INTEGER NOT NULL, visit_date TEXT NOT NULL, visit_type TEXT NOT NULL,
      symptoms TEXT, duration TEXT, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(patient_db_id) REFERENCES patients(id)
    );
    CREATE TABLE IF NOT EXISTS ehr_drafts (
      id INTEGER PRIMARY KEY AUTOINCREMENT, draft_code TEXT NOT NULL UNIQUE,
      patient_db_id INTEGER NOT NULL, language TEXT NOT NULL, transcript TEXT NOT NULL,
      structured_text TEXT, status TEXT NOT NULL DEFAULT 'Pending',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(patient_db_id) REFERENCES patients(id)
    );
    CREATE TABLE IF NOT EXISTS service_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      request_code TEXT NOT NULL UNIQUE,
      worker_id INTEGER NOT NULL,
      patient_db_id INTEGER,
      request_type TEXT NOT NULL,
      priority TEXT NOT NULL DEFAULT 'Normal',
      description TEXT NOT NULL,
      village TEXT NOT NULL,
      block TEXT NOT NULL,
      district TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Open',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(worker_id) REFERENCES asha_workers(id),
      FOREIGN KEY(patient_db_id) REFERENCES patients(id)
    );
    """)
    # Safe additive migration for an older starter database.
    columns = {r["name"] for r in db.execute("PRAGMA table_info(patients)").fetchall()}
    if "worker_id" not in columns:
        db.execute("ALTER TABLE patients ADD COLUMN worker_id INTEGER")
    db.commit()
    db.close()

def seed_admin():
    db = get_db()
    existing = db.execute("SELECT id FROM asha_workers WHERE role='admin' LIMIT 1").fetchone()
    if not existing:
        db.execute("""INSERT INTO asha_workers
          (full_name,worker_code,mobile,email,password_hash,state,district,block,village,phc,status,role)
          VALUES (?,?,?,?,?,?,?,?,?,?, 'Approved','admin')""",
          ("System Administrator", ADMIN_USERNAME, "0000000000", "", generate_password_hash(ADMIN_PASSWORD),
           "Admin", "Admin", "Admin", "Admin", "Admin"))
        db.commit()
    db.close()
