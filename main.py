from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3, uuid, os, datetime

app = Flask(__name__, static_folder="web")
CORS(app)

DB = "moov.db"

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, prenom TEXT, email TEXT,
        token TEXT UNIQUE, valid_until TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, event_id TEXT,
        redeemed_by TEXT, redeemed_at TEXT
    )""")
    con.commit()
    con.close()

init_db()

@app.route("/")
def index():
    return send_from_directory("web", "admin.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("web", path)

@app.route("/members", methods=["GET"])
def get_members():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT nom, prenom, email, token, valid_until FROM members")
    data = [{"nom":n, "prenom":p, "email":e, "token":t, "valid_until":v} for (n,p,e,t,v) in cur.fetchall()]
    con.close()
    return jsonify(data)

@app.route("/members", methods=["POST"])
def add_member():
    d = request.get_json()
    token = str(uuid.uuid4())
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("INSERT INTO members (nom, prenom, email, token, valid_until) VALUES (?, ?, ?, ?, ?)",
                (d["nom"], d["prenom"], d["email"], token, d.get("valid_until")))
    con.commit()
    con.close()
    return jsonify({"success":True, "token":token})

@app.route("/redeem", methods=["POST"])
def redeem():
    d = request.get_json()
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("SELECT id, nom, prenom, valid_until FROM members WHERE token=?", (d["token"],))
    row = cur.fetchone()
    if not row:
        return jsonify({"success":False, "error":"Code invalide"})

    member_id, nom, prenom, valid_until = row

    if valid_until:
        if datetime.date.today() > datetime.date.fromisoformat(valid_until):
            return jsonify({"success":False, "error":"Adhésion expirée"})

    cur.execute("SELECT redeemed_by, redeemed_at FROM redemptions WHERE member_id=? AND event_id=?", (member_id, d["eventId"]))
    redeemed = cur.fetchone()
    if redeemed:
        return jsonify({
            "success":False,
            "error":"Déjà scanné",
            "redeemed_by":redeemed[0],
            "redeemed_at":redeemed[1]
        })

    cur.execute("INSERT INTO redemptions (member_id, event_id, redeemed_by, redeemed_at) VALUES (?, ?, ?, ?)",
                (member_id, d["eventId"], d["volunteer"], datetime.datetime.now().isoformat()))
    con.commit()
    con.close()

    return jsonify({"success":True, "member":{"nom":nom,"prenom":prenom}})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
  
