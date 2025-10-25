from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
import qrcode, os, io, base64, json

app = Flask(__name__)

DATA_FILE = "data.json"

# Charger les données (adhérents, événements, bénévoles)
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"members": [], "events": [], "volunteers": [], "scans": []}


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# Génération d’un QR code encodé en base64
def generate_qr(member_id):
    img = qrcode.make(member_id)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@app.route("/

