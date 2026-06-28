from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
import hashlib
import json
from datetime import datetime
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")
app.secret_key = os.environ.get("SECRET_KEY", "personalized-path-secret")

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

WATSONX_API_KEY = os.environ.get("WATSONX_API_KEY", "")
WATSONX_PROJECT_ID = os.environ.get("WATSONX_PROJECT_ID", "")
WATSONX_URL = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            email    TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            created_at TEXT  DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS preferences (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            career_goal  TEXT,
            skill_level  TEXT,
            known_skills TEXT,
            interests    TEXT,
            study_hours  TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            prompt       TEXT,
            roadmap      TEXT,
            created_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# ── AI helper ─────────────────────────────────────────────────────────────────

def call_granite(prompt: str) -> str:
    """Send a prompt to IBM Granite and return the text response."""
    try:
        creds = Credentials(api_key=WATSONX_API_KEY, url=WATSONX_URL)
        model = ModelInference(
            model_id="ibm/granite-13b-chat-v2",
            credentials=creds,
            project_id=WATSONX_PROJECT_ID,
            params={"max_new_tokens": 1500, "temperature": 0.7},
        )
        response = model.generate_text(prompt=prompt)
        return response
    except Exception as e:
        return f"[AI Error] Could not reach IBM Granite: {str(e)}"


def build_roadmap_prompt(prefs: dict) -> str:
    return f"""You are an expert AI career mentor. A student needs a personalized learning roadmap.

Career Goal: {prefs.get('career_goal', 'Software Developer')}
Current Skill Level: {prefs.get('skill_level', 'Beginner')}
Known Skills/Languages: {prefs.get('known_skills', 'None')}
Interests: {prefs.get('interests', 'General programming')}
Daily Study Time: {prefs.get('study_hours', '2')} hours

Generate a detailed, structured 12-week personalized learning roadmap. Include:
1. Weekly learning goals with specific topics
2. Recommended free resources (YouTube, documentation, courses)
3. Hands-on projects for each phase
4. Certifications to pursue
5. Resume and interview preparation tips

Format each week clearly as "Week N: [Topic]" followed by bullet points.
Be specific, practical, and encouraging."""


def build_chat_prompt(question: str, context: dict) -> str:
    return f"""You are a helpful AI learning mentor for a student with these goals:
Career Goal: {context.get('career_goal', 'Not specified')}
Skill Level: {context.get('skill_level', 'Beginner')}

Answer this question clearly and practically:
{question}

Keep the answer focused, beginner-friendly if needed, and under 300 words."""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = hash_password(request.form["password"])
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, password),
            )
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username or email already exists.")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = hash_password(request.form["password"])
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?", (email, password)
        ).fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid email or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    prefs = conn.execute(
        "SELECT * FROM preferences WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    history = conn.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return render_template("dashboard.html", prefs=prefs, history=history, username=session["username"])


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    if request.method == "POST":
        data = {
            "career_goal": request.form.get("career_goal", ""),
            "skill_level": request.form.get("skill_level", ""),
            "known_skills": request.form.get("known_skills", ""),
            "interests": request.form.get("interests", ""),
            "study_hours": request.form.get("study_hours", "2"),
        }
        existing = conn.execute(
            "SELECT id FROM preferences WHERE user_id = ?", (session["user_id"],)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE preferences SET career_goal=?, skill_level=?, known_skills=?,
                   interests=?, study_hours=? WHERE user_id=?""",
                (*data.values(), session["user_id"]),
            )
        else:
            conn.execute(
                """INSERT INTO preferences (user_id, career_goal, skill_level, known_skills, interests, study_hours)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session["user_id"], *data.values()),
            )
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
    prefs = conn.execute(
        "SELECT * FROM preferences WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()
    return render_template("profile.html", prefs=prefs)


@app.route("/generate", methods=["POST"])
def generate():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    conn = get_db()
    prefs = conn.execute(
        "SELECT * FROM preferences WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    if not prefs:
        return jsonify({"error": "Please complete your profile first."}), 400
    prefs_dict = dict(prefs)
    prompt = build_roadmap_prompt(prefs_dict)
    roadmap = call_granite(prompt)
    conn.execute(
        "INSERT INTO history (user_id, prompt, roadmap) VALUES (?, ?, ?)",
        (session["user_id"], prompt, roadmap),
    )
    conn.commit()
    conn.close()
    return jsonify({"roadmap": roadmap})


@app.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400
    conn = get_db()
    prefs = conn.execute(
        "SELECT * FROM preferences WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()
    context = dict(prefs) if prefs else {}
    prompt = build_chat_prompt(question, context)
    answer = call_granite(prompt)
    return jsonify({"answer": answer})


@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    records = conn.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return render_template("history.html", records=records)


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
