# main.py
import os
import sqlite3
import uuid
import io
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, send_file, session
from flask_session import Session
import qrcode
from dotenv import load_dotenv

load_dotenv()

DB_FILE = "moov_authume.db"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", str(uuid.uuid4()))
Session(app)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin2025")


# --- Database helpers ---
def get_conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    con = get_conn()
    cur = con.cursor()
    # members
    cur.execute("""
      CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        prenom TEXT NOT NULL,
        email TEXT,
        valid_until TEXT,
        token TEXT UNIQUE,
        created_at TEXT
      )
    """)
    # volunteers
    cur.execute("""
      CREATE TABLE IF NOT EXISTS volunteers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT
      )
    """)
    # events
    cur.execute("""
      CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        date TEXT,
        created_at TEXT
      )
    """)
    # event_vouchers (types of bon per event)
    cur.execute("""
      CREATE TABLE IF NOT EXISTS event_vouchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        max_uses INTEGER NOT NULL DEFAULT 1,
        created_at TEXT,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
      )
    """)
    # redemptions
    cur.execute("""
      CREATE TABLE IF NOT EXISTS redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        voucher_id INTEGER NOT NULL,
        redeemed_by TEXT,
        redeemed_at TEXT,
        FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY(voucher_id) REFERENCES event_vouchers(id) ON DELETE CASCADE
      )
    """)
    con.commit()
    con.close()


init_db()


# --- Utility helpers ---
def row_to_member(r):
    return {"id": r[0], "nom": r[1], "prenom": r[2], "email": r[3], "valid_until": r[4], "token": r[5], "created_at": r[6]}


# --- Routes for pages ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin_page():
    # admin page will use API calls; but we can just serve the template
    return render_template("admin.html")


@app.route("/scan")
def scan_page():
    return render_template("scan.html")


