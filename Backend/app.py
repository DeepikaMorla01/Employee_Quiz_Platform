from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import hashlib, jwt, os, datetime, json
from functools import wraps
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = Flask(__name__)
CORS(app, origins=[
    "https://deepikamorla01.github.io",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "null"
], supports_credentials=True)

SECRET = os.environ.get("JWT_SECRET_KEY", "workeval_secret_key_2024")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
# Render gives postgres:// but psycopg2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ─── DB ABSTRACTION ───────────────────────────────────────────────────────────
# Supports PostgreSQL (Render) and SQLite (local) transparently.

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    def get_db():
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn

    def ph(n=1):
        """Return %s placeholders for postgres."""
        return ",".join(["%s"] * n)

    Q = "%s"   # query placeholder
else:
    import sqlite3

    DB = os.environ.get("DB_NAME", "workeval.db")

    def get_db():
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        return conn

    Q = "?"    # query placeholder


def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]


# ─── DB INIT ──────────────────────────────────────────────────────────────────

def init_db():
    conn = get_db()
    cur = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            department TEXT,
            role TEXT DEFAULT 'employee'
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
            question_text TEXT NOT NULL,
            options TEXT NOT NULL,
            correct_index INTEGER NOT NULL
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
            score REAL NOT NULL,
            accuracy REAL NOT NULL,
            time_taken REAL NOT NULL,
            attempt_number INTEGER DEFAULT 1,
            correct_count INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            performance_label TEXT,
            feedback TEXT,
            user_answers TEXT DEFAULT '{}',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # seed admin
        admin_pw    = hashlib.sha256(os.environ.get("ADMIN_PASSWORD","admin123").encode()).hexdigest()
        admin_email = os.environ.get("ADMIN_EMAIL","admin@workeval.com")
        admin_name  = os.environ.get("ADMIN_NAME","Admin")
        admin_dept  = os.environ.get("ADMIN_DEPARTMENT","HR")
        cur.execute("""
            INSERT INTO users (name, email, password, role, department)
            VALUES (%s,%s,%s,'admin',%s)
            ON CONFLICT (email) DO NOTHING
        """, (admin_name, admin_email, admin_pw, admin_dept))

    else:
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, department TEXT, role TEXT DEFAULT 'employee'
        );
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL, question_text TEXT NOT NULL,
            options TEXT NOT NULL, correct_index INTEGER NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, quiz_id INTEGER NOT NULL,
            score REAL NOT NULL, accuracy REAL NOT NULL, time_taken REAL NOT NULL,
            attempt_number INTEGER DEFAULT 1, correct_count INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0, performance_label TEXT, feedback TEXT,
            user_answers TEXT DEFAULT '{}',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );
        """)
        for col in ["correct_count INTEGER DEFAULT 0",
                    "total_questions INTEGER DEFAULT 0",
                    "user_answers TEXT DEFAULT '{}'"]:
            try: cur.execute(f"ALTER TABLE results ADD COLUMN {col}")
            except: pass

        admin_pw    = hashlib.sha256(os.environ.get("ADMIN_PASSWORD","admin123").encode()).hexdigest()
        admin_email = os.environ.get("ADMIN_EMAIL","admin@workeval.com")
        admin_name  = os.environ.get("ADMIN_NAME","Admin")
        admin_dept  = os.environ.get("ADMIN_DEPARTMENT","HR")
        cur.execute("INSERT OR IGNORE INTO users (name,email,password,role,department) VALUES (?,?,?,'admin',?)",
                    (admin_name, admin_email, admin_pw, admin_dept))

    conn.commit()
    conn.close()

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def make_token(user_id, role):
    payload = {"user_id": user_id, "role": role,
               "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)}
    return jwt.encode(payload, SECRET, algorithm="HS256")

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization","").replace("Bearer ","")
        try:
            data = jwt.decode(token, SECRET, algorithms=["HS256"])
            request.user_id = data["user_id"]
            request.role    = data["role"]
        except:
            return jsonify({"error":"Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization","").replace("Bearer ","")
        try:
            data = jwt.decode(token, SECRET, algorithms=["HS256"])
            if data["role"] != "admin":
                return jsonify({"error":"Forbidden"}), 403
            request.user_id = data["user_id"]
            request.role    = data["role"]
        except:
            return jsonify({"error":"Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    d = request.json
    name, email, pw, dept = d.get("name"), d.get("email"), d.get("password"), d.get("department","")
    if not all([name, email, pw]):
        return jsonify({"error":"All fields required"}), 400
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(f"INSERT INTO users (name,email,password,department) VALUES ({Q},{Q},{Q},{Q})",
                    (name, email, hash_pw(pw), dept))
        conn.commit(); conn.close()
        return jsonify({"message":"Account created"})
    except Exception as e:
        return jsonify({"error":"Email already registered"}), 409

@app.route("/login", methods=["POST"])
def login():
    d = request.json
    email, pw, role = d.get("email"), d.get("password"), d.get("role","employee")
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE email={Q} AND password={Q} AND role={Q}",
                (email, hash_pw(pw), role))
    user = cur.fetchone(); conn.close()
    if not user:
        return jsonify({"error":"Invalid credentials"}), 401
    user = row_to_dict(user)
    token = make_token(user["id"], user["role"])
    return jsonify({"token": token, "user": {
        "id": user["id"], "name": user["name"],
        "email": user["email"], "role": user["role"],
        "department": user["department"]
    }})

# ─── QUIZ ROUTES ──────────────────────────────────────────────────────────────

@app.route("/quizzes", methods=["GET"])
@require_auth
def list_quizzes():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT q.*, COUNT(qu.id) as question_count
        FROM quizzes q LEFT JOIN questions qu ON qu.quiz_id = q.id
        GROUP BY q.id ORDER BY q.id DESC""")
    quizzes = rows_to_list(cur.fetchall()); conn.close()
    return jsonify({"quizzes": quizzes})

