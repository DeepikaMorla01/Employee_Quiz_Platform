from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, hashlib, jwt, os, datetime
from functools import wraps
from dotenv import load_dotenv

# Load .env from the same directory as this file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = Flask(__name__)
CORS(app, origins=["https://deepikamorla01.github.io"])
SECRET = os.environ.get("JWT_SECRET_KEY", "workeval_secret_key_2024")
DB     = os.environ.get("DB_NAME", "workeval.db")

# ─── DB SETUP ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
            correct_count INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            performance_label TEXT,
            feedback TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );
        """)
        # migrations for existing databases
        try:
            db.execute("ALTER TABLE results ADD COLUMN correct_count INTEGER DEFAULT 0")
        except: pass
        try:
            db.execute("ALTER TABLE results ADD COLUMN total_questions INTEGER DEFAULT 0")
        except: pass
        try:
            db.execute("ALTER TABLE results ADD COLUMN user_answers TEXT DEFAULT '{}'")
        except: pass
        # seed admin account
        admin_pw   = os.environ.get("ADMIN_PASSWORD", "admin123")
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@workeval.com")
        admin_name  = os.environ.get("ADMIN_NAME", "Admin")
        admin_dept  = os.environ.get("ADMIN_DEPARTMENT", "HR")
        pw = hashlib.sha256(admin_pw.encode()).hexdigest()
        db.execute("INSERT OR IGNORE INTO users (name, email, password, role, department) VALUES (?,?,?,?,?)",
                   (admin_name, admin_email, pw, "admin", admin_dept))
        db.commit()

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def make_token(user_id, role):
    payload = {"user_id": user_id, "role": role,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)}
    return jwt.encode(payload, SECRET, algorithm="HS256")

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            data = jwt.decode(token, SECRET, algorithms=["HS256"])
            request.user_id = data["user_id"]
            request.role = data["role"]
        except:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            data = jwt.decode(token, SECRET, algorithms=["HS256"])
            if data["role"] != "admin":
                return jsonify({"error": "Forbidden"}), 403
            request.user_id = data["user_id"]
            request.role = data["role"]
        except:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    d = request.json
    name, email, pw, dept = d.get("name"), d.get("email"), d.get("password"), d.get("department", "")
    if not all([name, email, pw]):
        return jsonify({"error": "All fields required"}), 400
    try:
        with get_db() as db:
            db.execute("INSERT INTO users (name, email, password, department) VALUES (?,?,?,?)",
                       (name, email, hash_pw(pw), dept))
            db.commit()
        return jsonify({"message": "Account created"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 409

@app.route("/login", methods=["POST"])
def login():
    d = request.json
    email, pw, role = d.get("email"), d.get("password"), d.get("role", "employee")
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE email=? AND password=? AND role=?",
                          (email, hash_pw(pw), role)).fetchone()
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    token = make_token(user["id"], user["role"])
    return jsonify({"token": token, "user": {"id": user["id"], "name": user["name"],
                                              "email": user["email"], "role": user["role"],
                                              "department": user["department"]}})

# ─── QUIZ ROUTES ──────────────────────────────────────────────────────────────

@app.route("/quizzes", methods=["GET"])
@require_auth
def list_quizzes():
    with get_db() as db:
        quizzes = db.execute("""
            SELECT q.*, COUNT(qu.id) as question_count
            FROM quizzes q
            LEFT JOIN questions qu ON qu.quiz_id = q.id
            GROUP BY q.id ORDER BY q.id DESC""").fetchall()
    return jsonify({"quizzes": [dict(q) for q in quizzes]})

@app.route("/quiz/<int:quiz_id>", methods=["GET"])
@require_auth
def get_quiz(quiz_id):
    import json
    with get_db() as db:
        quiz = db.execute("SELECT * FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
        if not quiz:
            return jsonify({"error": "Quiz not found"}), 404
        qs = db.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY id", (quiz_id,)).fetchall()
    questions = []
    for q in qs:
        questions.append({"id": q["id"], "question_text": q["question_text"],
                          "options": json.loads(q["options"]), "correct_index": q["correct_index"]})
    return jsonify({"id": quiz["id"], "title": quiz["title"],
                    "description": quiz["description"], "questions": questions})

@app.route("/submit-quiz", methods=["POST"])
@require_auth
def submit_quiz():
    import json
    d = request.json
    quiz_id = d.get("quiz_id")
    answers = d.get("answers", {})  # {question_id: selected_index}
    time_taken = float(d.get("time_taken", 0))

    with get_db() as db:
        questions = db.execute("SELECT * FROM questions WHERE quiz_id=?", (quiz_id,)).fetchall()
        if not questions:
            return jsonify({"error": "Quiz not found"}), 404

        correct = 0
        for q in questions:
            user_ans = answers.get(str(q["id"]))
            if user_ans is not None and int(user_ans) == q["correct_index"]:
                correct += 1

        total = len(questions)
        wrong = total - correct
        accuracy = round((correct / total) * 100, 1) if total > 0 else 0
        score = accuracy

        # attempt number for THIS specific quiz
        attempt_num = db.execute(
            "SELECT COUNT(*) as cnt FROM results WHERE user_id=? AND quiz_id=?",
            (request.user_id, quiz_id)).fetchone()["cnt"] + 1

        prev_results = db.execute(
            "SELECT score FROM results WHERE user_id=?", (request.user_id,)).fetchall()
        prev_avg = sum(r["score"] for r in prev_results) / len(prev_results) if prev_results else score

    # ── predict performance & get feedback ──
    try:
        from ml_predictor import predict_performance
        features = {
            "score": score, "accuracy": accuracy,
            "time_taken": time_taken, "attempt_number": attempt_num,
            "previous_avg": prev_avg
        }
        label = predict_performance(features)
    except Exception as e:
        print(f"[ML] Fallback used: {e}")
        label = "High Performer" if score >= 80 else ("Average Performer" if score >= 50 else "Needs Improvement")
        features = {"score": score, "accuracy": accuracy, "time_taken": time_taken,
                    "attempt_number": attempt_num, "previous_avg": prev_avg}

    try:
        from feedback_generator import generate_feedback
        feedback = generate_feedback(features, label)
    except Exception as e:
        print(f"[Feedback] Fallback used: {e}")
        if label == "High Performer":
            feedback = f"Great work! You scored {score}% and completed the quiz in {time_taken} minutes. Your performance shows a strong understanding of the topic."
        elif label == "Average Performer":
            feedback = f"You scored {score}%, which is a solid attempt. Reviewing the questions you missed will help push your score higher next time."
        else:
            feedback = f"You scored {score}% this time. Don't be discouraged — going through the material again before your next attempt will make a real difference."

    with get_db() as db:
        db.execute("""INSERT INTO results
            (user_id, quiz_id, score, accuracy, time_taken, attempt_number, correct_count, total_questions, performance_label, feedback, user_answers)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (request.user_id, quiz_id, score, accuracy, time_taken, attempt_num, correct, total, label, feedback, json.dumps(answers)))
        db.commit()

    return jsonify({"score": score, "accuracy": accuracy, "time_taken": time_taken,
                    "correct": correct, "wrong": wrong, "total": total,
                    "attempt_number": attempt_num, "performance_label": label, "feedback": feedback})

