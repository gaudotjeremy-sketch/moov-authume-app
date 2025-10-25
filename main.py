import os
import sqlite3
import qrcode
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from datetime import datetime
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "moov2025")
DATABASE = "database.db"

# --- Base de données ---
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        # Table des adhérents
        c.execute("""CREATE TABLE IF NOT EXISTS members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nom TEXT, prenom TEXT, email TEXT,
                        valid_until TEXT, qr_code TEXT UNIQUE
                    )""")
        # Table des bénévoles
        c.execute("""CREATE TABLE IF NOT EXISTS volunteers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nom TEXT
                    )""")
        # Table des événements
        c.execute("""CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nom TEXT, date TEXT,
                        bons_boisson INTEGER DEFAULT 1,
                        bons_repas INTEGER DEFAULT 0,
                        bons_autre INTEGER DEFAULT 0
                    )""")
        # Table des scans
        c.execute("""CREATE TABLE IF NOT EXISTS scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        member_id INTEGER,
                        event_id INTEGER,
                        bon_type TEXT,
                        volunteer TEXT,
                        timestamp TEXT
                    )""")
        conn.commit()
init_db()

# --- Génération de QR codes ---
def generate_qr_code(data, filename):
    qr_dir = os.path.join("static", "qrcodes")
    # Vérifie que c'est bien un dossier
    if not os.path.isdir(qr_dir):
        try:
            os.makedirs(qr_dir, exist_ok=True)
        except FileExistsError:
            pass

    qr = qrcode.make(data)
    qr.save(filename)

def get_member_by_qr(qr_code):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, nom, prenom FROM members WHERE qr_code=?", (qr_code,))
        return c.fetchone()

# --- ROUTES ---

@app.route("/")
def index():
    return render_template("index.html")

# --- Espace Admin ---
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "logged_in" not in session:
        if request.method == "POST":
            if request.form["password"] == ADMIN_PASSWORD:
                session["logged_in"] = True
                return redirect(url_for("admin"))
            else:
                return render_template("index.html", error="Mot de passe incorrect ⚠️")
        return render_template("index.html")

    # Récupération des données à afficher
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM members")
        members = c.fetchall()
        c.execute("SELECT * FROM volunteers")
        volunteers = c.fetchall()
        c.execute("SELECT * FROM events")
        events = c.fetchall()
    return render_template("admin.html", members=members, volunteers=volunteers, events=events)

# --- Ajout d'un membre ---
@app.route("/add_member", methods=["POST"])
def add_member():
    nom = request.form["nom"]
    prenom = request.form["prenom"]
    email = request.form["email"]
    valid_until = request.form["valid_until"]

    qr_code_data = f"{nom}-{prenom}-{email}"
    qr_filename = f"static/qrcodes/{secure_filename(qr_code_data)}.png"

    generate_qr_code(qr_code_data, qr_filename)

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO members (nom, prenom, email, valid_until, qr_code) VALUES (?, ?, ?, ?, ?)",
                  (nom, prenom, email, valid_until, qr_code_data))
        conn.commit()
    return redirect(url_for("admin"))

# --- Suppression d'un membre ---
@app.route("/delete_member", methods=["POST"])
def delete_member():
    member_id = request.form["id"]
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM members WHERE id=?", (member_id,))
        conn.commit()
    return redirect(url_for("admin"))

# --- Ajout d'un bénévole ---
@app.route("/add_volunteer", methods=["POST"])
def add_volunteer():
    nom = request.form["nom"]
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO volunteers (nom) VALUES (?)", (nom,))
        conn.commit()
    return redirect(url_for("admin"))

# --- Suppression d'un bénévole ---
@app.route("/delete_volunteer", methods=["POST"])
def delete_volunteer():
    volunteer_id = request.form["id"]
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM volunteers WHERE id=?", (volunteer_id,))
        conn.commit()
    return redirect(url_for("admin"))

# --- Ajout d'un événement ---
@app.route("/add_event", methods=["POST"])
def add_event():
    nom = request.form["nom"]
    date = request.form["date"]
    bons_boisson = int(request.form.get("bons_boisson", 0))
    bons_repas = int(request.form.get("bons_repas", 0))
    bons_autre = int(request.form.get("bons_autre", 0))

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO events (nom, date, bons_boisson, bons_repas, bons_autre)
                     VALUES (?, ?, ?, ?, ?)""",
                     (nom, date, bons_boisson, bons_repas, bons_autre))
        conn.commit()
    return redirect(url_for("admin"))

# --- Espace Bénévole ---
@app.route("/benevole")
def benevole():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM events")
        events = c.fetchall()
        c.execute("SELECT * FROM volunteers")
        volunteers = c.fetchall()
    return render_template("benevole.html", events=events, volunteers=volunteers)

# --- Scan des QR codes ---
@app.route("/scan", methods=["POST"])
def scan():
    data = request.json
    qr_code = data["qr"]
    event_id = data["event_id"]
    volunteer = data["volunteer"]
    bon_type = data["bon_type"]

    member = get_member_by_qr(qr_code)
    if not member:
        return jsonify({"status": "error", "message": "QR code invalide ❌"})

    member_id = member[0]
    member_name = f"{member[1]} {member[2]}"

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT bons_boisson, bons_repas, bons_autre FROM events WHERE id=?", (event_id,))
        event = c.fetchone()
        if not event:
            return jsonify({"status": "error", "message": "Événement introuvable ❌"})

        max_bons = {"boisson": event[0], "repas": event[1], "autre": event[2]}
        c.execute("SELECT COUNT(*) FROM scans WHERE member_id=? AND event_id=? AND bon_type=?",
                  (member_id, event_id, bon_type))
        used = c.fetchone()[0]

        if used >= max_bons[bon_type]:
            c.execute("""SELECT volunteer, timestamp FROM scans
                         WHERE member_id=? AND event_id=? AND bon_type=? ORDER BY id DESC LIMIT 1""",
                         (member_id, event_id, bon_type))
            last = c.fetchone()
            return jsonify({"status": "used", "message": f"🚫 Bon déjà utilisé par {last[0]} à {last[1]} !"})

        c.execute("""INSERT INTO scans (member_id, event_id, bon_type, volunteer, timestamp)
                     VALUES (?, ?, ?, ?, ?)""",
                     (member_id, event_id, bon_type, volunteer, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    return jsonify({"status": "ok", "message": f"✅ Bon {bon_type} validé pour {member_name} !"})

# --- Lancement ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
