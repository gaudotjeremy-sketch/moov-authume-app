from flask import Flask, render_template, request, jsonify, send_file
from flask_session import Session
import io, qrcode, base64, os, datetime

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin2025")

members = []      # [{name, email, expiration, qr}]
volunteers = []   # [name]
events = []       # [name]
validated = {}    # {event_name: [(member_name, time, volunteer_name)]}


def generate_qr(name, email, expiration):
    data = f"{name}|{email}|{expiration}"
    qr_img = qrcode.make(data)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


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
    expiration = data["expiration"]

    qr_base64 = generate_qr(name, email, expiration)
    members.append({"name": name, "email": email, "expiration": expiration, "qr": qr_base64})

    return jsonify({"status": "ok", "qr": qr_base64})


@app.route("/delete_member", methods=["POST"])
def delete_member():
    data = request.get_json()
    global members
    members = [m for m in members if m["name"] != data["name"]]
    return jsonify({"status": "ok"})


@app.route("/extend_member", methods=["POST"])
def extend_member():
    data = request.get_json()
    name = data["name"]
    new_date = data["new_date"]
    for m in members:
        if m["name"] == name:
            m["expiration"] = new_date
            m["qr"] = generate_qr(m["name"], m["email"], new_date)
            return jsonify({"status": "ok", "new_date": new_date})
    return jsonify({"status": "error"})


@app.route("/add_event", methods=["POST"])
def add_event():
    data = request.get_json()
    events.append(data["name"])
    validated[data["name"]] = []
    return jsonify({"status": "ok"})


@app.route("/delete_event", methods=["POST"])
def delete_event():
    data = request.get_json()
    global events
    events = [e for e in events if e != data["name"]]
    validated.pop(data["name"], None)
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