@app.route("/my-results", methods=["GET"])
@require_auth
def my_results():
    with get_db() as db:
        rows = db.execute("""
            SELECT r.*, q.title as quiz_title
            FROM results r JOIN quizzes q ON r.quiz_id = q.id
            WHERE r.user_id=? ORDER BY r.submitted_at""", (request.user_id,)).fetchall()
    return jsonify({"results": [dict(r) for r in rows]})

# ─── ADMIN ROUTES ─────────────────────────────────────────────────────────────

@app.route("/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    with get_db() as db:
        total_emp = db.execute("SELECT COUNT(*) as c FROM users WHERE role='employee'").fetchone()["c"]
        total_q = db.execute("SELECT COUNT(*) as c FROM quizzes").fetchone()["c"]
        total_att = db.execute("SELECT COUNT(*) as c FROM results").fetchone()["c"]
        avg = db.execute("SELECT AVG(score) as a FROM results").fetchone()["a"]
    return jsonify({"total_employees": total_emp, "total_quizzes": total_q,
                    "total_attempts": total_att,
                    "avg_score": round(avg, 1) if avg else None})

@app.route("/admin/all-results", methods=["GET"])
@require_admin
def admin_all_results():
    with get_db() as db:
        # One row per employee per quiz — show their BEST attempt
        rows = db.execute("""
            SELECT
                u.id as user_id, u.name as employee_name, u.department,
                q.id as quiz_id, q.title as quiz_title,
                MAX(r.score) as score,
                r.accuracy, r.time_taken,
                r.performance_label,
                COUNT(r.id) as total_attempts,
                MAX(r.submitted_at) as submitted_at
            FROM results r
            JOIN users u ON r.user_id = u.id
            JOIN quizzes q ON r.quiz_id = q.id
            GROUP BY r.user_id, r.quiz_id
            ORDER BY submitted_at DESC""").fetchall()
    return jsonify({"results": [dict(r) for r in rows]})

@app.route("/admin/employees", methods=["GET"])
@require_admin
def admin_employees():
    with get_db() as db:
        # show ALL non-admin users (some may have registered with wrong dept but correct role)
        emps = db.execute("SELECT * FROM users WHERE role != 'admin'").fetchall()
        result = []
        for e in emps:
            stats = db.execute(
                "SELECT COUNT(*) as cnt, AVG(score) as avg FROM results WHERE user_id=?",
                (e["id"],)).fetchone()
            last = db.execute(
                "SELECT performance_label FROM results WHERE user_id=? ORDER BY submitted_at DESC LIMIT 1",
                (e["id"],)).fetchone()
            result.append({"id": e["id"], "name": e["name"], "email": e["email"],
                           "department": e["department"],
                           "quiz_count": stats["cnt"] or 0,
                           "avg_score": round(stats["avg"], 1) if stats["avg"] else None,
                           "performance_label": last["performance_label"] if last else None})
    return jsonify({"employees": result})

@app.route("/admin/employee/<int:emp_id>", methods=["GET"])
@require_admin
def admin_employee_detail(emp_id):
    with get_db() as db:
        emp = db.execute("SELECT * FROM users WHERE id=?", (emp_id,)).fetchone()
        if not emp:
            return jsonify({"error": "Employee not found"}), 404

        # Group by quiz — one row per quiz with best score + attempt count
        quiz_summary = db.execute("""
            SELECT
                q.id as quiz_id,
                q.title as quiz_title,
                COUNT(r.id) as total_attempts,
                MAX(r.score) as best_score,
                AVG(r.score) as avg_score,
                (SELECT r2.accuracy FROM results r2 WHERE r2.user_id=? AND r2.quiz_id=q.id ORDER BY r2.score DESC LIMIT 1) as best_accuracy,
                (SELECT r2.performance_label FROM results r2 WHERE r2.user_id=? AND r2.quiz_id=q.id ORDER BY r2.score DESC LIMIT 1) as performance_label,
                (SELECT r2.feedback FROM results r2 WHERE r2.user_id=? AND r2.quiz_id=q.id ORDER BY r2.submitted_at DESC LIMIT 1) as latest_feedback,
                MAX(r.submitted_at) as last_attempted,
                (SELECT COUNT(*) FROM questions WHERE quiz_id=q.id) as total_questions
            FROM results r
            JOIN quizzes q ON r.quiz_id = q.id
            WHERE r.user_id=?
            GROUP BY q.id
            ORDER BY last_attempted DESC
        """, (emp_id, emp_id, emp_id, emp_id)).fetchall()

        # overall stats
        overall = db.execute("""
            SELECT COUNT(*) as total_attempts, AVG(score) as avg_score
            FROM results WHERE user_id=?
        """, (emp_id,)).fetchone()

        last_label = db.execute("""
            SELECT performance_label FROM results WHERE user_id=?
            ORDER BY submitted_at DESC LIMIT 1
        """, (emp_id,)).fetchone()

    return jsonify({
        "employee": {
            "id": emp["id"], "name": emp["name"],
            "email": emp["email"], "department": emp["department"]
        },
        "overall": {
            "total_attempts": overall["total_attempts"] or 0,
            "avg_score": round(overall["avg_score"], 1) if overall["avg_score"] else None,
            "performance_label": last_label["performance_label"] if last_label else None,
            "unique_quizzes": len(quiz_summary)
        },
        "quiz_summary": [dict(q) for q in quiz_summary]
    })

@app.route("/admin/delete-employee/<int:emp_id>", methods=["DELETE"])
@require_admin
def delete_employee(emp_id):
    with get_db() as db:
        emp = db.execute("SELECT * FROM users WHERE id=? AND role!='admin'", (emp_id,)).fetchone()
        if not emp:
            return jsonify({"error": "Employee not found"}), 404
        db.execute("DELETE FROM results WHERE user_id=?", (emp_id,))
        db.execute("DELETE FROM users WHERE id=?", (emp_id,))
        db.commit()
    return jsonify({"message": "Employee deleted"})

@app.route("/admin/delete-result/<int:result_id>", methods=["DELETE"])
@require_admin
def delete_result(result_id):
    with get_db() as db:
        db.execute("DELETE FROM results WHERE id=?", (result_id,))
        db.commit()
    return jsonify({"message": "Result deleted"})

@app.route("/admin/create-quiz", methods=["POST"])
@require_admin
def create_quiz():
    d = request.json
    title = d.get("title", "").strip()
    description = d.get("description", "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400
    with get_db() as db:
        cur = db.execute("INSERT INTO quizzes (title, description) VALUES (?,?)", (title, description))
        db.commit()
    return jsonify({"quiz_id": cur.lastrowid, "message": "Quiz created"})

@app.route("/admin/save-quiz", methods=["POST"])
@require_admin
def save_quiz():
    import json
    d = request.json
    quiz_id = d.get("quiz_id")
    title = d.get("title", "").strip()
    description = d.get("description", "")
    questions = d.get("questions", [])
    if not title:
        return jsonify({"error": "Title required"}), 400
    with get_db() as db:
        db.execute("UPDATE quizzes SET title=?, description=? WHERE id=?", (title, description, quiz_id))
        db.execute("DELETE FROM questions WHERE quiz_id=?", (quiz_id,))
        for q in questions:
            db.execute("INSERT INTO questions (quiz_id, question_text, options, correct_index) VALUES (?,?,?,?)",
                       (quiz_id, q["question_text"], json.dumps(q["options"]), q["correct_index"]))
        db.commit()
    return jsonify({"message": "Quiz saved"})

@app.route("/admin/delete-quiz/<int:quiz_id>", methods=["DELETE"])
@require_admin
def delete_quiz(quiz_id):
    with get_db() as db:
        db.execute("DELETE FROM questions WHERE quiz_id=?", (quiz_id,))
        db.execute("DELETE FROM quizzes WHERE id=?", (quiz_id,))
        db.commit()
    return jsonify({"message": "Deleted"})

# ─── AI FEEDBACK PROXY ────────────────────────────────────────────────────────

@app.route("/ai-feedback", methods=["POST"])
@require_auth
def ai_feedback():
    """Stream AI-generated feedback via server-side Anthropic call."""
    import json, urllib.request, urllib.error

    data = request.get_json(force=True) or {}
    score      = data.get("score", 0)
    label      = data.get("label", "Needs Improvement")
    correct    = data.get("correct", 0)
    wrong      = data.get("wrong", 0)
    time_taken = data.get("time_taken", 0)
    quiz_title = data.get("quiz_title", "the quiz")

    # Read API key from .env (loaded at startup)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured on server"}), 503

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

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )

    from flask import Response, stream_with_context

    def generate():
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").rstrip("\n")
                    if not line.startswith("data: "):
                        continue
                    json_str = line[6:].strip()
                    if not json_str or json_str == "[DONE]":
                        continue
                    try:
                        evt = json.loads(json_str)
                        if evt.get("type") == "content_block_delta":
                            delta = evt.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                # SSE format
                                yield f"data: {json.dumps({'text': text})}\n\n"
                    except Exception:
                        pass
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            yield f"data: {json.dumps({'error': err_body})}\n\n"
        except Exception as ex:
            yield f"data: {json.dumps({'error': str(ex)})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", int(os.environ.get("FLASK_PORT", 5000))))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print(f"WorkEval backend running on http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
