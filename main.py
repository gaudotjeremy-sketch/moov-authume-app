import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_file
from flask_session import Session
import qrcode
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin2025")

# --- BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect("moov.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        prenom TEXT,
        email TEXT,
        valid_until TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS volunteers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        date TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS validations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        qr_data TEXT UNIQUE,
        volunteer TEXT,
        time TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# --- ROUTES DE BASE ---
@app.route("/")
def home():
    return render_template("admin.html")

@app.route("/scan")
def scan():
    return render_template("scan.html")

@app.route("/get-admin-password")
def get_admin_password():
    return jsonify({"password": ADMIN_PASSWORD})

# --- ADHÉRENTS ---
@app.route("/api/members", methods=["GET", "POST", "DELETE", "PUT"])
def manage_members():
    conn = sqlite3.connect("moov.db")
    c = conn.cursor()

    if request.method == "GET":
        members = c.execute("SELECT * FROM members").fetchall()
        conn.close()
        return jsonify(members)

    if request.method == "POST":
        data = request.json
        c.execute("INSERT INTO members (nom, prenom, email, valid_until) VALUES (?, ?, ?, ?)",
                  (data["nom"], data["prenom"], data["email"], data["valid_until"]))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    if request.method == "PUT":
        data = request.json
        c.execute("UPDATE members SET valid_until=? WHERE id=?", (data["valid_until"], data["id"]))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    if request.method == "DELETE":
        member_id = request.args.get("id")
        c.execute("DELETE FROM members WHERE id=?", (member_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "deleted"})

# --- GÉNÉRATION DE QR CODE ---
@app.route("/api/qrcode/<int:member_id>")
def generate_qrcode(member_id):
    conn = sqlite3.connect("moov.db")
    c = conn.cursor()
    c.execute("SELECT nom, prenom, email FROM members WHERE id=?", (member_id,))
    member = c.fetchone()
    conn.close()

    if not member:
        return "Adhérent introuvable", 404

    qr_data = f"Adhérent: {member[0]} {member[1]} | Email: {member[2]}"
    img = qrcode.make(qr_data)
    buffer = BytesIO()
    img.save(buffer, "PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")

# --- VALIDATION DES QR CODES ---
@app.route("/api/validate", methods=["POST"])
def validate_qr():
    data = request.json
    qr_data = data.get("qr_data")
    volunteer = data.get("volunteer")

    conn = sqlite3.connect("moov.db")
    c = conn.cursor()
    c.execute("SELECT volunteer, time FROM validations WHERE qr_data=?", (qr_data,))
    existing = c.fetchone()

    if existing:
        conn.close()
        return jsonify({"status": "used", "volunteer": existing[0], "time": existing[1]})

    time_now = datetime.now().strftime("%H:%M:%S")
    c.execute("INSERT INTO validations (qr_data, volunteer, time) VALUES (?, ?, ?)", (qr_data, volunteer, time_now))
    conn.commit()
    conn.close()

    member_name = qr_data.split("Adhérent: ")[1].split("|")[0].strip()
    return jsonify({"status": "ok", "member": member_name})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

    member_name = qr_data.split("Adhérent: ")[1].split("|")[0].strip()
    return jsonify({"status": "ok", "member": member_name})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
