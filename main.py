import os
import io
import json
import qrcode
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_session import Session

app = Flask(__name__)
app.secret_key = "moov-authume-secret-key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# -----------------------
# STOCKAGE LOCAL
# -----------------------
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"members": [], "events": [], "volunteers": [], "scans": []}, f)

def read_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def write_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# -----------------------
# PAGE D’ACCUEIL
# -----------------------
@app.route("/")
def index():
    return render_template("index.html")

# -----------------------
# ESPACE ADMIN
# -----------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    data = read_data()
    return render_template("admin.html", members=data["members"], events=data["events"], volunteers=data["volunteers"])

# -----------------------
# AJOUT / SUPPRESSION / MISE À JOUR DES ADHÉRENTS
# -----------------------
@app.route("/add_member", methods=["POST"])
def add_member():
    data = read_data()
    name = request.form["name"]
    email = request.form["email"]
    valid_until = request.form["valid_until"]

    member_id = str(len(data["members"]) + 1)
    qr_data = f"MOOV-{member_id}"
    data["members"].append({
        "id": member_id,
        "name": name,
        "email": email,
        "valid_until": valid_until,
        "qr": qr_data
    })
    write_data(data)
    return redirect(url_for("admin"))

@app.route("/delete_member/<member_id>")
def delete_member(member_id):
    data = read_data()
    data["members"] = [m for m in data["members"] if m["id"] != member_id]
    write_data(data)
    return redirect(url_for("admin"))

@app.route("/extend_member/<member_id>", methods=["POST"])
def extend_member(member_id):
    data = read_data()
    for m in data["members"]:
        if m["id"] == member_id:
            m["valid_until"] = request.form["valid_until"]
    write_data(data)
    return redirect(url_for("admin"))

# -----------------------
# GÉNÉRATION DU QR CODE
# -----------------------
@app.route("/qrcode/<member_id>")
def generate_qrcode(member_id):
    data = read_data()
    member = next((m for m in data["members"] if m["id"] == member_id), None)
    if not member:
        return "Membre introuvable", 404
    img = qrcode.make(member["qr"])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# -----------------------
# GESTION DES ÉVÉNEMENTS ET BONS
# -----------------------
@app.route("/add_event", methods=["POST"])
def add_event():
    data = read_data()
    name = request.form["event_name"]
    date = request.form["event_date"]
    drink_limit = int(request.form["drink_limit"])
    food_limit = int(request.form["food_limit"])

    event_id = str(len(data["events"]) + 1)
    data["events"].append({
        "id": event_id,
        "name": name,
        "date": date,
        "limits": {"boisson": drink_limit, "repas": food_limit}
    })
    write_data(data)
    return redirect(url_for("admin"))

@app.route("/delete_event/<event_id>")
def delete_event(event_id):
    data = read_data()
    data["events"] = [e for e in data["events"] if e["id"] != event_id]
    write_data(data)
    return redirect(url_for("admin"))

# -----------------------
# GESTION DES BÉNÉVOLES
# -----------------------
@app.route("/add_volunteer", methods=["POST"])
def add_volunteer():
    data = read_data()
    name = request.form["volunteer_name"]
    vid = str(len(data["volunteers"]) + 1)
    data["volunteers"].append({"id": vid, "name": name})
    write_data(data)
    return redirect(url_for("admin"))

@app.route("/delete_volunteer/<vol_id>")
def delete_volunteer(vol_id):
    data = read_data()
    data["volunteers"] = [v for v in data["volunteers"] if v["id"] != vol_id]
    write_data(data)
    return redirect(url_for("admin"))

# -----------------------
# PAGE SCAN
# -----------------------
@app.route("/scan")
def scan():
    data = read_data()
    return render_template("scan.html", events=data["events"], volunteers=data["volunteers"])

@app.route("/validate", methods=["POST"])
def validate():
    data = read_data()
    code = request.form["code"]
    event_id = request.form["event_id"]
    volunteer_id = request.form["volunteer_id"]
    bon_type = request.form["bon_type"]

    member = next((m for m in data["members"] if m["qr"] == code), None)
    if not member:
        return jsonify({"status": "error", "message": "QR code invalide ❌"})

    event = next((e for e in data["events"] if e["id"] == event_id), None)
    volunteer = next((v for v in data["volunteers"] if v["id"] == volunteer_id), None)

    # Cherche si déjà scanné
    scans = [s for s in data["scans"] if s["member_id"] == member["id"] and s["event_id"] == event_id and s["bon_type"] == bon_type]
    limit = event["limits"].get(bon_type, 1)

    if len(scans) >= limit:
        last = scans[-1]
        return jsonify({
            "status": "error",
            "message": f"Déjà utilisé 😅 — par {last['volunteer_name']} à {last['time']}"
        })

    data["scans"].append({
        "member_id": member["id"],
        "member_name": member["name"],
        "event_id": event_id,
        "event_name": event["name"],
        "volunteer_id": volunteer_id,
        "volunteer_name": volunteer["name"],
        "bon_type": bon_type,
        "time": datetime.now().strftime("%H:%M:%S")
    })

    write_data(data)
    return jsonify({"status": "success", "message": f"Bon {bon_type} validé pour {member['name']} ✅"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
