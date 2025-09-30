# server.py
from flask import (
    Flask, render_template, request, redirect, session, url_for, jsonify, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, uuid

# ---------- CONFIG ----------
app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_RANDOM_SECRET"  # <- change for production
BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED = {"png", "jpg", "jpeg", "gif", "mp4", "webm", "mov"}  # media + images
DB_PATH = os.path.join(BASE, "site.db")
MAX_MEDIA_SIZE = 50 * 1024 * 1024  # 50 MB (server-side check optional)

# ---------- DB helpers ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        name TEXT,
        age INTEGER,
        phone TEXT,
        profile_picture TEXT,
        token TEXT,
        is_admin INTEGER DEFAULT 0
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        content TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        filename TEXT,
        type TEXT, -- 'photo' or 'video'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        shared_with_id INTEGER,
        can_edit INTEGER DEFAULT 0,
        FOREIGN KEY(owner_id) REFERENCES users(id),
        FOREIGN KEY(shared_with_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()

def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED

# ---------- Helper utilities ----------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, username, name, age, phone, profile_picture, is_admin FROM users WHERE id=?", (uid,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def user_has_access(owner_id, viewer_id):
    # owner always can; admin bypass checked by caller
    if owner_id == viewer_id:
        return True
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT 1 FROM permissions WHERE owner_id=? AND shared_with_id=?", (owner_id, viewer_id))
    ok = c.fetchone() is not None
    conn.close()
    return ok

# ---------- Static uploads route ----------
@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------- Routes: Home / Auth ----------
@app.route("/")
def root():
    return redirect(url_for("home"))

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        # click-avatar upload only: JS triggers file input when user clicks avatar in register template
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        name = request.form.get("name", "")
        age = request.form.get("age") or None
        phone = request.form.get("phone", "")
        file = request.files.get("profile_picture")  # register template wires profile_picture input to avatar click

        if not username or not password:
            return render_template("register.html", error="Username and password required")

        filename = None
        if file and allowed_file(file.filename):
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))

        hashed = generate_password_hash(password)
        conn = get_db(); c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (username,password,name,age,phone,profile_picture) VALUES (?,?,?,?,?,?)",
                (username, hashed, name, age, phone, filename)
            )
            conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username already taken", form=request.form)
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        row = c.fetchone(); conn.close()
        if row and check_password_hash(row["password"], password):
            session.clear()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            session["is_admin"] = bool(row["is_admin"])
            return redirect(url_for("welcome"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/welcome")
def welcome():
    auth = "user_id" in session
    return render_template("welcome.html", authenticated=auth, username=session.get("username"))

# ---------- Dashboard & profile editing ----------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = current_user()
    # fetch notes and media for this user
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, content, created_at FROM notes WHERE owner_id=? ORDER BY created_at DESC", (user["id"],))
    notes = c.fetchall()
    c.execute("SELECT id, filename, type, created_at FROM media WHERE owner_id=? ORDER BY created_at DESC", (user["id"],))
    media = c.fetchall()
    conn.close()
    # profile_picture URL handling
    profile_url = url_for("static", filename="uploads/default-avatar.png")
    if user.get("profile_picture"):
        profile_url = url_for("uploads", filename=user["profile_picture"])
    return render_template("dashboard.html", user=user, notes=notes, media=media, profile_url=profile_url)

@app.route("/edit_profile", methods=["GET","POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = current_user()
    if request.method == "POST":
        name = request.form.get("name","")
        age = request.form.get("age") or None
        phone = request.form.get("phone","")
        file = request.files.get("profile_picture")
        filename = None
        if file and allowed_file(file.filename):
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            # delete old pic
            if user.get("profile_picture"):
                try:
                    old = os.path.join(UPLOAD_FOLDER, user["profile_picture"])
                    if os.path.exists(old): os.remove(old)
                except: pass
        conn = get_db(); c = conn.cursor()
        if filename:
            c.execute("UPDATE users SET name=?, age=?, phone=?, profile_picture=? WHERE id=?", (name, age, phone, filename, user["id"]))
        else:
            c.execute("UPDATE users SET name=?, age=?, phone=? WHERE id=?", (name, age, phone, user["id"]))
        conn.commit(); conn.close()
        return redirect(url_for("dashboard"))
    return render_template("edit_profile.html", user=user)

# ---------- Password change - shown only after clicking Change Password on dashboard ----------
@app.route("/change_password", methods=["POST"])
def change_password():
    if "user_id" not in session:
        return jsonify({"error":"unauthenticated"}), 401
    uid = session["user_id"]
    old = request.form.get("old_password","")
    new = request.form.get("new_password","")
    if not old or not new:
        return jsonify({"error":"old and new required"}), 400
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT password FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    if not row or not check_password_hash(row["password"], old):
        conn.close()
        return jsonify({"error":"old password incorrect"}), 401
    new_h = generate_password_hash(new)
    c.execute("UPDATE users SET password=? WHERE id=?", (new_h, uid))
    conn.commit(); conn.close()
    return jsonify({"ok":True, "message":"Password changed"})

# ---------- Notes and Media ----------

@app.route("/add_note", methods=["POST"])
def add_note():
    if "user_id" not in session:
        return redirect(url_for("login"))
    content = request.form.get("content","").strip()
    if not content:
        return redirect(url_for("dashboard"))
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO notes (owner_id, content) VALUES (?,?)", (session["user_id"], content))
    conn.commit(); conn.close()
    return redirect(url_for("dashboard"))

@app.route("/delete_note/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db(); c = conn.cursor()
    # check ownership or admin
    c.execute("SELECT owner_id FROM notes WHERE id=?", (note_id,))
    r = c.fetchone()
    if not r:
        conn.close(); abort(404)
    owner_id = r["owner_id"]
    if owner_id != session["user_id"] and not session.get("is_admin"):
        conn.close(); abort(403)
    c.execute("DELETE FROM notes WHERE id=?", (note_id,))
    conn.commit(); conn.close()
    return redirect(url_for("dashboard"))

@app.route("/add_media", methods=["POST"])
def add_media():
    if "user_id" not in session:
        return redirect(url_for("login"))
    file = request.files.get("file")
    if not file or not allowed_file(file.filename):
        return redirect(url_for("dashboard"))
    # optional: check file size from request.content_length
    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    # determine type
    ext = filename.rsplit(".",1)[-1].lower()
    mtype = "photo" if ext in {"png","jpg","jpeg","gif"} else "video"
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO media (owner_id, filename, type) VALUES (?,?,?)", (session["user_id"], filename, mtype))
    conn.commit(); conn.close()
    return redirect(url_for("dashboard"))

@app.route("/delete_media/<int:mid>", methods=["POST"])
def delete_media(mid):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT owner_id, filename FROM media WHERE id=?", (mid,))
    row = c.fetchone()
    if not row:
        conn.close(); abort(404)
    if row["owner_id"] != session["user_id"] and not session.get("is_admin"):
        conn.close(); abort(403)
    # delete file
    try:
        p = os.path.join(UPLOAD_FOLDER, row["filename"])
        if os.path.exists(p): os.remove(p)
    except: pass
    c.execute("DELETE FROM media WHERE id=?", (mid,))
    conn.commit(); conn.close()
    return redirect(url_for("dashboard"))

# ---------- Sharing pages (permissions) ----------
@app.route("/share_page", methods=["POST"])
def share_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    target = request.form.get("username","").strip()
    can_edit = 1 if request.form.get("can_edit") == "on" else 0
    if not target:
        return redirect(url_for("dashboard"))
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target,))
    row = c.fetchone()
    if not row:
        conn.close(); return render_template("dashboard.html", user=current_user(), notes=[], media=[], message="User not found")
    target_id = row["id"]
    # insert if not exists
    c.execute("SELECT 1 FROM permissions WHERE owner_id=? AND shared_with_id=?", (session["user_id"], target_id))
    if not c.fetchone():
        c.execute("INSERT INTO permissions (owner_id, shared_with_id, can_edit) VALUES (?,?,?)", (session["user_id"], target_id, can_edit))
        conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# ---------- Admin console (list/delete users) ----------
@app.route("/admin")
def admin_console():
    if not session.get("is_admin"):
        return "Unauthorized", 403
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, username, name, age, phone, is_admin FROM users ORDER BY id")
    users = c.fetchall()
    conn.close()
    return render_template("admin.html", users=users)

@app.route("/admin/delete_user/<int:uid>", methods=["POST"])
def admin_delete_user(uid):
    if not session.get("is_admin"):
        return "Unauthorized", 403
    conn = get_db(); c = conn.cursor()
    # delete user's media files
    c.execute("SELECT filename FROM media WHERE owner_id=?", (uid,))
    for r in c.fetchall():
        try:
            p = os.path.join(UPLOAD_FOLDER, r["filename"])
            if os.path.exists(p): os.remove(p)
        except: pass
    # delete profile pic
    c.execute("SELECT profile_picture FROM users WHERE id=?", (uid,))
    p = c.fetchone()
    if p and p["profile_picture"]:
        try:
            pp = os.path.join(UPLOAD_FOLDER, p["profile_picture"])
            if os.path.exists(pp): os.remove(pp)
        except: pass
    c.execute("DELETE FROM media WHERE owner_id=?", (uid,))
    c.execute("DELETE FROM notes WHERE owner_id=?", (uid,))
    c.execute("DELETE FROM permissions WHERE owner_id=? OR shared_with_id=?", (uid, uid))
    c.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()
    return redirect(url_for("admin_console"))

# ---------- Run ----------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