# --- Auth (session-based) ---
@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    d = request.get_json() or {}
    pw = d.get("password", "")
    if pw == ADMIN_PASSWORD:
        session["admin_logged"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Mot de passe incorrect"}), 401


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.pop("admin_logged", None)
    return jsonify({"success": True})


def require_admin():
    return session.get("admin_logged") is True


# --- API: Members CRUD ---
@app.route("/api/members", methods=["GET"])
def api_members_list():
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    con = get_conn()
    cur = con.cursor()
    cur.execute("SELECT id,nom,prenom,email,valid_until,token,created_at FROM members ORDER BY nom,prenom")
    rows = cur.fetchall()
    con.close()
    return jsonify([row_to_member(r) for r in rows])


@app.route("/api/members", methods=["POST"])
def api_members_create():
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json() or {}
    nom = d.get("nom", "").strip()
    prenom = d.get("prenom", "").strip()
    email = d.get("email", "").strip()
    valid_until = d.get("valid_until") or None
    token = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    con = get_conn()
    cur = con.cursor()
    cur.execute("INSERT INTO members (nom,prenom,email,valid_until,token,created_at) VALUES (?,?,?,?,?,?)",
                (nom, prenom, email, valid_until, token, now))
    con.commit()
    member_id = cur.lastrowid
    con.close()
    return jsonify({"success": True, "id": member_id, "token": token})


@app.route("/api/members/<int:member_id>", methods=["DELETE"])
def api_members_delete(member_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    con = get_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM members WHERE id=?", (member_id,))
    con.commit()
    con.close()
    return jsonify({"success": True})


@app.route("/api/members/<int:member_id>/prolong", methods=["POST"])
def api_members_prolong(member_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json() or {}
    new_date = d.get("valid_until")
    con = get_conn()
    cur = con.cursor()
    cur.execute("UPDATE members SET valid_until=? WHERE id=?", (new_date, member_id))
    con.commit()
    con.close()
    return jsonify({"success": True, "valid_until": new_date})


# --- QR image by token (admin) ---
@app.route("/api/qrcode/<token>")
def api_qrcode(token):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# --- Volunteers ---
@app.route("/api/volunteers", methods=["GET", "POST"])
def api_volunteers():
    if request.method == "GET":
        con = get_conn(); cur = con.cursor()
        cur.execute("SELECT id,name FROM volunteers ORDER BY name")
        rows = cur.fetchall(); con.close()
        return jsonify([{"id": r[0], "name": r[1]} for r in rows])
    else:
        if not require_admin(): return jsonify({"error": "unauthorized"}), 401
        d = request.get_json() or {}
        name = d.get("name")
        now = datetime.utcnow().isoformat()
        con = get_conn(); cur = con.cursor()
        cur.execute("INSERT INTO volunteers (name, created_at) VALUES (?,?)", (name, now))
        con.commit(); con.close()
        return jsonify({"success": True})


@app.route("/api/volunteers/<int:vid>", methods=["DELETE"])
def api_volunteers_delete(vid):
    if not require_admin(): return jsonify({"error": "unauthorized"}), 401
    con = get_conn(); cur = con.cursor()
    cur.execute("DELETE FROM volunteers WHERE id=?", (vid,))
    con.commit(); con.close()
    return jsonify({"success": True})


# --- Events ---
@app.route("/api/events", methods=["GET", "POST"])
def api_events():
    if request.method == "GET":
        con = get_conn(); cur = con.cursor()
        cur.execute("SELECT id,name,date FROM events ORDER BY date DESC")
        rows = cur.fetchall(); con.close()
        return jsonify([{"id": r[0], "name": r[1], "date": r[2]} for r in rows])
    else:
        if not require_admin(): return jsonify({"error": "unauthorized"}), 401
        d = request.get_json() or {}
        name = d.get("name"); date_str = d.get("date")
        now = datetime.utcnow().isoformat()
        con = get_conn(); cur = con.cursor()
        cur.execute("INSERT INTO events (name,date,created_at) VALUES (?,?,?)", (name, date_str, now))
        con.commit()
        event_id = cur.lastrowid
        con.close()
        return jsonify({"success": True, "id": event_id})


@app.route("/api/events/<int:eid>", methods=["DELETE"])
def api_events_delete(eid):
    if not require_admin(): return jsonify({"error": "unauthorized"}), 401
    con = get_conn(); cur = con.cursor()
    cur.execute("DELETE FROM events WHERE id=?", (eid,))
    cur.execute("DELETE FROM event_vouchers WHERE event_id=?", (eid,))
    cur.execute("DELETE FROM redemptions WHERE event_id=?", (eid,))
    con.commit(); con.close()
    return jsonify({"success": True})


# --- Event vouchers (types of bons) ---
@app.route("/api/event_vouchers", methods=["GET", "POST"])
def api_event_vouchers():
    if request.method == "GET":
        event_id = request.args.get("event_id")
        con = get_conn(); cur = con.cursor()
        cur.execute("SELECT id,event_id,name,max_uses FROM event_vouchers WHERE event_id=?", (event_id,))
        rows = cur.fetchall(); con.close()
        return jsonify([{"id": r[0], "event_id": r[1], "name": r[2], "max_uses": r[3]} for r in rows])
    else:
        if not require_admin(): return jsonify({"error": "unauthorized"}), 401
        d = request.get_json() or {}
        event_id = d.get("event_id"); name = d.get("name"); max_uses = int(d.get("max_uses", 1))
        now = datetime.utcnow().isoformat()
        con = get_conn(); cur = con.cursor()
        cur.execute("INSERT INTO event_vouchers (event_id,name,max_uses,created_at) VALUES (?,?,?,?)",
                    (event_id, name, max_uses, now))
        con.commit(); con.close()
        return jsonify({"success": True})


@app.route("/api/event_vouchers/<int:vid>", methods=["DELETE"])
def api_event_vouchers_delete(vid):
    if not require_admin(): return jsonify({"error": "unauthorized"}), 401
    con = get_conn(); cur = con.cursor()
    cur.execute("DELETE FROM event_vouchers WHERE id=?", (vid,))
    con.commit(); con.close()
    return jsonify({"success": True})


# --- Redemptions (scan) ---
@app.route("/api/redeem", methods=["POST"])
def api_redeem():
    d = request.get_json() or {}
    token = d.get("token")
    event_id = d.get("event_id")
    voucher_id = d.get("voucher_id")
    volunteer_name = d.get("volunteer")

    if not token or not event_id or not voucher_id or not volunteer_name:
        return jsonify({"success": False, "error": "token, event_id, voucher_id et volunteer requis"}), 400

    con = get_conn(); cur = con.cursor()
    # find member
    cur.execute("SELECT id,nom,prenom,valid_until FROM members WHERE token=?", (token,))
    m = cur.fetchone()
    if not m:
        con.close(); return jsonify({"success": False, "error": "Code invalide"}), 404
    member_id, nom, prenom, valid_until = m
    # check validity date
    if valid_until:
        try:
            if date.today() > date.fromisoformat(valid_until):
                con.close()
                return jsonify({"success": False, "error": f'Adhésion expirée le {valid_until}'}), 403
        except Exception:
            pass
    # voucher info
    cur.execute("SELECT name,max_uses FROM event_vouchers WHERE id=? AND event_id=?", (voucher_id, event_id))
    v = cur.fetchone()
    if not v:
        con.close(); return jsonify({"success": False, "error": "Type de bon introuvable"}), 404
    voucher_name, max_uses = v
    # count existing redemptions for this member/event/voucher
    cur.execute("SELECT COUNT(*) FROM redemptions WHERE member_id=? AND event_id=? AND voucher_id=?", (member_id, event_id, voucher_id))
    used_count = cur.fetchone()[0]
    if used_count >= max_uses:
        # find last redemption who/when
        cur.execute("SELECT redeemed_by,redeemed_at FROM redemptions WHERE member_id=? AND event_id=? AND voucher_id=? ORDER BY redeemed_at DESC LIMIT 1",
                    (member_id, event_id, voucher_id))
        last = cur.fetchone()
        con.close()
        return jsonify({"success": False, "error": "Déjà utilisé", "redeemed_by": last[0], "redeemed_at": last[1]}), 409
    # insert redemption
    now = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO redemptions (member_id,event_id,voucher_id,redeemed_by,redeemed_at) VALUES (?,?,?,?,?)",
                (member_id, event_id, voucher_id, volunteer_name, now))
    con.commit(); con.close()
    return jsonify({"success": True, "member": {"nom": nom, "prenom": prenom}, "voucher": voucher_name})


# --- list redemptions (admin) ---
@app.route("/api/redemptions", methods=["GET"])
def api_redemptions_list():
    if not require_admin(): return jsonify({"error": "unauthorized"}), 401
    con = get_conn(); cur = con.cursor()
    cur.execute("""SELECT r.id, m.nom, m.prenom, e.name, v.name, r.redeemed_by, r.redeemed_at
                   FROM redemptions r
                   LEFT JOIN members m ON r.member_id=m.id
                   LEFT JOIN events e ON r.event_id=e.id
                   LEFT JOIN event_vouchers v ON r.voucher_id=v.id
                   ORDER BY r.redeemed_at DESC LIMIT 200""")
    rows = cur.fetchall(); con.close()
    out = []
    for r in rows:
        out.append({"id": r[0], "nom": r[1], "prenom": r[2], "event": r[3], "voucher": r[4], "redeemed_by": r[5], "redeemed_at": r[6]})
    return jsonify(out)


# --- export members CSV (admin) ---
@app.route("/api/export_members")
def api_export_members():
    if not require_admin(): return jsonify({"error": "unauthorized"}), 401
    con = get_conn(); cur = con.cursor()
    cur.execute("SELECT nom,prenom,email,valid_until FROM members ORDER BY nom")
    rows = cur.fetchall(); con.close()
    csv = "Nom,Prénom,Email,Valid_until\n"
    for r in rows:
        csv += f'"{r[0]}","{r[1]}","{r[2] or ""}","{r[3] or ""}"\n'
    return send_file(io.BytesIO(csv.encode("utf-8")), mimetype="text/csv", as_attachment=True, download_name="members.csv")


if __name__ == "__main__":
    # Start server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
