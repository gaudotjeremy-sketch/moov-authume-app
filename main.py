# main.py
import os, sqlite3, uuid, datetime, io
from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for, send_file
from flask_cors import CORS
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import qrcode
from dotenv import load_dotenv

load_dotenv()

APP = Flask(__name__, static_folder="web", static_url_path="/")
CORS(APP)
APP.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'change_me'
APP.config['SESSION_TYPE'] = 'filesystem'
Session(APP)

DB_FILE = 'moov_authume.db'
ADMIN_PW = os.environ.get('ADMIN_PASSWORD') or 'admin123'

# --- init db
def init_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (
        id TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS members (
        id TEXT PRIMARY KEY, nom TEXT, prenom TEXT, email TEXT, valid_until TEXT, active INTEGER DEFAULT 1, token TEXT UNIQUE, created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY, name TEXT, date TEXT, created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS volunteers (
        id TEXT PRIMARY KEY, name TEXT, created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS voucher_types (
        id TEXT PRIMARY KEY, name TEXT, description TEXT, created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS redemptions (
        id TEXT PRIMARY KEY, member_id TEXT, event_id TEXT, voucher_type_id TEXT, redeemed_by TEXT, redeemed_at TEXT)''')
    con.commit()
    con.close()
init_db()

# --- helper DB
def db_conn():
    return sqlite3.connect(DB_FILE)

def require_admin():
    if session.get('admin_logged') != True:
        return False
    return True

# --- static file root
@APP.route('/')
def index():
    # redirect to login (admin). The site is single-site: admin behind login, scanner public page.
    return redirect('/login.html')

@APP.route('/<path:path>')
def static_proxy(path):
    return send_from_directory('web', path)

# --- Admin auth endpoints
@APP.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json() or {}
    pw = data.get('password','')
    # check against env ADMIN_PASSWORD (simple)
    if ADMIN_PW and pw == ADMIN_PW:
        session['admin_logged'] = True
        return jsonify({'success':True})
    return jsonify({'success':False, 'error':'Mot de passe incorrect'}), 401

@APP.route('/api/admin/logout', methods=['POST'])
def api_admin_logout():
    session.pop('admin_logged', None)
    return jsonify({'success':True})

@APP.route('/api/admin/check', methods=['GET'])
def api_admin_check():
    return jsonify({'ok': require_admin()})

# --- Members management
@APP.route('/api/members', methods=['GET'])
def api_members_list():
    if not require_admin(): return jsonify({'error':'unauthorized'}), 401
    con = db_conn(); cur = con.cursor()
    cur.execute('SELECT id,nom,prenom,email,valid_until,active,token,created_at FROM members ORDER BY nom')
    rows = cur.fetchall(); con.close()
    res = []
    for r in rows:
        res.append({'id':r[0],'nom':r[1],'prenom':r[2],'email':r[3],'valid_until':r[4],'active':bool(r[5]),'token':r[6],'created_at':r[7]})
    return jsonify(res)

@APP.route('/api/members', methods=['POST'])
def api_members_create():
    if not require_admin(): return jsonify({'error':'unauthorized'}), 401
    d = request.get_json() or {}
    nom = d.get('nom','').strip()
    prenom = d.get('prenom','').strip()
    email = d.get('email','').strip()
    valid_until = d.get('valid_until') or None
    token = str(uuid.uuid4())
    idm = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    con = db_conn(); cur = con.cursor()
    cur.execute('INSERT INTO members (id,nom,prenom,email,valid_until,active,token,created_at) VALUES (?,?,?,?,?,?,?,?)',
                (idm,nom,prenom,email,valid_until,1,token,now))
    con.commit(); con.close()
    return jsonify({'success':True,'id':idm,'token':token})

@APP.route('/api/members/<member_id>', methods=['DELETE'])
def api_members_delete(member_id):
    if not require_admin(): return jsonify({'error':'unauthorized'}), 401
    con = db_conn(); cur = con.cursor()
    cur.execute('DELETE FROM members WHERE id=?',(member_id,))
    cur.execute('DELETE FROM redemptions WHERE member_id=?',(member_id,))
    con.commit(); con.close()
    return jsonify({'success':True})

@APP.route('/api/members/<member_id>/prolong', methods=['POST'])
def api_members_prolong(member_id):
    if not require_admin(): return jsonify({'error':'unauthorized'}), 401
    d = request.get_json() or {}
    # expect valid_until new date string (YYYY-MM-DD)
    new_date = d.get('valid_until')
    con = db_conn(); cur = con.cursor()
    cur.execute('UPDATE members SET valid_until=? WHERE id=?',(new_date,member_id))
    con.commit(); con.close()
    return jsonify({'success':True,'valid_until':new_date})

# --- Events
@APP.route('/api/events', methods=['GET','POST'])
def api_events():
    if request.method=='GET':
        con=db_conn(); cur=con.cursor()
        cur.execute('SELECT id,name,date FROM events ORDER BY date DESC')
        rows=cur.fetchall(); con.close()
        return jsonify([{'id':r[0],'name':r[1],'date':r[2]} for r in rows])
    else:
        if not require_admin(): return jsonify({'error':'unauthorized'}),401
        d=request.get_json() or {}
        eid=str(uuid.uuid4()); now=datetime.datetime.utcnow().isoformat()
        con=db_conn(); cur=con.cursor()
        cur.execute('INSERT INTO events (id,name,date,created_at) VALUES (?,?,?,?)',(eid,d.get('name'),d.get('date'),now))
        con.commit(); con.close()
        return jsonify({'success':True,'id':eid})

@APP.route('/api/events/<event_id>', methods=['DELETE'])
def api_events_delete(event_id):
    if not require_admin(): return jsonify({'error':'unauthorized'}),401
    con=db_conn(); cur=con.cursor()
    cur.execute('DELETE FROM events WHERE id=?',(event_id,))
    cur.execute('DELETE FROM redemptions WHERE event_id=?',(event_id,))
    con.commit(); con.close()
    return jsonify({'success':True})

# --- Volunteers
@APP.route('/api/volunteers', methods=['GET','POST'])
def api_volunteers():
    if request.method=='GET':
        con=db_conn(); cur=con.cursor()
        cur.execute('SELECT id,name FROM volunteers ORDER BY name')
        rows=cur.fetchall(); con.close()
        return jsonify([{'id':r[0],'name':r[1]} for r in rows])
    else:
        if not require_admin(): return jsonify({'error':'unauthorized'}),401
        d=request.get_json() or {}
        vid=str(uuid.uuid4()); now=datetime.datetime.utcnow().isoformat()
        con=db_conn(); cur=con.cursor()
        cur.execute('INSERT INTO volunteers (id,name,created_at) VALUES (?,?,?)',(vid,d.get('name'),now))
        con.commit(); con.close()
        return jsonify({'success':True,'id':vid})

@APP.route('/api/volunteers/<vol_id>', methods=['DELETE'])
def api_volunteers_delete(vol_id):
    if not require_admin(): return jsonify({'error':'unauthorized'}),401
    con=db_conn(); cur=con.cursor()
    cur.execute('DELETE FROM volunteers WHERE id=?',(vol_id,))
    con.commit(); con.close()
    return jsonify({'success':True})

# --- Voucher types
@APP.route('/api/voucher_types', methods=['GET','POST'])
def api_voucher_types():
    if request.method=='GET':
        con=db_conn(); cur=con.cursor()
        cur.execute('SELECT id,name,description FROM voucher_types ORDER BY name')
        rows=cur.fetchall(); con.close()
        return jsonify([{'id':r[0],'name':r[1],'description':r[2]} for r in rows])
    else:
        if not require_admin(): return jsonify({'error':'unauthorized'}),401
        d=request.get_json() or {}
        vid=str(uuid.uuid4()); now=datetime.datetime.utcnow().isoformat()
        con=db_conn(); cur=con.cursor()
        cur.execute('INSERT INTO voucher_types (id,name,description,created_at) VALUES (?,?,?,?)',(vid,d.get('name'),d.get('description'),now))
        con.commit(); con.close()
        return jsonify({'success':True,'id':vid})

@APP.route('/api/voucher_types/<vt_id>', methods=['DELETE'])
def api_voucher_types_delete(vt_id):
    if not require_admin(): return jsonify({'error':'unauthorized'}),401
    con=db_conn(); cur=con.cursor()
    cur.execute('DELETE FROM voucher_types WHERE id=?',(vt_id,))
    con.commit(); con.close()
    return jsonify({'success':True})

# --- Redemption (scan)
@APP.route('/api/redeem', methods=['POST'])
def api_redeem():
    d = request.get_json() or {}
    token = d.get('token')
    event_id = d.get('eventId')
    volunteer = d.get('volunteer')
    voucher_type_id = d.get('voucherTypeId')  # optional: which kind of bon

    if not token or not event_id or not volunteer:
        return jsonify({'success':False,'error':'token, eventId et volunteer requis'}),400

    con=db_conn(); cur=con.cursor()
    cur.execute('SELECT id,nom,prenom,valid_until,active FROM members WHERE token=?',(token,))
    m = cur.fetchone()
    if not m:
        con.close(); return jsonify({'success':False,'error':'Code invalide'}),404

    member_id, nom, prenom, valid_until, active = m
    if active==0:
        con.close(); return jsonify({'success':False,'error':'Adhésion désactivée'}),403
    if valid_until:
        try:
            if datetime.date.today() > datetime.date.fromisoformat(valid_until):
                con.close(); return jsonify({'success':False,'error':'Adhésion expirée le '+valid_until},),403
        except Exception:
            pass

    # check existing redemption for same member/event/voucher_type (one use per member per event per type)
    if voucher_type_id:
        cur.execute('SELECT redeemed_by,redeemed_at FROM redemptions WHERE member_id=? AND event_id=? AND voucher_type_id=?',(member_id,event_id,voucher_type_id))
    else:
        cur.execute('SELECT redeemed_by,redeemed_at FROM redemptions WHERE member_id=? AND event_id=?',(member_id,event_id))
    already = cur.fetchone()
    if already:
        con.close()
        return jsonify({'success':False,'error':'Déjà scanné','redeemed_by':already[0],'redeemed_at':already[1]}),409

    # insert redemption
    rid=str(uuid.uuid4()); now=datetime.datetime.utcnow().isoformat()
    cur.execute('INSERT INTO redemptions (id,member_id,event_id,voucher_type_id,redeemed_by,redeemed_at) VALUES (?,?,?,?,?,?)',
                (rid,member_id,event_id,voucher_type_id,volunteer,now))
    con.commit(); con.close()
    return jsonify({'success':True,'member':{'nom':nom,'prenom':prenom}})

# --- list redemptions (admin)
@APP.route('/api/redemptions', methods=['GET'])
def api_redemptions_list():
    if not require_admin(): return jsonify({'error':'unauthorized'}),401
    con=db_conn(); cur=con.cursor()
    cur.execute('SELECT r.id,m.nom,m.prenom,e.name,r.voucher_type_id,r.redeemed_by,r.redeemed_at FROM redemptions r LEFT JOIN members m ON r.member_id=m.id LEFT JOIN events e ON r.event_id=e.id ORDER BY r.redeemed_at DESC')
    rows=cur.fetchall(); con.close()
    res=[]
    for r in rows:
        res.append({'id':r[0],'nom':r[1],'prenom':r[2],'event':r[3],'voucher_type_id':r[4],'redeemed_by':r[5],'redeemed_at':r[6]})
    return jsonify(res)

# --- QR image for member (admin) : serve a PNG QR for a given token
@APP.route('/api/qrcode/<token>')
def api_qrcode(token):
    # admin-only for privacy
    if not require_admin(): return jsonify({'error':'unauthorized'}),401
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    APP.run(host='0.0.0.0', port=port)
