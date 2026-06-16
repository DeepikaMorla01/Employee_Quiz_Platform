"""
Run this once to fix the admin account and add sample quizzes.
Place this file in the Backend/ folder and run: python fix_setup.py
"""

import sqlite3, hashlib, json, os

DB = "workeval.db"

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ── Create tables if not exist ──────────────────────────────────────────────
with get_db() as db:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department TEXT,
        role TEXT DEFAULT 'employee'
    );
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_index INTEGER NOT NULL,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    );
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        quiz_id INTEGER NOT NULL,
        score REAL NOT NULL,
        accuracy REAL NOT NULL,
        time_taken REAL NOT NULL,
        attempt_number INTEGER DEFAULT 1,
        performance_label TEXT,
        feedback TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    );
    """)
    db.commit()

# ── Migrate existing DB ──────────────────────────────────────────────────────
with get_db() as db:
    try:
        db.execute("ALTER TABLE results ADD COLUMN correct_count INTEGER DEFAULT 0")
        db.commit()
        print("✅ Added correct_count column")
    except: pass
    try:
        db.execute("ALTER TABLE results ADD COLUMN total_questions INTEGER DEFAULT 0")
        db.commit()
        print("✅ Added total_questions column")
    except: pass

# ── Delete old admin and re-insert cleanly ───────────────────────────────────
with get_db() as db:
    db.execute("DELETE FROM users WHERE email='admin@workeval.com'")
    db.execute(
        "INSERT INTO users (name, email, password, role, department) VALUES (?,?,?,?,?)",
        ("Admin", "admin@workeval.com", hash_pw("admin123"), "admin", "HR")
    )
    db.commit()
    print("✅ Admin account created: admin@workeval.com / admin123")

# ── Seed sample quizzes ──────────────────────────────────────────────────────
sample_quizzes = [
    {
        "title": "General Knowledge",
        "description": "Basic GK questions for all employees",
        "questions": [
            {"q": "What is the capital of India?", "opts": ["Mumbai", "Delhi", "Kolkata", "Chennai"], "ans": 1},
            {"q": "How many days are in a leap year?", "opts": ["365", "366", "364", "367"], "ans": 1},
            {"q": "Which planet is closest to the Sun?", "opts": ["Venus", "Earth", "Mercury", "Mars"], "ans": 2},
            {"q": "What does CPU stand for?", "opts": ["Central Processing Unit", "Computer Personal Unit", "Central Program Utility", "Core Processing Unit"], "ans": 0},
            {"q": "How many continents are there on Earth?", "opts": ["5", "6", "7", "8"], "ans": 2},
        ]
    },
    {
        "title": "Python Basics",
        "description": "Fundamental Python programming questions",
        "questions": [
            {"q": "Which keyword is used to define a function in Python?", "opts": ["func", "def", "function", "define"], "ans": 1},
            {"q": "What is the output of: print(type([]))?", "opts": ["<class 'tuple'>", "<class 'dict'>", "<class 'list'>", "<class 'set'>"], "ans": 2},
            {"q": "Which of these is used to add an item to a list?", "opts": [".add()", ".insert()", ".append()", ".push()"], "ans": 2},
            {"q": "What does 'len()' do in Python?", "opts": ["Deletes items", "Returns length", "Loops through list", "Converts to string"], "ans": 1},
            {"q": "How do you start a comment in Python?", "opts": ["//", "/*", "#", "--"], "ans": 2},
        ]
    },
    {
        "title": "Workplace & HR Policy",
        "description": "Company policy and workplace conduct questions",
        "questions": [
            {"q": "What should you do if you witness workplace harassment?", "opts": ["Ignore it", "Join in", "Report it to HR", "Post about it online"], "ans": 2},
            {"q": "How many hours is a standard full-time work week?", "opts": ["30", "35", "40", "45"], "ans": 2},
            {"q": "What is the purpose of a performance review?", "opts": ["To fire employees", "To increase workload", "To evaluate and support growth", "To reduce salary"], "ans": 2},
            {"q": "Which of the following is considered professional behavior?", "opts": ["Missing deadlines often", "Meeting deadlines and communicating delays", "Ignoring emails", "Blaming teammates"], "ans": 1},
            {"q": "What does KPI stand for?", "opts": ["Key Personal Interest", "Key Performance Indicator", "Knowledge Process Integration", "Key Productivity Index"], "ans": 1},
        ]
    }
]

with get_db() as db:
    # check if quizzes already exist
    existing = db.execute("SELECT COUNT(*) as c FROM quizzes").fetchone()["c"]
    if existing > 0:
        print(f"ℹ️  {existing} quiz(es) already exist — skipping quiz seeding.")
    else:
        for quiz in sample_quizzes:
            cur = db.execute(
                "INSERT INTO quizzes (title, description) VALUES (?,?)",
                (quiz["title"], quiz["description"])
            )
            quiz_id = cur.lastrowid
            for q in quiz["questions"]:
                db.execute(
                    "INSERT INTO questions (quiz_id, question_text, options, correct_index) VALUES (?,?,?,?)",
                    (quiz_id, q["q"], json.dumps(q["opts"]), q["ans"])
                )
        db.commit()
        print(f"✅ {len(sample_quizzes)} sample quizzes added with 5 questions each.")

print("\n─────────────────────────────────────")
print("Everything is set up. Now run: python app.py")
print("─────────────────────────────────────")
print("Admin login → admin@workeval.com / admin123 (Role: Admin/HR)")
print("Register a new account for employee login.")