import base64
from flask import Flask, request, redirect, session, render_template_string
import sqlite3, os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY","change-this-secret-key")
DB="admin.db"

def db():
    con=sqlite3.connect(DB, timeout=30)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    try:
        con.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return con

def init():
    con=db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS players(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT,
      balance INTEGER DEFAULT 0,
      vip TEXT DEFAULT 'Normal',
      status TEXT DEFAULT 'Active'
    );
    CREATE TABLE IF NOT EXISTS games(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      enabled INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      player TEXT,
      type TEXT,
      amount INTEGER,
      status TEXT DEFAULT 'Pending'
    );
    CREATE TABLE IF NOT EXISTS notices(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      message TEXT
    );
    CREATE TABLE IF NOT EXISTS payment_settings(
        id INTEGER PRIMARY KEY,
        upi_id TEXT DEFAULT '',
        qr_url TEXT DEFAULT '',
        account_name TEXT DEFAULT '',
        note TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS qr_ranges(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    min_amount INTEGER NOT NULL,
    max_amount INTEGER NOT NULL,
    upi_id TEXT DEFAULT '',
    qr_url TEXT DEFAULT '',
    account_name TEXT DEFAULT '',
    note TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1
);
""")
    if con.execute("SELECT COUNT(*) c FROM games").fetchone()["c"]==0:
        con.executemany("INSERT INTO games(name) VALUES(?)",
                       [("Aviator",),("Slots",),("Lucky Gems Demo",)])
    # Seed QR ranges if empty
    count = con.execute("SELECT COUNT(*) FROM qr_ranges").fetchone()[0]
    if count == 0:
        ranges = [
            (1,100),
            (101,500),
            (501,1000),
            (1001,2000),
            (2001,3000),
            (3001,5000),
            (5001,10000),
            (10001,100000)
        ]
        con.executemany(
            """INSERT INTO qr_ranges
            (min_amount,max_amount,account_name,note,enabled)
            VALUES(?,?,?, ?,1)""",
            [(a,b,"","") for a,b in ranges]
        )

    con.commit()
    con.close()

PAGE="""
<!doctype html>
<html>
<head>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Spin Admin Panel</title>
<style>
body{margin:0;background:#07111f;color:#fff;font-family:Arial}
header{padding:16px;background:#102038;font-size:20px;font-weight:bold}
nav{padding:10px;background:#0b1728}
nav a{display:inline-block;color:white;text-decoration:none;background:#18304d;padding:10px;margin:3px;border-radius:8px}
main{padding:14px}
.card{background:#102038;padding:15px;border-radius:12px;margin:8px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
input,select,button{padding:11px;border:0;border-radius:8px;margin:4px}
button{background:#19b97c;color:white;font-weight:bold}
table{width:100%;border-collapse:collapse;background:#102038}
td,th{padding:10px;border-bottom:1px solid #24364d;text-align:left}
.badge{padding:5px 8px;border-radius:7px;background:#24364d}
</style>
</head>
<body>
<header>SPIN ADMIN PANEL</header>
{% if session.get('admin') %}
<nav>
<a href="/">Dashboard</a>
<a href="/players">Players</a>
<a href="/games">Games</a>
<a href="/payments">Payments</a><a href="/finance">Finance</a><a href="/admin/direct-credit">Direct Credit</a>
<a href="/notifications">Notifications</a>
<a href="/support">Support</a>
<a href="/history">History</a>
<a href="/logout">Logout</a>
</nav>
{% endif %}
<main>{{body|safe}}</main>
</body></html>
"""

def page(body):
    return render_template_string(PAGE,body=body)

def auth():
    return session.get("admin")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        if request.form.get("user")==os.environ.get("SPIN123_ADMIN_USER","Id7297862426") and request.form.get("pass")==os.environ.get("ADMIN_PASSWORD","7297862426"):
            session["admin"]=1
            return redirect("/")
        return page("<div class=card>Wrong username or password</div>")
    return page("""
    <div class=card>
    <h2>Admin Login</h2>
    <form method=post>
    <input name=user placeholder=Username>
    <input type=password name=pass placeholder=Password>
    <button>LOGIN</button>
    </form>
    </div>""")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def home():
    if not auth(): return redirect("/login")
    con=db()
    p=con.execute("SELECT COUNT(*) c FROM players").fetchone()["c"]
    g=con.execute("SELECT COUNT(*) c FROM games WHERE enabled=1").fetchone()["c"]
    pay=con.execute("SELECT COUNT(*) c FROM payments WHERE status='Pending'").fetchone()["c"]
    con.close()
    return page(f"""
    <div class=grid>
    <div class=card>Players<h2>{p}</h2></div>
    <div class=card>Enabled Games<h2>{g}</h2></div>
    <div class=card>Online<h2>0</h2></div>
    <div class=card>Pending Requests<h2>{pay}</h2></div>
    </div>
    <div class=card><b>Backend connected ✅</b><br>SQLite database active</div>
    """)

@app.route("/players",methods=["GET","POST"])
def players():
    if not auth(): return redirect("/login")
    con=db()
    if request.method=="POST":
        con.execute("INSERT INTO players(username,balance,vip) VALUES(?,?,?)",
                    (request.form["username"],request.form.get("balance",0),request.form.get("vip","Normal")))
        con.commit()
    rows=con.execute("SELECT * FROM players ORDER BY id DESC").fetchall()
    con.close()
    html="""<div class=card><h3>Add Player</h3>
    <form method=post>
    <input name=username placeholder="Player name" required>
    <input name=balance type=number value=0>
    <select name=vip><option>Normal</option><option>VIP 1</option><option>VIP 2</option><option>VIP 3</option></select>
    <button>Add Player</button></form></div>
    <table><tr><th>ID</th><th>Player</th><th>Balance</th><th>VIP</th><th>Status</th></tr>"""
    for r in rows:
        html+=f"<tr><td>{r['id']}</td><td>{r['username']}</td><td>{r['balance']}</td><td>{r['vip']}</td><td>{r['status']}</td></tr>"
    return page(html+"</table>")

@app.route("/games")
def games():
    if not auth(): return redirect("/login")
    con=db()
    rows=con.execute("SELECT * FROM games").fetchall()
    con.close()
    html="<h3>Game Management</h3>"
    for r in rows:
        s="Enabled" if r["enabled"] else "Disabled"
        html+=f"<div class=card>{r['name']} <span class=badge>{s}</span> <a href='/game/{r['id']}/toggle'><button>Toggle</button></a></div>"
    return page(html)

@app.route("/game/<int:i>/toggle")
def toggle_game(i):
    if not auth(): return redirect("/login")
    con=db()
    con.execute("UPDATE games SET enabled=1-enabled WHERE id=?",(i,))
    con.commit(); con.close()
    return redirect("/games")

@app.route("/payments",methods=["GET","POST"])
def payments():
    if not auth(): return redirect("/login")
    con=db()
    if request.method=="POST":
        con.execute("INSERT INTO payments(player,type,amount) VALUES(?,?,?)",
                    (request.form["player"],request.form["type"],request.form["amount"]))
        con.commit()
    rows=con.execute("SELECT * FROM payments ORDER BY id DESC").fetchall()

    # ===== PAYMENT TOTAL SUMMARY =====
    try:
        total_deposit = float(con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM money_requests WHERE type='Deposit'"
        ).fetchone()[0] or 0)
        total_withdraw = float(con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM money_requests WHERE type='Withdraw'"
        ).fetchone()[0] or 0)
        total_refund = float(con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM money_requests WHERE type='Refund'"
        ).fetchone()[0] or 0)
        total_pending = float(con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM money_requests WHERE status='Pending'"
        ).fetchone()[0] or 0)
        total_approved = float(con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM money_requests WHERE status='Approved'"
        ).fetchone()[0] or 0)
    except Exception:
        total_deposit = total_withdraw = total_refund = 0.0
        total_pending = total_approved = 0.0

    try:
        prow = con.execute("SELECT balance FROM platform_account WHERE id=1").fetchone()
        platform_balance = float(prow[0] if prow else 0)
    except Exception:
        platform_balance = 0.0

    con.close()
    cfgcon=db()
    cfg=cfgcon.execute("SELECT upi_id,qr_url,account_name,note FROM payment_settings WHERE id=1").fetchone()
    cfgcon.close()

    upi=cfg["upi_id"] if cfg else ""
    qr=cfg["qr_url"] if cfg else ""
    account=cfg["account_name"] if cfg else ""
    note=cfg["note"] if cfg else ""

    rangecon=db()
    range_rows=rangecon.execute(
        "SELECT id,min_amount,max_amount,upi_id,qr_url,account_name,note,enabled FROM qr_ranges ORDER BY min_amount"
    ).fetchall()
    rangecon.close()

    range_cards="""<div class=card><h3>QR Amount Ranges</h3>"""

    for rr in range_rows:
        state="Enabled" if rr["enabled"] else "Disabled"
        checked="checked" if rr["enabled"] else ""

        range_cards+=f"""<div style="padding:12px;margin:10px 0;background:#0b1728;border-radius:8px">
        <b>₹{rr["min_amount"]} - ₹{rr["max_amount"]}</b>
        <p>Status: {state}</p>

        <form method=post action="/qr-range/{rr['id']}" enctype="multipart/form-data">
        <input name=account_name placeholder="Account Name" value="{rr['account_name'] or ''}">
        <input name=upi_id placeholder="UPI ID" value="{rr['upi_id'] or ''}">
        <input name=note placeholder="Note" value="{rr['note'] or ''}">
        <input type=file name=qr_file accept="image/png,image/jpeg,image/webp">
        <input type=hidden name=old_qr value="{rr['qr_url'] or ''}">
        <label>
        <input type=checkbox name=enabled value=1 {checked}> Enabled
        </label>
        <button>Save Range</button>
        </form>"""

        if rr["qr_url"]:
            range_cards+=f"""<br>
            <img src="{rr['qr_url']}" style="max-width:160px;border-radius:8px">"""

        range_cards+="</div>"

    range_cards+="</div>"

    qr_card=range_cards+f"""<div class=card>
    <h3>QR Payment Settings</h3>
    <form method=post action="/payment-settings" enctype="multipart/form-data">
    <input name=account_name placeholder="Account Name" value="{account}">
    <input name=upi_id placeholder="UPI ID" value="{upi}">
    <input type=file name=qr_file accept="image/png,image/jpeg,image/webp">\n    <input type=hidden name=old_qr value="{qr}">
    <input name=note placeholder="Payment Note" value="{note}">
    <button>Save QR Settings</button>
    </form>"""
    if qr:
        qr_card+=f"""<br><img src="{qr}" style="max-width:220px">
        <p><b>UPI ID:</b> {upi}</p>"""
    qr_card+="</div>"

    summary_card=f"""
<div class=card>
<h2>Payment Amount Summary</h2>
<div class=grid>
  <div class=card><b>Total Deposits</b><h2>₹{total_deposit:,.2f}</h2></div>
  <div class=card><b>Total Withdrawals</b><h2>₹{total_withdraw:,.2f}</h2></div>
  <div class=card><b>Total Refunds</b><h2>₹{total_refund:,.2f}</h2></div>
  <div class=card><b>Pending Amount</b><h2>₹{total_pending:,.2f}</h2></div>
  <div class=card><b>Approved Amount</b><h2>₹{total_approved:,.2f}</h2></div>
  <div class=card><b>Platform Balance</b><h2>₹{platform_balance:,.2f}</h2></div>
</div>
</div>
"""

    html=summary_card+qr_card+"""
<div class=card>
<h3>Temporary Unlimited Withdrawal</h3>
<p>Time खत्म होने पर 80% withdrawal rule अपने आप वापस लागू होगा.</p>

<button onclick="setUnlimited(30)">30 Min</button>
<button onclick="setUnlimited(60)">1 Hour</button>
<button onclick="setUnlimited(120)">2 Hours</button>
<button onclick="setUnlimited(0)">OFF</button>

<p id="unlimitedStatus">Status loading...</p>

<script>
async function setUnlimited(minutes){
    const key = prompt("Admin API Key");
    if(!key) return;

    const r = await fetch("/api/admin/withdrawal-unlimited",{
        method:"POST",
        headers:{
            "Content-Type":"application/json",
            "X-Admin-Key":key
        },
        body:JSON.stringify({minutes:minutes})
    });

    const j = await r.json();

    if(!j.ok){
        alert(j.error || "Request failed");
        return;
    }

    if(j.unlimited){
        document.getElementById("unlimitedStatus").innerText =
            "Unlimited until: " + j.unlimited_until;
    }else{
        document.getElementById("unlimitedStatus").innerText =
            "OFF - 80% rule active";
    }
}
</script>
<div class=card><h3>Payment Requests</h3>
    <form method=post>
    <input name=player placeholder="Player" required>
    <select name=type><option>Deposit</option><option>Withdrawal Demo</option><option>Refund Demo</option></select>
    <input name=amount type=number placeholder="Amount" required>
    <button>Create Request</button></form></div>
    <table><tr><th>Player</th><th>Type</th><th>Amount</th><th>Status</th><th>Action</th></tr>"""
    for r in rows:
        html+=f"<tr><td>{r['player']}</td><td>{r['type']}</td><td>{r['amount']}</td><td>{r['status']}</td><td><a href='/payment/{r['id']}/approve'><button>Approve</button></a></td></tr>"
    return page(html+"</table>")

@app.route("/payment-settings",methods=["POST"])
def save_payment_settings():
    if not auth():
        return redirect("/login")
    con=db()
    con.execute(
        """INSERT OR REPLACE INTO payment_settings
        (id,upi_id,qr_url,account_name,note)
        VALUES(1,?,?,?,?)""",
        (
            request.form.get("upi_id","").strip(),
            (
            "data:" + request.files["qr_file"].mimetype + ";base64," +
            base64.b64encode(request.files["qr_file"].read()).decode("ascii")
            if request.files.get("qr_file") and request.files["qr_file"].filename
            else request.form.get("old_qr","").strip()
        ),
            request.form.get("account_name","").strip(),
            request.form.get("note","").strip()
        )
    )
    con.commit()
    con.close()
    return redirect("/payments")

@app.route("/qr-range/<int:range_id>",methods=["POST"])
def save_qr_range(range_id):
    if not auth():
        return redirect("/login")

    qr=request.form.get("old_qr","").strip()

    f=request.files.get("qr_file")
    if f and f.filename:
        qr="data:"+f.mimetype+";base64,"+base64.b64encode(f.read()).decode("ascii")

    con=db()
    con.execute(
        """UPDATE qr_ranges
        SET upi_id=?,qr_url=?,account_name=?,note=?,enabled=?
        WHERE id=?""",
        (
            request.form.get("upi_id","").strip(),
            qr,
            request.form.get("account_name","").strip(),
            request.form.get("note","").strip(),
            1 if request.form.get("enabled")=="1" else 0,
            range_id
        )
    )
    con.commit()
    con.close()

    return redirect("/payments")

@app.route("/payment/<int:i>/approve")
def approve(i):
    if not auth(): return redirect("/login")
    con=db()
    con.execute("UPDATE payments SET status='Approved' WHERE id=?",(i,))
    con.commit(); con.close()
    return redirect("/payments")

@app.route("/notifications",methods=["GET","POST"])
def notifications():
    if not auth(): return redirect("/login")
    con=db()
    if request.method=="POST":
        con.execute("INSERT INTO notices(message) VALUES(?)",(request.form["message"],))
        con.commit()
    rows=con.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
    con.close()
    html="""<div class=card><h3>Notifications</h3>
    <form method=post><input name=message placeholder="Notification message" required><button>Save Notification</button></form></div>"""
    for r in rows: html+=f"<div class=card>{r['message']}</div>"
    return page(html)

@app.route("/support")
def support():
    if not auth(): return redirect("/login")
    con=db()
    rows=con.execute("""
        SELECT p.id,p.username,
               COUNT(sm.id) AS message_count,
               MAX(sm.created_at) AS last_message,
               SUM(CASE WHEN sm.sender='player' AND sm.is_read=0 THEN 1 ELSE 0 END) AS unread
        FROM players p
        JOIN support_messages sm ON sm.player_id=p.id
        GROUP BY p.id,p.username
        ORDER BY last_message DESC
    """).fetchall()
    con.close()
    import html
    body="<div class=card><h2>Player Support Inbox</h2><p>Text, image, PDF/document support chat.</p></div>"
    if not rows:
        body += "<div class=card>No support conversations yet.</div>"
    for r in rows:
        body += (
            "<div class=card>"
            f"<b>User ID {r['id']} — {html.escape(str(r['username']))}</b><br>"
            f"Messages: {r['message_count']} &nbsp; Unread: {r['unread'] or 0}<br>"
            f"Last: {html.escape(str(r['last_message'] or ''))}<br><br>"
            f"<a href='/support/{r['id']}'><button>Open Chat</button></a>"
            "</div>"
        )
    return page(body)

@app.route("/history")
def history():
    if not auth(): return redirect("/login")
    con=db()
    rows=con.execute("SELECT * FROM payments ORDER BY id DESC LIMIT 50").fetchall()
    con.close()
    html="<h3>Activity History</h3>"
    for r in rows:
        html+=f"<div class=card>{r['player']} — {r['type']} — ₹{r['amount']} — {r['status']}</div>"
    return page(html)

init()


from flask import jsonify

@app.route('/api/games')
def api_games():
    con=db()
    rows=con.execute("SELECT id,name,enabled,code,category,resource_url FROM games ORDER BY id").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/players')
def api_players():
    con=db()
    rows=con.execute("SELECT id,username,balance,vip,status FROM players ORDER BY id DESC").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/payments')
def api_payments():
    con=db()
    rows=con.execute("SELECT id,player,type,amount,status FROM payments ORDER BY id DESC LIMIT 100").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/notices')
def api_notices():
    con=db()
    rows=con.execute("SELECT id,message FROM notices ORDER BY id DESC").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


# ===== PLAYER / WALLET API =====
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import datetime
import os

def api_player():
    auth_header = request.headers.get("Authorization","")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:].strip()

    con=db()
    row=con.execute(
        "SELECT * FROM players WHERE token=? AND status='Active'",
        (token,)
    ).fetchone()
    con.close()
    return row


@app.route("/api/register", methods=["POST"])
def api_register():
    data=request.get_json(silent=True) or {}
    username=str(data.get("username","")).strip()
    password=str(data.get("password",""))

    if len(username) < 3 or len(password) < 6:
        return jsonify({
            "ok":False,
            "error":"Username minimum 3 and password minimum 6 characters"
        }),400

    con=db()

    old=con.execute(
        "SELECT id FROM players WHERE lower(username)=lower(?)",
        (username,)
    ).fetchone()

    if old:
        con.close()
        return jsonify({"ok":False,"error":"Username already exists"}),409

    token=secrets.token_urlsafe(32)

    con.execute("""
        INSERT INTO players(
            username,balance,vip,status,password_hash,token,created_at
        )
        VALUES(?,0,'Normal','Active',?,?,?)
    """,(
        username,
        generate_password_hash(password),
        token,
        datetime.utcnow().isoformat()
    ))

    con.commit()

    player=con.execute(
        "SELECT id,username,balance,vip,status FROM players WHERE username=?",
        (username,)
    ).fetchone()

    con.close()

    return jsonify({
        "ok":True,
        "token":token,
        "player":dict(player)
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    data=request.get_json(silent=True) or {}
    username=str(data.get("username","")).strip()
    password=str(data.get("password",""))

    con=db()
    row=con.execute(
        "SELECT * FROM players WHERE lower(username)=lower(?)",
        (username,)
    ).fetchone()

    if not row or not row["password_hash"] or \
       not check_password_hash(row["password_hash"],password):
        con.close()
        return jsonify({"ok":False,"error":"Invalid login"}),401

    if row["status"] != "Active":
        con.close()
        return jsonify({"ok":False,"error":"Account disabled"}),403

    token=secrets.token_urlsafe(32)

    con.execute(
        "UPDATE players SET token=? WHERE id=?",
        (token,row["id"])
    )
    con.commit()

    player=con.execute(
        "SELECT id,username,balance,vip,status FROM players WHERE id=?",
        (row["id"],)
    ).fetchone()

    con.close()

    return jsonify({
        "ok":True,
        "token":token,
        "player":dict(player)
    })


@app.route("/api/wallet", methods=["GET"])
def api_wallet():
    player=api_player()

    if not player:
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    con=db()

    history=con.execute("""
        SELECT id,type,amount,status,reference,created_at
        FROM wallet_transactions
        WHERE player_id=?
        ORDER BY id DESC
        LIMIT 50
    """,(player["id"],)).fetchall()

    con.close()

    return jsonify({
        "ok":True,
        "balance":player["balance"],
        "history":[dict(x) for x in history]
    })


@app.route("/api/deposit", methods=["POST"])
def api_deposit_request():
    player=api_player()

    if not player:
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    data=request.get_json(silent=True) or {}

    try:
        amount=int(data.get("amount",0))
    except:
        amount=0

    if amount <= 0:
        return jsonify({"ok":False,"error":"Invalid amount"}),400

    con=db()

    cur=con.execute("""
        INSERT INTO money_requests(player_id,type,amount,status)
        VALUES(?,'Deposit',?,'Pending')
    """,(player["id"],amount))

    con.commit()
    request_id=cur.lastrowid
    con.close()

    return jsonify({
        "ok":True,
        "request_id":request_id,
        "status":"Pending"
    })


@app.route("/api/withdraw", methods=["POST"])
def api_withdraw_request():
    player=api_player()

    if not player:
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    data=request.get_json(silent=True) or {}

    try:
        amount=int(data.get("amount",0))
    except:
        amount=0

    if amount <= 0:
        return jsonify({"ok":False,"error":"Invalid amount"}),400

    if amount > player["balance"]:
        return jsonify({
            "ok":False,
            "error":"Insufficient balance"
        }),400

    con=db()

    # Maximum cumulative withdrawal = 80% of approved deposits
    dep = con.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM money_requests
        WHERE player_id=? AND type='Deposit' AND status='Approved'
    """, (player["id"],)).fetchone()[0]

    used = con.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM money_requests
        WHERE player_id=? AND type='Withdraw'
          AND status IN ('Pending','Approved')
    """, (player["id"],)).fetchone()[0]

    max_withdraw = int(dep * 0.80)
    remaining = max(0, max_withdraw - used)

    unlimited = False
    row = con.execute(
        "SELECT unlimited_until FROM withdrawal_settings WHERE id=1"
    ).fetchone()

    if row and row[0]:
        from datetime import datetime
        try:
            unlimited = datetime.fromisoformat(row[0]) > datetime.now()
        except ValueError:
            unlimited = False

    if (not unlimited) and amount > remaining:
        con.close()
        return jsonify({
            "ok": False,
            "error": "80% withdrawal limit exceeded",
            "approved_deposit": dep,
            "max_withdraw": max_withdraw,
            "already_used": used,
            "remaining": remaining
        }),400

    account_holder = str(data.get("account_holder","")).strip()
    account_number = str(data.get("account_number","")).strip()
    ifsc = str(data.get("ifsc","")).strip().upper()
    bank_name = str(data.get("bank_name","")).strip()

    if not account_holder or not account_number or not ifsc:
        con.close()
        return jsonify({
            "ok": False,
            "error": "Bank details required"
        }),400

    cur=con.execute("""
        INSERT INTO money_requests(
            player_id,type,amount,status,
            account_holder,account_number,ifsc,bank_name
        )
        VALUES(?,'Withdraw',?,'Pending',?,?,?,?)
    """,(
        player["id"],amount,
        account_holder,account_number,ifsc,bank_name
    ))

    con.commit()
    request_id=cur.lastrowid
    con.close()

    return jsonify({
        "ok":True,
        "request_id":request_id,
        "status":"Pending"
    })


@app.route("/api/admin/game/<int:game_id>/toggle", methods=["POST"])
def api_admin_game_toggle(game_id):
    expected=os.environ.get("SPIN123_ADMIN_API_KEY","")
    supplied=request.headers.get("X-Admin-Key","")

    if not expected or not secrets.compare_digest(expected,supplied):
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    con=db()

    game=con.execute(
        "SELECT id,name,enabled FROM games WHERE id=?",
        (game_id,)
    ).fetchone()

    if not game:
        con.close()
        return jsonify({"ok":False,"error":"Game not found"}),404

    new_status=0 if game["enabled"] else 1

    con.execute(
        "UPDATE games SET enabled=? WHERE id=?",
        (new_status,game_id)
    )

    con.commit()
    con.close()

    return jsonify({
        "ok":True,
        "id":game_id,
        "name":game["name"],
        "enabled":new_status
    })




@app.route("/api/admin/money-request/<int:req_id>/approve", methods=["POST"])
def api_admin_approve_money_request(req_id):
    expected=os.environ.get("SPIN123_ADMIN_API_KEY","")
    supplied=request.headers.get("X-Admin-Key","")

    if not expected or not secrets.compare_digest(expected,supplied):
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    con=db()

    try:
        con.execute("BEGIN IMMEDIATE")

        req=con.execute("""
            SELECT id,player_id,type,amount,status
            FROM money_requests
            WHERE id=?
        """,(req_id,)).fetchone()

        if not req:
            con.rollback()
            con.close()
            return jsonify({"ok":False,"error":"Request not found"}),404

        if req["status"] != "Pending":
            con.rollback()
            con.close()
            return jsonify({
                "ok":False,
                "error":"Request already processed",
                "status":req["status"]
            }),409

        if req["type"] == "Deposit":

            con.execute("""
                UPDATE players
                SET balance=balance+?
                WHERE id=?
            """,(req["amount"],req["player_id"]))

            con.execute("""
                INSERT INTO wallet_transactions
                (player_id,type,amount,status,reference)
                VALUES(?,?,?,?,?)
            """,(
                req["player_id"],
                "Deposit",
                req["amount"],
                "Completed",
                "DEP-"+str(req_id)
            ))

        elif req["type"] == "Withdraw":

            player=con.execute(
                "SELECT balance FROM players WHERE id=?",
                (req["player_id"],)
            ).fetchone()

            if not player or player["balance"] < req["amount"]:
                con.rollback()
                con.close()
                return jsonify({
                    "ok":False,
                    "error":"Insufficient balance"
                }),400

            con.execute("""
                UPDATE players
                SET balance=balance-?
                WHERE id=?
            """,(req["amount"],req["player_id"]))

            con.execute("""
                INSERT INTO wallet_transactions
                (player_id,type,amount,status,reference)
                VALUES(?,?,?,?,?)
            """,(
                req["player_id"],
                "Withdraw",
                -req["amount"],
                "Completed",
                "WDR-"+str(req_id)
            ))

        else:
            con.rollback()
            con.close()
            return jsonify({"ok":False,"error":"Unknown request type"}),400

        con.execute(
            "UPDATE money_requests SET status='Approved' WHERE id=?",
            (req_id,)
        )

        con.commit()

        player=con.execute(
            "SELECT id,username,balance FROM players WHERE id=?",
            (req["player_id"],)
        ).fetchone()

        con.close()

        return jsonify({
            "ok":True,
            "request_id":req_id,
            "status":"Approved",
            "player":dict(player)
        })

    except Exception as e:
        con.rollback()
        con.close()
        return jsonify({"ok":False,"error":str(e)}),500



@app.route("/api/admin/money-request/<int:req_id>/reject", methods=["POST"])
def api_admin_reject_money_request(req_id):
    expected=os.environ.get("SPIN123_ADMIN_API_KEY","")
    supplied=request.headers.get("X-Admin-Key","")

    if not expected or not secrets.compare_digest(expected,supplied):
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    con=db()

    req=con.execute("""
        SELECT id,player_id,type,amount,status
        FROM money_requests
        WHERE id=?
    """,(req_id,)).fetchone()

    if not req:
        con.close()
        return jsonify({"ok":False,"error":"Request not found"}),404

    if req["status"] != "Pending":
        con.close()
        return jsonify({
            "ok":False,
            "error":"Request already processed",
            "status":req["status"]
        }),409

    con.execute(
        "UPDATE money_requests SET status='Rejected' WHERE id=?",
        (req_id,)
    )
    con.commit()
    con.close()

    return jsonify({
        "ok":True,
        "request_id":req_id,
        "status":"Rejected"
    })



@app.route("/api/payment-settings", methods=["GET"])
def api_payment_settings():
    con = db()
    row = con.execute(
        "SELECT upi_id, qr_url, account_name, note FROM payment_settings WHERE id=1"
    ).fetchone()
    con.close()

    if not row:
        return jsonify({
            "upi_id": "",
            "qr_url": "",
            "account_name": "",
            "note": ""
        })

    return jsonify(dict(row))


@app.route("/api/admin/withdrawal-unlimited", methods=["POST"])
def admin_withdrawal_unlimited():
    expected = os.environ.get("SPIN123_ADMIN_API_KEY")
    supplied = request.headers.get("X-Admin-Key", "")

    if not expected or not secrets.compare_digest(expected, supplied):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}

    try:
        minutes = int(data.get("minutes", 0))
    except:
        minutes = 0

    con = db()

    if minutes <= 0:
        until = ""
    else:
        from datetime import datetime, timedelta
        until = (datetime.now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")

    con.execute(
        "UPDATE withdrawal_settings SET unlimited_until=? WHERE id=1",
        (until,)
    )
    con.commit()
    con.close()

    return jsonify({
        "ok": True,
        "unlimited": bool(until),
        "unlimited_until": until
    })

@app.route("/api/admin/withdrawal-unlimited", methods=["GET"])
def admin_withdrawal_unlimited_status():
    expected = os.environ.get("SPIN123_ADMIN_API_KEY")
    supplied = request.headers.get("X-Admin-Key", "")

    if not expected or not secrets.compare_digest(expected, supplied):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    con = db()
    row = con.execute(
        "SELECT unlimited_until FROM withdrawal_settings WHERE id=1"
    ).fetchone()
    con.close()

    until = row[0] if row else ""

    return jsonify({
        "ok": True,
        "unlimited_until": until
    })


@app.route("/finance")
def finance_panel():
    if not session.get("admin"):
        return redirect("/login")

    import html
    con = db()

    # Schema initialized at startup. Keep this GET read-only
    # to avoid SQLite write locks under concurrent requests.

    wallet = con.execute(
        "SELECT balance FROM platform_account WHERE id=1"
    ).fetchone()

    reqs = con.execute("""
        SELECT
            m.id,m.player_id,p.username,m.type,m.amount,m.status,
            m.account_holder,m.account_number,m.ifsc,m.bank_name,
            m.created_at
        FROM money_requests m
        LEFT JOIN players p ON p.id=m.player_id
        ORDER BY m.id DESC
        LIMIT 200
    """).fetchall()

    settlements = con.execute("""
        SELECT id,amount,account_holder,account_number,ifsc,
               bank_name,status,reference,created_at
        FROM admin_settlements
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    con.commit()
    con.close()

    balance = float(wallet[0] if wallet else 0)

    deposits = ""
    withdrawals = ""

    for r in reqs:
        player = html.escape(str(r["username"] or r["player_id"]))
        status = html.escape(str(r["status"]))
        amount = html.escape(str(r["amount"]))

        if r["type"] == "Deposit":
            deposits += (
                "<tr>"
                f"<td>{r['id']}</td>"
                f"<td>{player}</td>"
                f"<td>₹{amount}</td>"
                f"<td>{status}</td>"
                f"<td>{html.escape(str(r['created_at'] or ''))}</td>"
                "</tr>"
            )

        elif r["type"] == "Withdraw":
            withdrawals += (
                "<tr>"
                f"<td>{r['id']}</td>"
                f"<td>{player}</td>"
                f"<td>₹{amount}</td>"
                f"<td>{html.escape(str(r['account_holder'] or ''))}</td>"
                f"<td>{html.escape(str(r['account_number'] or ''))}</td>"
                f"<td>{html.escape(str(r['ifsc'] or ''))}</td>"
                f"<td>{html.escape(str(r['bank_name'] or ''))}</td>"
                f"<td>{status}</td>"
                "</tr>"
            )

    settlement_rows = ""

    for x in settlements:
        settlement_rows += (
            "<tr>"
            f"<td>{x['id']}</td>"
            f"<td>₹{x['amount']}</td>"
            f"<td>{html.escape(str(x['account_holder']))}</td>"
            f"<td>{html.escape(str(x['account_number']))}</td>"
            f"<td>{html.escape(str(x['ifsc']))}</td>"
            f"<td>{html.escape(str(x['bank_name'] or ''))}</td>"
            f"<td>{html.escape(str(x['status']))}</td>"
            f"<td>{html.escape(str(x['reference'] or ''))}</td>"
            "</tr>"
        )

    return page(f"""
    <div class=card>
      <h2>Platform Account</h2>
      <h1>₹{balance:.2f}</h1>
      <p>Platform Ledger Balance</p>

      <form method=post action="/finance/settlement">
        <input type=number min=1 name=amount placeholder="Amount" required>
        <input name=account_holder placeholder="Account Holder Name" required>
        <input name=account_number placeholder="Account Number" required>
        <input name=ifsc placeholder="IFSC" required>
        <input name=bank_name placeholder="Bank Name">
        <button>Create Settlement</button>
      </form>
    </div>

    <div class=card>
      <h2>Player Deposit Requests</h2>
      <div style="overflow:auto">
      <table>
        <tr>
          <th>ID</th><th>Player</th><th>Amount</th>
          <th>Status</th><th>Created</th>
        </tr>
        {deposits}
      </table>
      </div>
    </div>

    <div class=card>
      <h2>Player Withdrawal Requests</h2>
      <div style="overflow:auto">
      <table>
        <tr>
          <th>ID</th><th>Player</th><th>Amount</th>
          <th>Holder</th><th>Account No</th><th>IFSC</th>
          <th>Bank</th><th>Status</th>
        </tr>
        {withdrawals}
      </table>
      </div>
    </div>

    <div class=card>
      <h2>Platform Settlement History</h2>
      <div style="overflow:auto">
      <table>
        <tr>
          <th>ID</th><th>Amount</th><th>Holder</th>
          <th>Account No</th><th>IFSC</th><th>Bank</th>
          <th>Status</th><th>Reference</th>
        </tr>
        {settlement_rows}
      </table>
      </div>
    </div>
    """)


@app.route("/finance/settlement", methods=["POST"])
def finance_settlement():
    if not session.get("admin"):
        return redirect("/login")

    try:
        amount = float(request.form.get("amount", 0))
    except:
        amount = 0

    holder = request.form.get("account_holder", "").strip()
    account = request.form.get("account_number", "").strip()
    ifsc = request.form.get("ifsc", "").strip().upper()
    bank = request.form.get("bank_name", "").strip()

    if amount <= 0 or not holder or not account or not ifsc:
        return page("<div class=card>Invalid settlement details</div>")

    con = db()

    row = con.execute(
        "SELECT balance FROM platform_account WHERE id=1"
    ).fetchone()

    balance = float(row[0] if row else 0)

    if amount > balance:
        con.close()
        return page(
            f"<div class=card>Insufficient Platform Balance: ₹{balance:.2f}</div>"
        )

    import time
    ref = "SET-" + str(int(time.time()))

    con.execute("""
        INSERT INTO admin_settlements(
            amount,account_holder,account_number,ifsc,
            bank_name,status,reference
        )
        VALUES(?,?,?,?,?,'Pending',?)
    """,(amount,holder,account,ifsc,bank,ref))

    con.execute(
        "UPDATE platform_account SET balance=balance-? WHERE id=1",
        (amount,)
    )

    con.commit()
    con.close()

    return redirect("/finance")



# ===== SPIN777 LEGACY / PROBE BRIDGE =====
# Safe compatibility layer for an authorized legacy client.
# It does not bypass TLS, DNS, authentication, or a third-party server.
import json as _legacy_json
from datetime import datetime as _legacy_datetime

def _legacy_probe_enabled():
    return os.environ.get("LEGACY_PROBE", "1").lower() in ("1", "true", "yes", "on")

def _legacy_ensure_tables():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS legacy_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method TEXT,
            path TEXT,
            query TEXT,
            content_type TEXT,
            body TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

def _legacy_payload_body():
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    data = {}
    # Form fields are useful for old clients that don't send JSON.
    for k in request.form.keys():
        data[k] = request.form.get(k)
    return data

def _legacy_log_request():
    if not _legacy_probe_enabled():
        return
    try:
        _legacy_ensure_tables()
        body = _legacy_payload_body()
        safe = {}
        # Never store passwords, tokens, cookies, card/account numbers, or auth secrets.
        sensitive = {
            "password","pass","pwd","token","authorization","cookie",
            "accountnumber","account_number","cardno","card_no","ifsc",
            "upi","upi_id"
        }
        for k, v in body.items():
            if str(k).lower() in sensitive:
                safe[k] = "[REDACTED]"
            else:
                s = str(v)
                safe[k] = s[:500]
        con = db()
        con.execute(
            """INSERT INTO legacy_requests(method,path,query,content_type,body)
               VALUES(?,?,?,?,?)""",
            (
                request.method,
                request.path,
                request.query_string.decode("utf-8", "ignore")[:2000],
                request.headers.get("Content-Type","")[:200],
                _legacy_json.dumps(safe, ensure_ascii=False)[:8000],
            )
        )
        con.commit()
        con.close()
    except Exception:
        pass

def _legacy_player_from_token():
    # Reuse the existing bearer-token auth first.
    try:
        return api_player()
    except Exception:
        return None

def _legacy_public_player(row):
    if not row:
        return None
    return {
        "userId": row["id"],
        "uid": row["id"],
        "id": row["id"],
        "name": row["username"],
        "nickname": row["username"],
        "username": row["username"],
        "balance": float(row["balance"] or 0),
        "money": float(row["balance"] or 0),
        "wallet": float(row["balance"] or 0),
        "vip": row["vip"],
        "status": row["status"],
    }

def _legacy_success(row=None, extra=None, msg="success"):
    data = _legacy_public_player(row) if row is not None else {}
    if extra:
        if data is None:
            data = {}
        data.update(extra)
    return jsonify({"ok": True, "code": 0, "msg": msg, "data": data})

@app.route("/api/health", methods=["GET"])
def legacy_health():
    return jsonify({
        "ok": True,
        "service": "spin123-admin",
        "bridge": "legacy-ready",
        "probe": _legacy_probe_enabled(),
        "time": _legacy_datetime.utcnow().isoformat() + "Z",
    })

@app.route("/legacy/login", methods=["POST"])
@app.route("/user/login", methods=["POST"])
def legacy_login_alias():
    _legacy_log_request()
    # The existing /api/login is the canonical authentication implementation.
    return api_login()

@app.route("/legacy/profile", methods=["GET","POST"])
@app.route("/user/info", methods=["GET","POST"])
def legacy_profile_alias():
    _legacy_log_request()
    player = _legacy_player_from_token()
    if not player:
        return jsonify({"ok": False, "code": 401, "msg": "Unauthorized"}), 401
    return _legacy_success(player)

@app.route("/wallet", methods=["GET","POST"])
@app.route("/balance", methods=["GET","POST"])
@app.route("/legacy/wallet", methods=["GET","POST"])
def legacy_wallet_alias():
    _legacy_log_request()
    player = _legacy_player_from_token()
    if not player:
        return jsonify({"ok": False, "code": 401, "msg": "Unauthorized"}), 401
    return _legacy_success(player, {
        "balance": float(player["balance"] or 0),
        "money": float(player["balance"] or 0),
        "wallet": float(player["balance"] or 0),
    })

@app.route("/deposit", methods=["POST"])
@app.route("/recharge", methods=["POST"])
@app.route("/legacy/deposit", methods=["POST"])
def legacy_deposit_alias():
    _legacy_log_request()
    # Existing handler already validates bearer auth and amount.
    return api_deposit_request()

@app.route("/withdraw", methods=["POST"])
@app.route("/legacy/withdraw", methods=["POST"])
def legacy_withdraw_alias():
    _legacy_log_request()
    # Existing handler already validates bearer auth and bank fields.
    return api_withdraw_request()

@app.route("/transaction", methods=["GET"])
@app.route("/record", methods=["GET"])
@app.route("/legacy/history", methods=["GET"])
def legacy_history_alias():
    _legacy_log_request()
    player = _legacy_player_from_token()
    if not player:
        return jsonify({"ok": False, "code": 401, "msg": "Unauthorized"}), 401
    con = db()
    rows = con.execute(
        """SELECT id,type,amount,status,reference,created_at
           FROM wallet_transactions WHERE player_id=?
           ORDER BY id DESC LIMIT 200""",
        (player["id"],)
    ).fetchall()
    con.close()
    return jsonify({
        "ok": True, "code": 0, "msg": "success",
        "data": [dict(x) for x in rows]
    })

@app.route("/api/admin/legacy-requests", methods=["GET"])
def legacy_admin_requests():
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    _legacy_ensure_tables()
    con = db()
    rows = con.execute(
        """SELECT id,method,path,query,content_type,body,created_at
           FROM legacy_requests ORDER BY id DESC LIMIT 500"""
    ).fetchall()
    con.close()
    return jsonify({"ok": True, "requests": [dict(x) for x in rows]})


# ===== SPIN123 FINAL FINANCE / VIP / PLATFORM EXTENSION =====
def _spin123_final_init():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS platform_account(
        id INTEGER PRIMARY KEY CHECK(id=1),
        balance REAL NOT NULL DEFAULT 0
    );
    INSERT OR IGNORE INTO platform_account(id,balance) VALUES(1,0);

    CREATE TABLE IF NOT EXISTS platform_ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        balance_after REAL NOT NULL,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS pool_ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_pool REAL NOT NULL,
        player_share REAL NOT NULL,
        platform_share REAL NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    con.commit()
    con.close()

_spin123_final_init()

@app.route("/api/refund", methods=["POST"])
@app.route("/refund", methods=["POST"])
@app.route("/legacy/refund", methods=["POST"])
def spin123_refund_request():
    player = api_player()
    if not player:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form or {}
    try:
        amount = int(data.get("amount", 0))
    except Exception:
        amount = 0
    if amount <= 0:
        return jsonify({"ok": False, "error": "Invalid amount"}), 400
    con = db()
    cur = con.execute(
        """INSERT INTO money_requests(player_id,type,amount,status)
           VALUES(?,'Refund',?,'Pending')""",
        (player["id"], amount)
    )
    con.commit()
    rid = cur.lastrowid
    con.close()
    return jsonify({"ok": True, "request_id": rid, "type": "Refund", "status": "Pending"})

@app.route("/api/admin/refund/<int:req_id>/approve", methods=["POST"])
def spin123_refund_approve(req_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    con = db()
    row = con.execute(
        """SELECT id,player_id,amount,status FROM money_requests
           WHERE id=? AND type='Refund'""", (req_id,)
    ).fetchone()
    if not row:
        con.close()
        return jsonify({"ok": False, "error": "Refund request not found"}), 404
    if row["status"] != "Pending":
        con.close()
        return jsonify({"ok": False, "error": "Already processed"}), 400

    con.execute("UPDATE money_requests SET status='Approved' WHERE id=?", (req_id,))
    con.execute("UPDATE players SET balance=balance+? WHERE id=?", (row["amount"], row["player_id"]))
    try:
        con.execute(
            """INSERT INTO wallet_transactions(player_id,type,amount,status,reference)
               VALUES(?,'Refund',?,'Approved',?)""",
            (row["player_id"], row["amount"], f"REFUND-{req_id}")
        )
    except Exception:
        pass
    con.commit()
    con.close()
    return jsonify({"ok": True, "request_id": req_id, "status": "Approved"})

@app.route("/api/admin/refund/<int:req_id>/reject", methods=["POST"])
def spin123_refund_reject(req_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    con = db()
    con.execute(
        """UPDATE money_requests SET status='Rejected'
           WHERE id=? AND type='Refund' AND status='Pending'""", (req_id,)
    )
    con.commit()
    con.close()
    return jsonify({"ok": True, "request_id": req_id, "status": "Rejected"})

@app.route("/api/vip", methods=["GET"])
@app.route("/vip", methods=["GET"])
@app.route("/legacy/vip", methods=["GET"])
def spin123_vip():
    player = api_player()
    if not player:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return jsonify({
        "ok": True,
        "vip": player["vip"],
        "level": player["vip"],
        "player_id": player["id"]
    })

@app.route("/api/admin/player/<int:player_id>/vip", methods=["POST"])
def spin123_set_vip(player_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form or {}
    vip = str(data.get("vip", "Normal")).strip() or "Normal"
    con = db()
    con.execute("UPDATE players SET vip=? WHERE id=?", (vip, player_id))
    con.commit()
    con.close()
    return jsonify({"ok": True, "player_id": player_id, "vip": vip})

@app.route("/payment-config", methods=["GET"])
@app.route("/legacy/payment-config", methods=["GET"])
@app.route("/legacy/payment-settings", methods=["GET"])
def spin123_payment_config():
    return api_payment_settings()

@app.route("/api/admin/pool/split", methods=["POST"])
def spin123_pool_split():
    """Transparent accounting only: 60% player pool, 40% platform share."""
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form or {}
    try:
        total = float(data.get("total_pool", 0))
    except Exception:
        total = 0
    if total < 0:
        return jsonify({"ok": False, "error": "Invalid total_pool"}), 400

    player_share = round(total * 0.60, 2)
    platform_share = round(total * 0.40, 2)

    con = db()
    con.execute(
        "INSERT INTO pool_ledger(total_pool,player_share,platform_share) VALUES(?,?,?)",
        (total, player_share, platform_share)
    )
    con.execute("UPDATE platform_account SET balance=balance+? WHERE id=1", (platform_share,))
    bal = con.execute("SELECT balance FROM platform_account WHERE id=1").fetchone()[0]
    con.execute(
        """INSERT INTO platform_ledger(type,amount,balance_after,note)
           VALUES('PoolShare',?,?,?)""",
        (platform_share, bal, f"40% platform share from pool {total}")
    )
    con.commit()
    con.close()
    return jsonify({
        "ok": True,
        "total_pool": total,
        "player_share_60": player_share,
        "platform_share_40": platform_share,
        "platform_balance": bal
    })

@app.route("/api/admin/platform-account", methods=["GET"])
def spin123_platform_account():
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    con = db()
    bal = con.execute("SELECT balance FROM platform_account WHERE id=1").fetchone()[0]
    rows = con.execute(
        """SELECT id,type,amount,balance_after,note,created_at
           FROM platform_ledger ORDER BY id DESC LIMIT 200"""
    ).fetchall()
    con.close()
    return jsonify({"ok": True, "balance": bal, "ledger": [dict(r) for r in rows]})

@app.route("/api/admin/platform-withdraw", methods=["POST"])
def spin123_platform_withdraw():
    """Admin platform balance may intentionally go negative; ledger always records it."""
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form or {}
    try:
        amount = float(data.get("amount", 0))
    except Exception:
        amount = 0
    if amount <= 0:
        return jsonify({"ok": False, "error": "Invalid amount"}), 400

    note = str(data.get("note", "")).strip()
    con = db()
    con.execute("UPDATE platform_account SET balance=balance-? WHERE id=1", (amount,))
    bal = con.execute("SELECT balance FROM platform_account WHERE id=1").fetchone()[0]
    con.execute(
        """INSERT INTO platform_ledger(type,amount,balance_after,note)
           VALUES('AdminWithdraw',?,?,?)""",
        (-amount, bal, note)
    )
    con.commit()
    con.close()
    return jsonify({"ok": True, "withdrawn": amount, "platform_balance": bal})

@app.route("/api/admin/pool/history", methods=["GET"])
def spin123_pool_history():
    if not session.get("admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    con = db()
    rows = con.execute(
        """SELECT id,total_pool,player_share,platform_share,created_at
           FROM pool_ledger ORDER BY id DESC LIMIT 200"""
    ).fetchall()
    con.close()
    return jsonify({"ok": True, "rows": [dict(r) for r in rows]})
# ===== END SPIN123 FINAL EXTENSION =====


# Capture only unmatched requests. We keep the original 404 behavior,
# so the probe cannot accidentally make an unsupported API look successful.
@app.errorhandler(404)
def legacy_probe_404(err):
    _legacy_log_request()
    return jsonify({
        "ok": False,
        "code": 404,
        "msg": "route not mapped",
        "path": request.path
    }), 404

_legacy_ensure_tables()
# ===== END LEGACY / PROBE BRIDGE =====

# ===== PLAYERS AUTH SCHEMA MIGRATION =====
def migrate_players_auth_schema():
    con = db()
    cols = {r["name"] for r in con.execute("PRAGMA table_info(players)").fetchall()}

    if "password_hash" not in cols:
        con.execute("ALTER TABLE players ADD COLUMN password_hash TEXT")

    if "token" not in cols:
        con.execute("ALTER TABLE players ADD COLUMN token TEXT")

    if "created_at" not in cols:
        con.execute("ALTER TABLE players ADD COLUMN created_at TEXT")

    con.commit()
    con.close()

migrate_players_auth_schema()
# ===== END PLAYERS AUTH SCHEMA MIGRATION =====


# ===== MONEY REQUESTS SCHEMA FIX =====
def migrate_money_requests():
    con = db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS money_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pending',
            reference TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cols = {
        r["name"]
        for r in con.execute("PRAGMA table_info(money_requests)").fetchall()
    }

    if "reference" not in cols:
        con.execute(
            "ALTER TABLE money_requests ADD COLUMN reference TEXT DEFAULT ''"
        )

    if "created_at" not in cols:
        con.execute(
            "ALTER TABLE money_requests ADD COLUMN created_at TEXT"
        )

    con.commit()
    con.close()

migrate_money_requests()
# ===== END MONEY REQUESTS SCHEMA FIX =====


# ===== FINANCE PAGE SCHEMA FIX =====
def migrate_finance_schema():
    con = db()

    # money_requests के Finance/Withdraw fields
    con.execute("""
        CREATE TABLE IF NOT EXISTS money_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pending',
            reference TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cols = {
        r["name"]
        for r in con.execute("PRAGMA table_info(money_requests)").fetchall()
    }

    missing = {
        "account_holder": "TEXT DEFAULT ''",
        "account_number": "TEXT DEFAULT ''",
        "ifsc": "TEXT DEFAULT ''",
        "bank_name": "TEXT DEFAULT ''",
        "reference": "TEXT DEFAULT ''",
        "created_at": "TEXT"
    }

    for name, definition in missing.items():
        if name not in cols:
            con.execute(
                f"ALTER TABLE money_requests ADD COLUMN {name} {definition}"
            )

    # Admin/Platform settlement history
    con.execute("""
        CREATE TABLE IF NOT EXISTS admin_settlements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL DEFAULT 0,
            account_holder TEXT DEFAULT '',
            account_number TEXT DEFAULT '',
            ifsc TEXT DEFAULT '',
            bank_name TEXT DEFAULT '',
            status TEXT DEFAULT 'Completed',
            reference TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.commit()
    con.close()

migrate_finance_schema()
# ===== END FINANCE PAGE SCHEMA FIX =====



# ===== SPIN123 COMPLETE PAYMENT FLOW =====
import hmac as _spin_hmac
import hashlib as _spin_hashlib
import time as _spin_time
import json as _spin_json
import urllib.parse as _spin_urlparse
import html as _spin_html

def _spin123_payment_schema_v2():
    con = db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS payment_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE NOT NULL,
        player_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        utr TEXT UNIQUE,
        provider_status TEXT NOT NULL,
        credited INTEGER NOT NULL DEFAULT 0,
        raw_payload TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS admin_direct_credits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cols = {r["name"] for r in con.execute("PRAGMA table_info(money_requests)").fetchall()}
    additions = {
        "utr": "TEXT DEFAULT ''",
        "provider_status": "TEXT DEFAULT 'Pending'",
        "payment_token": "TEXT DEFAULT ''",
        "verified_at": "TEXT DEFAULT ''",
        "provider_event_id": "TEXT DEFAULT ''",
    }
    for name, definition in additions.items():
        if name not in cols:
            con.execute(f"ALTER TABLE money_requests ADD COLUMN {name} {definition}")

    con.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_money_requests_utr
        ON money_requests(utr)
        WHERE utr IS NOT NULL AND trim(utr) <> ''
    """)
    con.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_money_requests_payment_token
        ON money_requests(payment_token)
        WHERE payment_token IS NOT NULL AND trim(payment_token) <> ''
    """)
    con.commit()
    con.close()

_spin123_payment_schema_v2()

def _spin123_webhook_secret():
    return os.environ.get("PAYMENT_WEBHOOK_SECRET", "").encode()

def _spin123_sig_message(data, extended=False):
    fields = [
        str(data.get("event_id", "")),
        str(data.get("user_id", "")),
        str(data.get("amount", "")),
        str(data.get("utr", "")),
        str(data.get("status", "")),
        str(data.get("timestamp", "")),
    ]
    if extended:
        fields.append(str(data.get("request_id", "")))
    return "|".join(fields).encode()

def _spin123_verify_signature(data, supplied):
    secret = _spin123_webhook_secret()
    if not secret or not supplied:
        return False
    candidates = [
        _spin_hmac.new(secret, _spin123_sig_message(data, False), _spin_hashlib.sha256).hexdigest(),
        _spin_hmac.new(secret, _spin123_sig_message(data, True), _spin_hashlib.sha256).hexdigest(),
    ]
    return any(_spin_hmac.compare_digest(x, supplied) for x in candidates)

def _spin123_success_status(status):
    return str(status or "").upper() in {"SUCCESS", "SUCCESSFUL", "PAID", "COMPLETED", "VERIFIED"}

def _spin123_credit_request(con, req, utr, event_id):
    """Credit exactly once. Caller must be inside BEGIN IMMEDIATE transaction."""
    fresh = con.execute(
        "SELECT id,player_id,amount,status,utr FROM money_requests WHERE id=?",
        (req["id"],)
    ).fetchone()
    if not fresh:
        return False, "Request not found"

    if fresh["status"] == "Approved":
        return False, "Already credited"
    if fresh["status"] != "Pending":
        return False, "Request is not pending"

    con.execute(
        "UPDATE players SET balance=balance+? WHERE id=?",
        (fresh["amount"], fresh["player_id"])
    )
    con.execute("""
        UPDATE money_requests
        SET status='Approved',
            utr=?,
            reference=?,
            provider_status='Verified',
            verified_at=CURRENT_TIMESTAMP,
            provider_event_id=?
        WHERE id=? AND status='Pending'
    """, (utr, utr, event_id, fresh["id"]))

    try:
        con.execute("""
            INSERT INTO wallet_transactions(player_id,type,amount,status,reference)
            VALUES(?,'Deposit',?,'Approved',?)
        """, (fresh["player_id"], fresh["amount"], utr))
    except Exception:
        pass
    return True, "Credited"

def _spin123_select_payment_config(amount):
    con = db()
    rr = con.execute("""
        SELECT min_amount,max_amount,upi_id,qr_url,account_name,note
        FROM qr_ranges
        WHERE enabled=1 AND ? BETWEEN min_amount AND max_amount
        ORDER BY min_amount ASC LIMIT 1
    """, (amount,)).fetchone()

    if rr and (rr["upi_id"] or rr["qr_url"]):
        cfg = dict(rr)
    else:
        row = con.execute(
            "SELECT upi_id,qr_url,account_name,note FROM payment_settings WHERE id=1"
        ).fetchone()
        cfg = dict(row) if row else {
            "upi_id":"", "qr_url":"", "account_name":"", "note":""
        }
    con.close()
    return cfg

def _spin123_upi_links(upi_id, account_name, amount, request_id):
    params = {
        "pa": upi_id,
        "pn": account_name or "Spin123",
        "am": f"{float(amount):.2f}",
        "cu": "INR",
        "tn": f"Spin123 Deposit #{request_id}",
        "tr": f"SPIN123-{request_id}",
    }
    query = _spin_urlparse.urlencode(params)
    upi_uri = "upi://pay?" + query

    def intent(package_name):
        return (
            "intent://pay?" + query +
            "#Intent;scheme=upi;package=" + package_name + ";end"
        )

    return {
        "upi_uri": upi_uri,
        "google_pay": intent("com.google.android.apps.nbu.paisa.user"),
        "phonepe": intent("com.phonepe.app"),
        "paytm": intent("net.one97.paytm"),
    }

def _spin123_validate_utr(utr):
    utr = str(utr or "").strip().upper()
    if not (6 <= len(utr) <= 40):
        return ""
    if not all(c.isalnum() or c in "-_" for c in utr):
        return ""
    return utr

@app.route("/api/deposit/prepare", methods=["POST"])
def spin123_deposit_prepare():
    player = api_player()
    if not player:
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    data = request.get_json(silent=True) or request.form or {}
    try:
        amount = int(data.get("amount", 0))
    except Exception:
        amount = 0
    if amount <= 0:
        return jsonify({"ok":False,"error":"Invalid amount"}),400

    cfg = _spin123_select_payment_config(amount)
    if not cfg.get("upi_id") and not cfg.get("qr_url"):
        return jsonify({"ok":False,"error":"Payment QR/UPI is not configured"}),503

    token = secrets.token_urlsafe(24)
    con = db()
    cur = con.execute("""
        INSERT INTO money_requests(
            player_id,type,amount,status,reference,utr,
            provider_status,payment_token
        )
        VALUES(?,'Deposit',?,'Pending','','','Pending',?)
    """, (player["id"], amount, token))
    request_id = cur.lastrowid
    con.commit()
    con.close()

    links = _spin123_upi_links(
        cfg.get("upi_id",""),
        cfg.get("account_name",""),
        amount,
        request_id
    )
    payment_url = request.host_url.rstrip("/") + "/pay/" + token

    return jsonify({
        "ok": True,
        "request_id": request_id,
        "status": "Pending",
        "payment_url": payment_url,
        "amount": amount,
        "upi_id": cfg.get("upi_id",""),
        "account_name": cfg.get("account_name",""),
        "qr_url": cfg.get("qr_url",""),
        "note": cfg.get("note",""),
        "upi": links
    })

def _spin123_submit_utr_for_request(req_id, player_id, utr):
    utr = _spin123_validate_utr(utr)
    if not utr:
        return {"ok":False,"error":"Invalid UTR"},400

    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        req = con.execute("""
            SELECT id,player_id,amount,status,utr
            FROM money_requests
            WHERE id=? AND type='Deposit'
        """, (req_id,)).fetchone()

        if not req or int(req["player_id"]) != int(player_id):
            con.rollback(); con.close()
            return {"ok":False,"error":"Deposit request not found"},404

        if req["status"] == "Approved":
            bal = con.execute("SELECT balance FROM players WHERE id=?", (player_id,)).fetchone()[0]
            con.rollback(); con.close()
            return {"ok":True,"status":"Approved","credited":True,"balance":bal},200

        duplicate = con.execute("""
            SELECT id,player_id FROM money_requests
            WHERE utr=? AND id<>?
        """, (utr, req_id)).fetchone()
        if duplicate:
            con.rollback(); con.close()
            return {"ok":False,"error":"UTR already used"},409

        con.execute("""
            UPDATE money_requests
            SET utr=?, reference=?, provider_status='Pending'
            WHERE id=?
        """, (utr, utr, req_id))

        event = con.execute("""
            SELECT id,event_id,player_id,amount,provider_status,credited
            FROM payment_events
            WHERE utr=?
        """, (utr,)).fetchone()

        credited = False
        if (event and _spin123_success_status(event["provider_status"])
                and int(event["player_id"]) == int(player_id)
                and float(event["amount"]) == float(req["amount"])):
            credited, _ = _spin123_credit_request(con, req, utr, event["event_id"])
            if credited:
                con.execute("UPDATE payment_events SET credited=1 WHERE id=?", (event["id"],))

        con.commit()
        bal = con.execute("SELECT balance FROM players WHERE id=?", (player_id,)).fetchone()[0]
        state = con.execute(
            "SELECT status,provider_status FROM money_requests WHERE id=?",
            (req_id,)
        ).fetchone()
        con.close()

        return {
            "ok":True,
            "request_id":req_id,
            "utr":utr,
            "status":state["status"],
            "provider_status":state["provider_status"],
            "credited":bool(credited),
            "balance":bal
        },200
    except sqlite3.IntegrityError:
        con.rollback(); con.close()
        return {"ok":False,"error":"UTR already used"},409
    except Exception as e:
        con.rollback(); con.close()
        return {"ok":False,"error":str(e)},500

@app.route("/api/deposit/<int:req_id>/utr", methods=["POST"])
def spin123_submit_utr(req_id):
    player = api_player()
    if not player:
        return jsonify({"ok":False,"error":"Unauthorized"}),401
    data = request.get_json(silent=True) or request.form or {}
    result, code = _spin123_submit_utr_for_request(req_id, player["id"], data.get("utr",""))
    return jsonify(result), code

@app.route("/api/deposit/<int:req_id>/status", methods=["GET"])
def spin123_deposit_status(req_id):
    player = api_player()
    if not player:
        return jsonify({"ok":False,"error":"Unauthorized"}),401
    con = db()
    row = con.execute("""
        SELECT id,amount,status,utr,provider_status,verified_at
        FROM money_requests WHERE id=? AND player_id=? AND type='Deposit'
    """, (req_id, player["id"])).fetchone()
    con.close()
    if not row:
        return jsonify({"ok":False,"error":"Deposit request not found"}),404
    return jsonify({"ok":True, **dict(row)})

@app.route("/pay/<token>", methods=["GET"])
def spin123_payment_page(token):
    con = db()
    req = con.execute("""
        SELECT m.id,m.player_id,m.amount,m.status,m.utr,m.provider_status,
               p.username
        FROM money_requests m
        LEFT JOIN players p ON p.id=m.player_id
        WHERE m.payment_token=? AND m.type='Deposit'
    """, (token,)).fetchone()
    con.close()
    if not req:
        return page("<div class=card>Payment request not found.</div>"),404

    cfg = _spin123_select_payment_config(req["amount"])
    links = _spin123_upi_links(
        cfg.get("upi_id",""),
        cfg.get("account_name",""),
        req["amount"],
        req["id"]
    )
    qr = cfg.get("qr_url","")
    qr_html = (
        f'<img src="{_spin_html.escape(qr, quote=True)}" '
        'style="width:240px;max-width:85%;border-radius:14px;background:white;padding:8px">'
        if qr else ""
    )
    safe_upi = _spin_html.escape(cfg.get("upi_id",""))
    safe_name = _spin_html.escape(cfg.get("account_name",""))
    safe_token = _spin_html.escape(token, quote=True)
    safe_gpay = _spin_html.escape(links["google_pay"], quote=True)
    safe_phonepe = _spin_html.escape(links["phonepe"], quote=True)
    safe_paytm = _spin_html.escape(links["paytm"], quote=True)
    safe_upi_uri = _spin_html.escape(links["upi_uri"], quote=True)

    return page(f"""
    <div class=card style="text-align:center">
      <h2>Deposit ₹{req['amount']}</h2>
      <p>User: {_spin_html.escape(str(req['username'] or req['player_id']))}</p>
      {qr_html}
      <p><b>{safe_name}</b><br>{safe_upi}</p>

      <a href="{safe_gpay}"><button>Google Pay</button></a>
      <a href="{safe_phonepe}"><button>PhonePe</button></a>
      <a href="{safe_paytm}"><button>Paytm</button></a>
      <br>
      <a href="{safe_upi_uri}"><button>Other UPI App</button></a>

      <hr style="margin:18px 0;border-color:#24364d">
      <p>Payment complete होने के बाद UTR डालें.</p>
      <form method=post action="/pay/{safe_token}/utr">
        <input name=utr placeholder="UTR / Transaction ID" required>
        <button>Verify Payment</button>
      </form>
      <p id=status>Current status: {_spin_html.escape(str(req['status']))}</p>
    </div>
    <script>
    async function refreshStatus(){{
      try {{
        const r=await fetch("/pay/{safe_token}/status");
        const j=await r.json();
        if(j.ok){{
          document.getElementById("status").innerText =
            "Status: " + j.status + " / " + j.provider_status;
          if(j.status==="Approved"){{
            document.getElementById("status").innerText =
              "✅ Payment Successful - Wallet credited";
          }}
        }}
      }} catch(e) {{}}
    }}
    document.addEventListener("visibilitychange",()=>{{
      if(!document.hidden) refreshStatus();
    }});
    setInterval(refreshStatus,5000);
    </script>
    """)

@app.route("/pay/<token>/utr", methods=["POST"])
def spin123_payment_page_submit_utr(token):
    con = db()
    req = con.execute(
        "SELECT id,player_id FROM money_requests WHERE payment_token=? AND type='Deposit'",
        (token,)
    ).fetchone()
    con.close()
    if not req:
        return page("<div class=card>Payment request not found.</div>"),404

    result, code = _spin123_submit_utr_for_request(
        req["id"], req["player_id"], request.form.get("utr","")
    )
    if result.get("credited"):
        msg = "✅ Payment verified. Wallet credited successfully."
    elif result.get("ok"):
        msg = "⏳ UTR saved. Provider verification pending."
    else:
        msg = "❌ " + _spin_html.escape(str(result.get("error","Request failed")))
    return page(
        f'<div class=card><h3>{msg}</h3>'
        f'<a href="/pay/{_spin_html.escape(token, quote=True)}"><button>Back</button></a></div>'
    ), code

@app.route("/pay/<token>/status", methods=["GET"])
def spin123_payment_page_status(token):
    con = db()
    row = con.execute("""
        SELECT id,amount,status,provider_status,verified_at
        FROM money_requests WHERE payment_token=? AND type='Deposit'
    """, (token,)).fetchone()
    con.close()
    if not row:
        return jsonify({"ok":False,"error":"Not found"}),404
    return jsonify({"ok":True, **dict(row)})

@app.route("/api/payment/webhook", methods=["POST"])
def spin123_payment_webhook():
    data = request.get_json(silent=True) or {}
    sig = request.headers.get("X-Spin123-Signature", "").strip()

    if not _spin123_verify_signature(data, sig):
        return jsonify({"ok":False,"error":"Invalid webhook signature"}),401

    try:
        event_id = str(data["event_id"]).strip()
        player_id = int(data["user_id"])
        amount = float(data["amount"])
        utr = _spin123_validate_utr(data.get("utr",""))
        status = str(data.get("status","")).strip().upper()
        ts = int(data.get("timestamp",0))
        request_id = int(data.get("request_id",0) or 0)
    except Exception:
        return jsonify({"ok":False,"error":"Invalid payload"}),400

    if not event_id or amount <= 0 or not utr:
        return jsonify({"ok":False,"error":"Missing/invalid event_id, amount or UTR"}),400
    if ts and abs(int(_spin_time.time()) - ts) > 900:
        return jsonify({"ok":False,"error":"Stale webhook"}),400

    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")

        existing = con.execute(
            "SELECT id,credited,provider_status FROM payment_events WHERE event_id=? OR utr=?",
            (event_id, utr)
        ).fetchone()
        if existing:
            con.rollback(); con.close()
            return jsonify({
                "ok":True,
                "duplicate":True,
                "credited":bool(existing["credited"]),
                "status":existing["provider_status"]
            })

        player = con.execute("SELECT id FROM players WHERE id=?", (player_id,)).fetchone()
        if not player:
            con.rollback(); con.close()
            return jsonify({"ok":False,"error":"Unknown user_id"}),404

        con.execute("""
            INSERT INTO payment_events(
                event_id,player_id,amount,utr,provider_status,credited,raw_payload
            ) VALUES(?,?,?,?,?,?,?)
        """, (
            event_id, player_id, amount, utr, status, 0,
            _spin_json.dumps(data, separators=(",",":"))
        ))

        req = None
        if request_id:
            req = con.execute("""
                SELECT id,player_id,amount,status,utr
                FROM money_requests
                WHERE id=? AND type='Deposit' AND player_id=? AND amount=?
            """, (request_id, player_id, amount)).fetchone()

        if not req:
            req = con.execute("""
                SELECT id,player_id,amount,status,utr
                FROM money_requests
                WHERE type='Deposit' AND player_id=? AND amount=? AND utr=?
                ORDER BY id DESC LIMIT 1
            """, (player_id, amount, utr)).fetchone()

        if not req:
            candidates = con.execute("""
                SELECT id,player_id,amount,status,utr
                FROM money_requests
                WHERE type='Deposit' AND player_id=? AND amount=? AND status='Pending'
                ORDER BY id DESC LIMIT 2
            """, (player_id, amount)).fetchall()
            if len(candidates) == 1:
                req = candidates[0]

        credited = False
        if req and _spin123_success_status(status):
            credited, _ = _spin123_credit_request(con, req, utr, event_id)
            if credited:
                con.execute(
                    "UPDATE payment_events SET credited=1 WHERE event_id=?",
                    (event_id,)
                )
        elif req:
            con.execute("""
                UPDATE money_requests
                SET utr=?,reference=?,provider_status=?
                WHERE id=? AND status='Pending'
            """, (utr, utr, status or "Pending", req["id"]))

        con.commit()
        bal = con.execute("SELECT balance FROM players WHERE id=?", (player_id,)).fetchone()[0]
        con.close()
        return jsonify({
            "ok":True,
            "event_id":event_id,
            "user_id":player_id,
            "utr":utr,
            "provider_status":status,
            "matched_request_id": req["id"] if req else None,
            "credited":bool(credited),
            "balance":bal
        })
    except sqlite3.IntegrityError:
        con.rollback(); con.close()
        return jsonify({"ok":True,"duplicate":True,"credited":False}),200
    except Exception as e:
        con.rollback(); con.close()
        return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/admin/direct-credit", methods=["POST"])
def spin123_admin_direct_credit():
    if not session.get("admin"):
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    data = request.get_json(silent=True) or request.form or {}
    try:
        player_id = int(data.get("user_id",0))
        amount = float(data.get("amount",0))
    except Exception:
        return jsonify({"ok":False,"error":"Invalid user_id/amount"}),400

    note = str(data.get("note","")).strip()
    if player_id <= 0 or amount <= 0:
        return jsonify({"ok":False,"error":"Invalid user_id/amount"}),400

    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        player = con.execute(
            "SELECT id,username,balance FROM players WHERE id=?",
            (player_id,)
        ).fetchone()
        if not player:
            con.rollback(); con.close()
            return jsonify({"ok":False,"error":"Player not found"}),404

        con.execute("UPDATE players SET balance=balance+? WHERE id=?", (amount, player_id))
        con.execute("UPDATE platform_account SET balance=balance-? WHERE id=1", (amount,))
        platform_balance = con.execute(
            "SELECT balance FROM platform_account WHERE id=1"
        ).fetchone()[0]

        con.execute(
            "INSERT INTO admin_direct_credits(player_id,amount,note) VALUES(?,?,?)",
            (player_id, amount, note)
        )
        con.execute("""
            INSERT INTO platform_ledger(type,amount,balance_after,note)
            VALUES('DirectPlayerCredit',?,?,?)
        """, (-amount, platform_balance, note or f"Direct credit to player {player_id}"))
        try:
            con.execute("""
                INSERT INTO wallet_transactions(player_id,type,amount,status,reference)
                VALUES(?,'AdminCredit',?,'Approved',?)
            """, (player_id, amount, note or "ADMIN-DIRECT-CREDIT"))
        except Exception:
            pass

        con.commit()
        balance = con.execute(
            "SELECT balance FROM players WHERE id=?", (player_id,)
        ).fetchone()[0]
        con.close()
        return jsonify({
            "ok":True,
            "user_id":player_id,
            "credited":amount,
            "balance":balance,
            "platform_balance":platform_balance
        })
    except Exception as e:
        con.rollback(); con.close()
        return jsonify({"ok":False,"error":str(e)}),500

@app.route("/admin/direct-credit", methods=["GET","POST"])
def spin123_admin_direct_credit_page():
    if not session.get("admin"):
        return redirect("/login")

    message = ""
    if request.method == "POST":
        data = request.form
        try:
            player_id = int(data.get("user_id",0))
            amount = float(data.get("amount",0))
        except Exception:
            player_id, amount = 0, 0

        note = str(data.get("note","")).strip()
        if player_id > 0 and amount > 0:
            con = db()
            try:
                con.execute("BEGIN IMMEDIATE")
                player = con.execute(
                    "SELECT id,username FROM players WHERE id=?", (player_id,)
                ).fetchone()
                if not player:
                    message = "❌ Player not found"
                    con.rollback()
                else:
                    con.execute("UPDATE players SET balance=balance+? WHERE id=?", (amount,player_id))
                    con.execute("UPDATE platform_account SET balance=balance-? WHERE id=1",(amount,))
                    pbal = con.execute("SELECT balance FROM platform_account WHERE id=1").fetchone()[0]
                    con.execute(
                        "INSERT INTO admin_direct_credits(player_id,amount,note) VALUES(?,?,?)",
                        (player_id,amount,note)
                    )
                    con.execute("""
                        INSERT INTO platform_ledger(type,amount,balance_after,note)
                        VALUES('DirectPlayerCredit',?,?,?)
                    """,(-amount,pbal,note or f"Direct credit to player {player_id}"))
                    try:
                        con.execute("""
                            INSERT INTO wallet_transactions(player_id,type,amount,status,reference)
                            VALUES(?,'AdminCredit',?,'Approved',?)
                        """,(player_id,amount,note or "ADMIN-DIRECT-CREDIT"))
                    except Exception:
                        pass
                    con.commit()
                    message = f"✅ ₹{amount:.2f} credited to User ID {player_id}"
            except Exception as e:
                con.rollback()
                message = "❌ " + _spin_html.escape(str(e))
            finally:
                con.close()
        else:
            message = "❌ Valid User ID and amount required"

    con = db()
    bal = con.execute("SELECT balance FROM platform_account WHERE id=1").fetchone()
    rows = con.execute("""
        SELECT d.id,d.player_id,p.username,d.amount,d.note,d.created_at
        FROM admin_direct_credits d
        LEFT JOIN players p ON p.id=d.player_id
        ORDER BY d.id DESC LIMIT 100
    """).fetchall()
    con.close()

    history = ""
    for r in rows:
        history += (
            f"<tr><td>{r['id']}</td><td>{r['player_id']}</td>"
            f"<td>{_spin_html.escape(str(r['username'] or ''))}</td>"
            f"<td>₹{float(r['amount']):.2f}</td>"
            f"<td>{_spin_html.escape(str(r['note'] or ''))}</td>"
            f"<td>{_spin_html.escape(str(r['created_at'] or ''))}</td></tr>"
        )

    return page(f"""
      <div class=card>
        <h2>Admin Direct User Credit</h2>
        <p>Platform balance: ₹{float(bal[0] if bal else 0):.2f}</p>
        <p>{message}</p>
        <form method=post>
          <input name=user_id type=number min=1 placeholder="User ID" required>
          <input name=amount type=number min=1 step=0.01 placeholder="Amount" required>
          <input name=note placeholder="Note / Reference">
          <button>Credit User Wallet</button>
        </form>
      </div>
      <div class=card>
        <h3>Direct Credit History</h3>
        <div style="overflow:auto"><table>
          <tr><th>ID</th><th>User ID</th><th>Player</th><th>Amount</th><th>Note</th><th>Created</th></tr>
          {history}
        </table></div>
      </div>
    """)

@app.route("/api/admin/payment-events", methods=["GET"])
def spin123_admin_payment_events():
    if not session.get("admin"):
        return jsonify({"ok":False,"error":"Unauthorized"}),401
    con = db()
    rows = con.execute("""
        SELECT id,event_id,player_id,amount,utr,provider_status,credited,created_at
        FROM payment_events ORDER BY id DESC LIMIT 500
    """).fetchall()
    con.close()
    return jsonify({"ok":True,"rows":[dict(r) for r in rows]})
# ===== END SPIN123 COMPLETE PAYMENT FLOW =====




# ===== SPIN123 COMPLETE PLAYER <-> ADMIN SUPPORT CHAT =====
from werkzeug.utils import secure_filename
from flask import send_from_directory
import uuid as _support_uuid
import html as _support_html

SUPPORT_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "support_uploads")
os.makedirs(SUPPORT_UPLOAD_DIR, exist_ok=True)
SUPPORT_ALLOWED_EXT = {"png","jpg","jpeg","webp","pdf","txt","doc","docx","xls","xlsx"}
SUPPORT_MAX_FILE = 5 * 1024 * 1024

def _support_init():
    con=db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS support_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        sender TEXT NOT NULL,
        topic TEXT DEFAULT 'Other',
        request_ref TEXT DEFAULT '',
        utr TEXT DEFAULT '',
        amount REAL,
        message TEXT DEFAULT '',
        attachment_name TEXT DEFAULT '',
        attachment_path TEXT DEFAULT '',
        attachment_mime TEXT DEFAULT '',
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_support_player_id ON support_messages(player_id,id);
    """)
    con.commit(); con.close()

_support_init()

def _support_save_upload(file_obj):
    if not file_obj or not getattr(file_obj, "filename", ""):
        return "", "", ""
    original = secure_filename(file_obj.filename)
    if not original or "." not in original:
        raise ValueError("Unsupported attachment")
    ext = original.rsplit(".",1)[1].lower()
    if ext not in SUPPORT_ALLOWED_EXT:
        raise ValueError("Unsupported attachment type")
    data = file_obj.read(SUPPORT_MAX_FILE + 1)
    if len(data) > SUPPORT_MAX_FILE:
        raise ValueError("Attachment maximum 5 MB")
    stored = f"{_support_uuid.uuid4().hex}.{ext}"
    path = os.path.join(SUPPORT_UPLOAD_DIR, stored)
    with open(path, "wb") as f:
        f.write(data)
    return original, stored, (getattr(file_obj, "mimetype", "") or "application/octet-stream")

@app.route("/api/support/messages", methods=["GET","POST"])
def spin123_player_support_messages():
    player=api_player()
    if not player:
        return jsonify({"ok":False,"error":"Unauthorized"}),401

    if request.method=="GET":
        con=db()
        rows=con.execute("""
            SELECT id,sender,topic,request_ref,utr,amount,message,
                   attachment_name,attachment_path,attachment_mime,is_read,created_at
            FROM support_messages WHERE player_id=? ORDER BY id ASC LIMIT 500
        """,(player["id"],)).fetchall()
        con.execute("UPDATE support_messages SET is_read=1 WHERE player_id=? AND sender='admin'",(player["id"],))
        con.commit(); con.close()
        data=[]
        for r in rows:
            x=dict(r)
            x["attachment_url"] = (f"/api/support/attachment/{r['id']}" if r["attachment_path"] else "")
            x.pop("attachment_path",None)
            data.append(x)
        return jsonify({"ok":True,"messages":data})

    payload=request.get_json(silent=True) if request.is_json else request.form
    payload=payload or {}
    topic=str(payload.get("topic","Other")).strip() or "Other"
    allowed_topics={"Deposit","Withdraw","Refund","Wallet","QR/UPI","VIP","Login/Account","Game Issue","Other"}
    if topic not in allowed_topics:
        topic="Other"
    message=str(payload.get("message","")).strip()
    request_ref=str(payload.get("request_ref","")).strip()[:120]
    utr=str(payload.get("utr","")).strip()[:120]
    try:
        amount=float(payload.get("amount")) if str(payload.get("amount","")).strip() else None
    except Exception:
        amount=None

    aname=apath=amime=""
    try:
        if not request.is_json:
            aname,apath,amime=_support_save_upload(request.files.get("attachment"))
    except ValueError as e:
        return jsonify({"ok":False,"error":str(e)}),400

    if not message and not apath:
        return jsonify({"ok":False,"error":"Message or attachment required"}),400

    con=db()
    cur=con.execute("""
        INSERT INTO support_messages(
            player_id,sender,topic,request_ref,utr,amount,message,
            attachment_name,attachment_path,attachment_mime,is_read
        ) VALUES(?,'player',?,?,?,?,?,?,?,?,0)
    """,(player["id"],topic,request_ref,utr,amount,message,aname,apath,amime))
    con.commit(); mid=cur.lastrowid; con.close()
    return jsonify({"ok":True,"message_id":mid,"status":"Sent"})

@app.route("/api/support/attachment/<int:message_id>", methods=["GET"])
def spin123_support_attachment(message_id):
    con=db()
    row=con.execute("SELECT player_id,attachment_name,attachment_path FROM support_messages WHERE id=?",(message_id,)).fetchone()
    con.close()
    if not row or not row["attachment_path"]:
        return jsonify({"ok":False,"error":"Attachment not found"}),404
    player=api_player()
    if not session.get("admin") and (not player or player["id"] != row["player_id"]):
        return jsonify({"ok":False,"error":"Unauthorized"}),401
    return send_from_directory(SUPPORT_UPLOAD_DIR,row["attachment_path"],as_attachment=True,download_name=row["attachment_name"])

@app.route("/support/<int:player_id>", methods=["GET","POST"])
def spin123_admin_support_chat(player_id):
    if not auth():
        return redirect("/login")
    con=db()
    p=con.execute("SELECT id,username FROM players WHERE id=?",(player_id,)).fetchone()
    if not p:
        con.close()
        return page("<div class=card>Player not found.</div>")

    error=""
    if request.method=="POST":
        message=request.form.get("message","").strip()
        topic=request.form.get("topic","Other").strip() or "Other"
        request_ref=request.form.get("request_ref","").strip()[:120]
        utr=request.form.get("utr","").strip()[:120]
        try:
            amount=float(request.form.get("amount")) if request.form.get("amount","").strip() else None
        except Exception:
            amount=None
        aname=apath=amime=""
        try:
            aname,apath,amime=_support_save_upload(request.files.get("attachment"))
        except ValueError as e:
            error=str(e)
        if not error:
            if message or apath:
                con.execute("""
                    INSERT INTO support_messages(
                        player_id,sender,topic,request_ref,utr,amount,message,
                        attachment_name,attachment_path,attachment_mime,is_read
                    ) VALUES(?,'admin',?,?,?,?,?,?,?,?,0)
                """,(player_id,topic,request_ref,utr,amount,message,aname,apath,amime))
                con.commit()
            else:
                error="Message or attachment required"

    con.execute("UPDATE support_messages SET is_read=1 WHERE player_id=? AND sender='player'",(player_id,))
    con.commit()
    rows=con.execute("""
        SELECT * FROM support_messages WHERE player_id=? ORDER BY id ASC LIMIT 500
    """,(player_id,)).fetchall()
    con.close()

    body=f"<div class=card><a href='/support'>← Inbox</a><h2>User ID {p['id']} — {_support_html.escape(str(p['username']))}</h2></div>"
    if error:
        body+=f"<div class=card>{_support_html.escape(error)}</div>"
    body+="<div class=card>"
    for r in rows:
        who="PLAYER" if r["sender"]=="player" else "ADMIN"
        body+=f"<div style='padding:10px;margin:8px 0;background:#0b1728;border-radius:8px'><b>{who} · {_support_html.escape(str(r['topic']))}</b><br>"
        if r["request_ref"]: body+=f"Ref: {_support_html.escape(str(r['request_ref']))}<br>"
        if r["utr"]: body+=f"UTR: {_support_html.escape(str(r['utr']))}<br>"
        if r["amount"] is not None: body+=f"Amount: ₹{r['amount']}<br>"
        if r["message"]: body+=f"{_support_html.escape(str(r['message']))}<br>"
        if r["attachment_path"]:
            body+=f"<a href='/api/support/attachment/{r['id']}'>📎 {_support_html.escape(str(r['attachment_name']))}</a><br>"
        body+=f"<small>{_support_html.escape(str(r['created_at']))}</small></div>"
    body+="</div>"
    body+=f"""
    <div class=card><h3>Reply</h3>
    <form method=post enctype="multipart/form-data">
      <select name=topic>
        <option>Deposit</option><option>Withdraw</option><option>Refund</option>
        <option>Wallet</option><option>QR/UPI</option><option>VIP</option>
        <option>Login/Account</option><option>Game Issue</option><option selected>Other</option>
      </select>
      <input name=request_ref placeholder="Request / Reference ID">
      <input name=utr placeholder="UTR / Transaction ID">
      <input name=amount type=number step=0.01 placeholder="Amount">
      <input name=message placeholder="Reply message">
      <input type=file name=attachment accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.doc,.docx,.xls,.xlsx">
      <button>Send Reply</button>
    </form></div>
    """
    return page(body)

@app.route("/api/admin/support/<int:player_id>/messages", methods=["GET"])
def spin123_admin_support_api(player_id):
    if not auth():
        return jsonify({"ok":False,"error":"Unauthorized"}),401
    con=db()
    rows=con.execute("""
        SELECT id,sender,topic,request_ref,utr,amount,message,
               attachment_name,attachment_mime,is_read,created_at
        FROM support_messages WHERE player_id=? ORDER BY id ASC LIMIT 500
    """,(player_id,)).fetchall()
    con.close()
    return jsonify({"ok":True,"player_id":player_id,"messages":[dict(r) for r in rows]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
