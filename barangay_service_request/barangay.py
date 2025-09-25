from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
from pathlib import Path
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret123"  # <- use a secure random key in production

DB_PATH = Path(__file__).parent / "requests.db"

# ==== File Upload Settings ====
UPLOAD_FOLDER = Path(__file__).parent / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ==== Database Init ====
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # Create table if not exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                issue TEXT,
                location TEXT,
                date TEXT,
                status TEXT
            )
        ''')
        conn.commit()

        # Ensure "photo" column exists (migration-safe)
        try:
            c.execute("ALTER TABLE requests ADD COLUMN photo TEXT")
            conn.commit()
            print("✅ Added missing 'photo' column.")
        except sqlite3.OperationalError:
            # Column already exists
            pass

init_db()

# ==== Routes ====
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["GET", "POST"])
def submit():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        issue = request.form.get("issue", "").strip()
        location = request.form.get("location", "").strip()
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        status = "Pending"

        # --- Handle Photo Upload ---
        photo_filename = None
        if "photo" in request.files:
            file = request.files["photo"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_path = UPLOAD_FOLDER / filename
                file.save(save_path)
                photo_filename = filename

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO requests (name, issue, location, date, status, photo) VALUES (?,?,?,?,?,?)",
                (name, issue, location, date, status, photo_filename)
            )
            conn.commit()

        return redirect(url_for("requests_list"))

    return render_template("submit.html")

@app.route("/requests")
def requests_list():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM requests ORDER BY date DESC")
        requests_data = c.fetchall()
    return render_template("requests.html", requests=requests_data)

# === Simple Admin Login ===
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = request.form.get("username", "")
        pw = request.form.get("password", "")
        if user == "admin" and pw == "password":
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if not session.get("admin"):
        return redirect(url_for("login"))

    if request.method == "POST" and "status" in request.form:
        req_id = request.form.get("id")
        new_status = request.form.get("status")
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE requests SET status=? WHERE id=?", (new_status, req_id))
            conn.commit()

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM requests ORDER BY date DESC")
        requests_data = c.fetchall()

    return render_template("admin.html", requests=requests_data)

# === Delete Request Route ===
@app.route("/delete_request/<int:req_id>", methods=["POST"])
def delete_request(req_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM requests WHERE id=?", (req_id,))
        conn.commit()

    return redirect(url_for("admin_panel"))

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
