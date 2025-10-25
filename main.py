from flask import Flask, render_template, request, jsonify, send_file
from flask_session import Session
import io, qrcode, base64, os, datetime

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin2025")

members = []
volunteers = []
events = []
validated = {}  # {event_name: [(member_name, time, volunteer_name)]}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin_page():
    return render_template("admin.html", members=members, volunteers=volunteers, events=events)

@app.route("/get-admin-password")
def get_admin_password():
    return jsonify({"password": ADMIN_PASSWORD})

@app.route("/scan")
def scan_page():
    return render_template("scan.html", events=events, volunteers=volunteers)

@app.route("/add_member", methods=["POST"])
def add_member():
    data = request.get_json()
    name = data["name"]
    email = data["email"]
    expiration = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    qr_data = f"{name}|{email}|{expiration}"
    qr_img = qrcode.make(qr_data)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    members.append({"name": name, "email": email, "expiration": expiration, "qr": qr_base64})
    return jsonify({"status": "ok", "qr": qr_base64})

@app.route("/delete_member", methods=["POST"])
def delete_member():
    data = request.get_json()
    name = data["name"]
    global members
    members = [m for m in members if m["name"] != name]
    return jsonify({"status": "ok"})

@app.route("/extend_member", methods=["POST"])
def extend_member():
    data = request.get_json()
    name = data["name"]
    for m in members:
        if m["name"] == name:
            new_date = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
            m["expiration"] = new_date
            return jsonify({"status": "ok", "new_date": new_date})
    return jsonify({"status": "error"})

@app.route("/add_volunteer", methods=["POST"])
def add_volunteer():
    data = request.get_json()
    volunteers.append(data["name"])
    return jsonify({"status": "ok"})

@app.route("/delete_volunteer", methods=["POST"])
def delete_volunteer():
    data = request.get_json()
    name = data["name"]
    global volunteers
    volunteers = [v for v in volunteers if v != name]
    return jsonify({"status": "ok"})

@app.route("/add_event", methods=["POST"])
def add_event():
    data = request.get_json()
    events.append(data["name"])
    validated[data["name"]] = []
    return jsonify({"status": "ok"})

@app.route("/delete_event", methods=["POST"])
def delete_event():
    data = request.get_json()
    name = data["name"]
    global events
    events = [e for e in events if e != name]
    validated.pop(name, None)
    return jsonify({"status": "ok"})

@app.route("/validate_qr", methods=["POST"])
def validate_qr():
    data = request.get_json()
    event = data["event"]
    member_name = data["member"]
    volunteer = data["volunteer"]

    if event not in validated:
        validated[event] = []

    for entry in validated[event]:
        if entry[0] == member_name:
            return jsonify({"status": "error", "message": f"Déjà scanné par {entry[2]} à {entry[1]}"})

    time = datetime.datetime.now().strftime("%H:%M:%S")
    validated[event].append((member_name, time, volunteer))
    return jsonify({"status": "ok", "message": f"Validation enregistrée à {time}"})

@app.route("/export_members")
def export_members():
    csv_data = "Nom,Email,Expiration\n"
    for m in members:
        csv_data += f"{m['name']},{m['email']},{m['expiration']}\n"
    return send_file(io.BytesIO(csv_data.encode()), mimetype="text/csv", as_attachment=True, download_name="adherents.csv")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
