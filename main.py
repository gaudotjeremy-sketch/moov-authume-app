from flask import Flask, render_template, request, jsonify
from flask_session import Session
import os

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin2025")

# --- Stockage des données en mémoire (pour simplifier) ---
members = []
volunteers = []
events = []
validated_bons = {}

# --- Page d'accueil (admin) ---
@app.route("/")
def home():
    return render_template("admin.html")

# --- Page scan (bénévoles) ---
@app.route("/scan")
def scan_page():
    return render_template("scan.html")

# --- Mot de passe admin ---
@app.route("/get-admin-password")
def get_admin_password():
    return jsonify({"password": ADMIN_PASSWORD})

# --- Exemple d'API pour scanner un QR code ---
@app.route("/validate_qr", methods=["POST"])
def validate_qr():
    data = request.get_json()
    member_name = data.get("member_name")
    event = data.get("event")

    if not member_name or not event:
        return jsonify({"status": "error", "message": "Données manquantes."})

    if event not in validated_bons:
        validated_bons[event] = []

    if member_name in validated_bons[event]:
        return jsonify({"status": "error", "message": f"{member_name} a déjà utilisé son bon pour {event}."})
    
    validated_bons[event].append(member_name)
    return jsonify({"status": "ok", "message": f"Bon validé pour {member_name}."})

# --- Lancer l'app ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