@app.route("/quiz/<int:quiz_id>", methods=["GET"])
@require_auth
def get_quiz(quiz_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM quizzes WHERE id={Q}", (quiz_id,))
    quiz = row_to_dict(cur.fetchone())
    if not quiz:
        conn.close()
        return jsonify({"error":"Quiz not found"}), 404
    cur.execute(f"SELECT * FROM questions WHERE quiz_id={Q} ORDER BY id", (quiz_id,))
    qs = rows_to_list(cur.fetchall()); conn.close()
    questions = [{"id": q["id"], "question_text": q["question_text"],
                  "options": json.loads(q["options"]), "correct_index": q["correct_index"]} for q in qs]
    return jsonify({"id": quiz["id"], "title": quiz["title"],
                    "description": quiz["description"], "questions": questions})

@app.route("/submit-quiz", methods=["POST"])
@require_auth
def submit_quiz():
    d = request.json
    quiz_id    = d.get("quiz_id")
    answers    = d.get("answers", {})
    time_taken = float(d.get("time_taken", 0))

    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM questions WHERE quiz_id={Q}", (quiz_id,))
    questions = rows_to_list(cur.fetchall())
    if not questions:
        conn.close()
        return jsonify({"error":"Quiz not found"}), 404

    correct = sum(1 for q in questions
                  if answers.get(str(q["id"])) is not None
                  and int(answers[str(q["id"])]) == q["correct_index"])
    total    = len(questions)
    wrong    = total - correct
    accuracy = round((correct / total) * 100, 1) if total > 0 else 0
    score    = accuracy

    cur.execute(f"SELECT COUNT(*) as cnt FROM results WHERE user_id={Q} AND quiz_id={Q}",
                (request.user_id, quiz_id))
    attempt_num = (cur.fetchone() or {"cnt":0})["cnt"] + 1 if USE_POSTGRES else cur.fetchone()[0] + 1

    cur.execute(f"SELECT score FROM results WHERE user_id={Q}", (request.user_id,))
    prev = [r["score"] if isinstance(r,dict) else r[0] for r in cur.fetchall()]
    prev_avg = sum(prev)/len(prev) if prev else score
    conn.close()

    try:
        from ml_predictor import predict_performance
        label = predict_performance({"score":score,"accuracy":accuracy,
                                     "time_taken":time_taken,"attempt_number":attempt_num,"previous_avg":prev_avg})
    except Exception as e:
        print(f"[ML] {e}")
        label = "High Performer" if score>=80 else ("Average Performer" if score>=50 else "Needs Improvement")

    try:
        from feedback_generator import generate_feedback
        feedback = generate_feedback({"score":score,"accuracy":accuracy,"time_taken":time_taken,
                                      "attempt_number":attempt_num,"previous_avg":prev_avg}, label)
    except Exception as e:
        print(f"[Feedback] {e}")
        if label=="High Performer":
            feedback = f"Great work! You scored {score}% and showed strong understanding of the topic."
        elif label=="Average Performer":
            feedback = f"You scored {score}%. Reviewing missed questions will help push your score higher."
        else:
            feedback = f"You scored {score}% this time. Revisiting the material will make a real difference."

    conn = get_db(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO results
        (user_id,quiz_id,score,accuracy,time_taken,attempt_number,correct_count,total_questions,performance_label,feedback,user_answers)
        VALUES ({Q},{Q},{Q},{Q},{Q},{Q},{Q},{Q},{Q},{Q},{Q})""",
        (request.user_id,quiz_id,score,accuracy,time_taken,attempt_num,correct,total,label,feedback,json.dumps(answers)))
    conn.commit(); conn.close()

    return jsonify({"score":score,"accuracy":accuracy,"time_taken":time_taken,
                    "correct":correct,"wrong":wrong,"total":total,
                    "attempt_number":attempt_num,"performance_label":label,"feedback":feedback})

@app.route("/my-results", methods=["GET"])
@require_auth
def my_results():
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"""
        SELECT r.*, q.title as quiz_title
        FROM results r JOIN quizzes q ON r.quiz_id = q.id
        WHERE r.user_id={Q} ORDER BY r.submitted_at""", (request.user_id,))
    rows = rows_to_list(cur.fetchall()); conn.close()
    return jsonify({"results": rows})

# ─── ADMIN ROUTES ─────────────────────────────────────────────────────────────

@app.route("/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM users WHERE role='employee'")
    total_emp = (cur.fetchone() or {"c":0})["c"]
    cur.execute("SELECT COUNT(*) as c FROM quizzes")
    total_q = (cur.fetchone() or {"c":0})["c"]
    cur.execute("SELECT COUNT(*) as c FROM results")
    total_att = (cur.fetchone() or {"c":0})["c"]
    cur.execute("SELECT AVG(score) as a FROM results")
    avg = (cur.fetchone() or {"a":None})["a"]
    conn.close()
    return jsonify({"total_employees":total_emp,"total_quizzes":total_q,
                    "total_attempts":total_att,"avg_score":round(avg,1) if avg else None})

@app.route("/admin/all-results", methods=["GET"])
@require_admin
def admin_all_results():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT u.id as user_id, u.name as employee_name, u.department,
               q.id as quiz_id, q.title as quiz_title,
               MAX(r.score) as score, r.accuracy, r.time_taken,
               r.performance_label, COUNT(r.id) as total_attempts,
               MAX(r.submitted_at) as submitted_at
        FROM results r
        JOIN users u ON r.user_id=u.id
        JOIN quizzes q ON r.quiz_id=q.id
        GROUP BY r.user_id,r.quiz_id,u.id,u.name,u.department,q.id,q.title,r.accuracy,r.time_taken,r.performance_label
        ORDER BY submitted_at DESC""")
    rows = rows_to_list(cur.fetchall()); conn.close()
    return jsonify({"results": rows})

@app.route("/admin/employees", methods=["GET"])
@require_admin
def admin_employees():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE role != 'admin'")
    emps = rows_to_list(cur.fetchall())
    result = []
    for e in emps:
        cur.execute(f"SELECT COUNT(*) as cnt, AVG(score) as avg FROM results WHERE user_id={Q}", (e["id"],))
        stats = row_to_dict(cur.fetchone()) or {"cnt":0,"avg":None}
        cur.execute(f"SELECT performance_label FROM results WHERE user_id={Q} ORDER BY submitted_at DESC LIMIT 1", (e["id"],))
        last = row_to_dict(cur.fetchone())
        result.append({"id":e["id"],"name":e["name"],"email":e["email"],
                       "department":e["department"],
                       "quiz_count": stats.get("cnt") or 0,
                       "avg_score": round(stats["avg"],1) if stats.get("avg") else None,
                       "performance_label": last["performance_label"] if last else None})
    conn.close()
    return jsonify({"employees": result})

@app.route("/admin/employee/<int:emp_id>", methods=["GET"])
@require_admin
def admin_employee_detail(emp_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE id={Q}", (emp_id,))
    emp = row_to_dict(cur.fetchone())
    if not emp:
        conn.close()
        return jsonify({"error":"Employee not found"}), 404
    cur.execute(f"SELECT COUNT(*) as total_attempts, AVG(score) as avg_score FROM results WHERE user_id={Q}", (emp_id,))
    overall = row_to_dict(cur.fetchone()) or {}
    cur.execute(f"SELECT performance_label FROM results WHERE user_id={Q} ORDER BY submitted_at DESC LIMIT 1", (emp_id,))
    last_label = row_to_dict(cur.fetchone())
    cur.execute(f"""
        SELECT q.id as quiz_id, q.title as quiz_title,
               COUNT(r.id) as total_attempts, MAX(r.score) as best_score,
               AVG(r.score) as avg_score, MAX(r.submitted_at) as last_attempted
        FROM results r JOIN quizzes q ON r.quiz_id=q.id
        WHERE r.user_id={Q} GROUP BY q.id,q.title ORDER BY last_attempted DESC""", (emp_id,))
    quiz_summary = rows_to_list(cur.fetchall())
    conn.close()
    return jsonify({
        "employee":{"id":emp["id"],"name":emp["name"],"email":emp["email"],"department":emp["department"]},
        "overall":{"total_attempts":overall.get("total_attempts") or 0,
                   "avg_score":round(overall["avg_score"],1) if overall.get("avg_score") else None,
                   "performance_label":last_label["performance_label"] if last_label else None,
                   "unique_quizzes":len(quiz_summary)},
        "quiz_summary": quiz_summary
    })

@app.route("/admin/delete-employee/<int:emp_id>", methods=["DELETE"])
@require_admin
def delete_employee(emp_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE id={Q} AND role!='admin'", (emp_id,))
    if not cur.fetchone():
        conn.close()
        return jsonify({"error":"Employee not found"}), 404
    cur.execute(f"DELETE FROM results WHERE user_id={Q}", (emp_id,))
    cur.execute(f"DELETE FROM users WHERE id={Q}", (emp_id,))
    conn.commit(); conn.close()
    return jsonify({"message":"Employee deleted"})

@app.route("/admin/delete-result/<int:result_id>", methods=["DELETE"])
@require_admin
def delete_result(result_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"DELETE FROM results WHERE id={Q}", (result_id,))
    conn.commit(); conn.close()
    return jsonify({"message":"Result deleted"})

@app.route("/admin/create-quiz", methods=["POST"])
@require_admin
def create_quiz():
    d = request.json
    title = d.get("title","").strip()
    description = d.get("description","").strip()
    if not title:
        return jsonify({"error":"Title required"}), 400
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"INSERT INTO quizzes (title,description) VALUES ({Q},{Q})", (title, description))
    if USE_POSTGRES:
        cur.execute("SELECT lastval()")
        quiz_id = cur.fetchone()[0]
    else:
        quiz_id = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({"quiz_id": quiz_id, "message":"Quiz created"})

@app.route("/admin/save-quiz", methods=["POST"])
@require_admin
def save_quiz():
    d = request.json
    quiz_id = d.get("quiz_id")
    title = d.get("title","").strip()
    description = d.get("description","")
    questions = d.get("questions",[])
    if not title:
        return jsonify({"error":"Title required"}), 400
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"UPDATE quizzes SET title={Q},description={Q} WHERE id={Q}", (title,description,quiz_id))
    cur.execute(f"DELETE FROM questions WHERE quiz_id={Q}", (quiz_id,))
    for q in questions:
        cur.execute(f"INSERT INTO questions (quiz_id,question_text,options,correct_index) VALUES ({Q},{Q},{Q},{Q})",
                    (quiz_id, q["question_text"], json.dumps(q["options"]), q["correct_index"]))
    conn.commit(); conn.close()
    return jsonify({"message":"Quiz saved"})

@app.route("/admin/delete-quiz/<int:quiz_id>", methods=["DELETE"])
@require_admin
def delete_quiz(quiz_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"DELETE FROM questions WHERE quiz_id={Q}", (quiz_id,))
    cur.execute(f"DELETE FROM quizzes WHERE id={Q}", (quiz_id,))
    conn.commit(); conn.close()
    return jsonify({"message":"Deleted"})

# ─── AI FEEDBACK PROXY ────────────────────────────────────────────────────────

@app.route("/ai-feedback", methods=["POST"])
@require_auth
def ai_feedback():
    import urllib.request, urllib.error
    data       = request.get_json(force=True) or {}
    score      = data.get("score", 0)
    label      = data.get("label", "Needs Improvement")
    correct    = data.get("correct", 0)
    wrong      = data.get("wrong", 0)
    time_taken = data.get("time_taken", 0)
    quiz_title = data.get("quiz_title", "the quiz")
    api_key    = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error":"ANTHROPIC_API_KEY not configured"}), 503

    prompt = (
        f'You are a supportive workplace performance coach. An employee just completed "{quiz_title}".\n'
        f"Results: Score {score}%, {correct} correct, {wrong} wrong, completed in {time_taken} minutes. "
        f"Performance level: {label}.\n\n"
        "Write a warm, personalised 3-sentence feedback paragraph:\n"
        "1. Acknowledge their result honestly and specifically.\n"
        "2. Give one concrete, actionable tip to improve.\n"
        "3. End with genuine encouragement.\n\n"
        "Keep it conversational, avoid clichés, and be specific to their score. "
        "Do NOT use bullet points or headers. Plain paragraph only."
    )
    payload = json.dumps({"model":"claude-sonnet-4-6","max_tokens":300,"stream":True,
                          "messages":[{"role":"user","content":prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload,
        headers={"Content-Type":"application/json","x-api-key":api_key,
                 "anthropic-version":"2023-06-01"}, method="POST")

    def generate():
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").rstrip("\n")
                    if not line.startswith("data: "): continue
                    json_str = line[6:].strip()
                    if not json_str or json_str == "[DONE]": continue
                    try:
                        evt = json.loads(json_str)
                        if evt.get("type") == "content_block_delta":
                            text = evt.get("delta",{}).get("text","")
                            yield f"data: {json.dumps({'text':text})}\n\n"
                    except: pass
        except urllib.error.HTTPError as e:
            yield f"data: {json.dumps({'error':e.read().decode()})}\n\n"
        except Exception as ex:
            yield f"data: {json.dumps({'error':str(ex)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port  = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", 5000)))
    debug = os.environ.get("FLASK_DEBUG","true").lower() == "true"
    print(f"WorkEval backend running on http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)