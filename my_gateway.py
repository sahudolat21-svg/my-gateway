import http.server
import socketserver
import json
import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", 8080))
DB_FILE = "payments.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Payments table
    c.execute("""CREATE TABLE IF NOT EXISTS tx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utr TEXT UNIQUE,
        amt TEXT,
        proof TEXT,
        status TEXT DEFAULT 'PENDING',
        dt TEXT
    )""")
    # Settings table
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        val TEXT
    )""")
    # Default settings agar pehle se nahi hai
    c.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('upi_id', '7546982355-1@mbkns')")
    c.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('receiver_name', 'Rupa Kumari')")
    c.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('admin_user', '7546982355')")
    c.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('admin_pass', '7546982355')")
    c.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('owner_user', 'owner7546')")
    c.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('owner_pass', 'owner7546')")
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = sqlite3.connect(DB_FILE)
    r = conn.cursor().execute("SELECT val FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r[0] if r else ""

def set_setting(key, val):
    conn = sqlite3.connect(DB_FILE)
    conn.cursor().execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

def render_pay_page():
    upi_id = get_setting("upi_id")
    name = get_setting("receiver_name")
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>UPI Checkout</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:#0f172a; color:#f8fafc; font-family:sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }}
        .c {{ background:#1e293b; padding:22px; border-radius:16px; max-width:360px; width:100%; text-align:center; border:1px solid #334155; }}
        .amt-box {{ margin:15px 0; text-align:left; }}
        .amt-box label {{ font-size:13px; color:#94a3b8; font-weight:bold; }}
        .amt-input {{ width:100%; padding:14px; margin-top:6px; background:#0f172a; border:2px solid #38bdf8; border-radius:8px; color:#38bdf8; font-size:22px !important; font-weight:bold; text-align:center; }}
        .btn {{ display:block; width:100%; padding:12px; margin:6px 0; border-radius:6px; border:none; color:#fff; font-weight:bold; text-decoration:none; cursor:pointer; font-size:15px; text-align:center; }}
        input {{ width:100%; padding:12px; margin:6px 0 12px 0; background:#0f172a; border:1px solid #475569; border-radius:5px; color:#fff; font-size:16px !important; }}
        .badge {{ margin: 10px auto; padding: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; font-size: 11px; color: #cbd5e1; text-align: left; }}
        #success-modal {{ display:none; background:#064e3b; border:1px solid #10b981; padding:15px; border-radius:10px; margin-top:15px; }}
        #qrcode {{ display:flex; justify-content:center; margin:10px auto; background:#fff; padding:10px; border-radius:8px; width:fit-content; }}
        #step2 {{ display:none; }}
    </style>
</head>
<body>
    <div class="c">
        <h3 style="margin:0;">{name}</h3>
        <div style="color:#94a3b8;font-size:12px;margin-top:4px;">{upi_id}</div>
        
        <div id="step1">
            <div class="amt-box">
                <label>Enter Amount (₹):</label>
                <input type="number" id="amtInput" class="amt-input" placeholder="Enter amount" min="1">
            </div>
            <button class="btn" style="background:#0284c7;font-size:16px;padding:14px;" onclick="proceedToPay()">Proceed to Pay ➔</button>
            <div id="step1-err" style="color:#ef4444;font-size:13px;margin-top:8px;"></div>
        </div>

        <div id="step2">
            <div style="display:flex;justify-content:space-between;align-items:center;margin:12px 0 6px 0;">
                <span id="displayAmt" style="font-size:20px;color:#38bdf8;font-weight:bold;">₹0</span>
                <button onclick="changeAmt()" style="background:transparent;border:1px solid #64748b;color:#94a3b8;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;">Edit Amount</button>
            </div>

            <div id="qrcode"></div>
            <button type="button" onclick="downloadQR()" style="background:#16a34a;color:#fff;border:none;padding:8px 14px;border-radius:5px;margin-top:6px;font-weight:bold;cursor:pointer;">📥 Download QR Code</button>

            <div class="badge">
                <span style="color: #38bdf8; font-weight: bold;">💳 Supported:</span> RuPay Credit Card, Debit Card & UPI Apps
            </div>

            <a id="btnPhonePe" class="btn" style="background:#5f259f;" href="#">Pay via PhonePe</a>
            <a id="btnGPay" class="btn" style="background:#1a73e8;" href="#">Pay via Google Pay</a>
            <a id="btnPaytm" class="btn" style="background:#00b9f1;" href="#">Pay via Paytm</a>

            <div id="form-container" style="border-top:1px solid #334155;margin-top:15px;padding-top:10px;text-align:left;font-size:12px;">
                <label>12-Digit UTR Number:</label>
                <input type="text" id="u" maxlength="12" placeholder="Enter 12-digit UTR">
                
                <label>Payment Proof (Screenshot):</label>
                <input type="file" id="p" accept="image/*">
                
                <button class="btn" style="background:#10b981;" onclick="sendProof()">Submit Proof</button>
                <div id="st" style="margin-top:8px;font-weight:bold;text-align:center;"></div>
            </div>
        </div>

        <div id="success-modal">
            <h2 style="color:#34d399;margin:0 0 8px 0;">🎉 Payment Successful!</h2>
            <p style="margin:0;font-size:13px;color:#e2e8f0;">Aapka payment verify aur approve kar diya gaya hai.</p>
        </div>
    </div>

    <script>
    var upiId = "{upi_id}";
    var name = "{name}";
    var currentAmt = "";

    function proceedToPay() {{
        var amt = document.getElementById('amtInput').value.trim();
        var err = document.getElementById('step1-err');
        if (!amt || parseFloat(amt) <= 0) {{
            err.innerText = "Kripya valid amount daalein!";
            return;
        }}
        err.innerText = "";
        currentAmt = amt;

        document.getElementById('displayAmt').innerText = "₹" + amt;
        var upiUri = "upi://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";

        document.getElementById('btnPhonePe').href = "phonepe://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";
        document.getElementById('btnGPay').href = "tez://upi/pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";
        document.getElementById('btnPaytm').href = "paytmmp://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";

        var qrDiv = document.getElementById('qrcode');
        qrDiv.innerHTML = "";
        new QRCode(qrDiv, {{
            text: upiUri,
            width: 170,
            height: 170,
            correctLevel: QRCode.CorrectLevel.M
        }});

        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';
    }}

    function changeAmt() {{
        document.getElementById('step2').style.display = 'none';
        document.getElementById('step1').style.display = 'block';
    }}

    function downloadQR() {{
        var img = document.querySelector('#qrcode img');
        if (!img || !img.src) return;
        var a = document.createElement('a');
        a.href = img.src;
        a.download = 'upi_qr.png';
        a.click();
    }}

    function sendProof() {{
        var u = document.getElementById('u').value.trim();
        var f = document.getElementById('p').files[0];
        var s = document.getElementById('st');
        if (u.length !== 12) {{
            s.innerHTML = '<span style="color:#ef4444;">12-Digit valid UTR daalein</span>';
            return;
        }}
        if (!f) {{
            s.innerHTML = '<span style="color:#ef4444;">Screenshot chunein</span>';
            return;
        }}
        s.innerHTML = '<span style="color:#38bdf8;">Uploading proof...</span>';
        var reader = new FileReader();
        reader.onload = function() {{
            fetch('/api/submit', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ utr: u, proof: reader.result, amt: currentAmt }})
            }})
            .then(res => res.json())
            .then(d => {{
                if (d.ok) {{
                    s.innerHTML = '<span style="color:#f59e0b;">⏳ Verification Pending... Admin approval ka intezar karein.</span>';
                    setInterval(() => {{
                        fetch('/api/check-status?utr=' + u).then(r => r.json()).then(res => {{
                            if (res.status === 'APPROVED') {{
                                document.getElementById('form-container').style.display = 'none';
                                document.getElementById('success-modal').style.display = 'block';
                            }}
                        }});
                    }}, 3000);
                }} else {{
                    s.innerHTML = '<span style="color:#ef4444;">' + d.msg + '</span>';
                }}
            }});
        }};
        reader.readAsDataURL(f);
    }}
    </script>
</body>
</html>"""

def render_login(title, api_endpoint, target_redirect):
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{title}</title>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:#0f172a; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }}
        .box {{ background:#1e293b; padding:25px; border-radius:12px; width:100%; max-width:320px; text-align:center; border:1px solid #334155; }}
        input {{ width:100%; padding:12px; margin:8px 0; background:#0f172a; border:1px solid #475569; border-radius:5px; color:#fff; font-size:16px !important; }}
        button {{ width:100%; padding:12px; background:#38bdf8; border:none; border-radius:6px; font-weight:bold; cursor:pointer; margin-top:8px; font-size:15px; }}
    </style>
</head>
<body>
    <div class="box">
        <h3>{title}</h3>
        <input type="text" id="user" placeholder="Username / Mobile">
        <input type="password" id="pass" placeholder="Password">
        <button onclick="login()">Login</button>
        <div id="err" style="color:#ef4444;font-size:13px;margin-top:10px;"></div>
    </div>
    <script>
    function login() {{
        var u = document.getElementById('user').value.trim();
        var p = document.getElementById('pass').value.trim();
        fetch('{api_endpoint}', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{user: u, pass: p}})
        }})
        .then(r => r.json())
        .then(d => {{
            if(d.ok) {{
                location.href = '{target_redirect}';
            }} else {{
                document.getElementById('err').innerText = d.msg;
            }}
        }});
    }}
    </script>
</body>
</html>"""

class H(http.server.SimpleHTTPRequestHandler):
    def is_auth(self, role):
        cookies = self.headers.get('Cookie', '')
        return f'{role}_auth=logged_in' in cookies

    def do_GET(self):
        p = urlparse(self.path).path
        
        # 1. USER URL
        if p in ["/", "/pay"]:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_pay_page().encode("utf-8"))

        elif p == "/api/check-status":
            q = urlparse(self.path).query
            utr = ""
            for item in q.split("&"):
                if item.startswith("utr="):
                    utr = item.split("=")[1]
            conn = sqlite3.connect(DB_FILE)
            r = conn.cursor().execute("SELECT status FROM tx WHERE utr=?", (utr,)).fetchone()
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": r[0] if r else "NOT_FOUND"}).encode("utf-8"))

        # 2. ADMIN URL (/admin)
        elif p == "/admin/login":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_login("🛡️ Admin Login", "/api/admin/login", "/admin").encode("utf-8"))

        elif p == "/admin":
            if not self.is_auth("admin") and not self.is_auth("owner"):
                self.send_response(302)
                self.send_header("Location", "/admin/login")
                self.end_headers()
                return

            conn = sqlite3.connect(DB_FILE)
            rows = conn.cursor().execute("SELECT id, utr, amt, proof, status, dt FROM tx ORDER BY id DESC").fetchall()
            conn.close()
            
            trs = ""
            for r in rows:
                col = "#10b981" if r[4] == "APPROVED" else ("#ef4444" if r[4] == "REJECTED" else "#f59e0b")
                im = f'<img src="{r[3]}" onclick="viewImg(\'{r[3]}\')" style="width:55px;height:55px;object-fit:cover;border-radius:6px;cursor:pointer;border:1px solid #475569;">' if r[3] else "-"
                act = f'<button onclick="act({r[0]},\'APPROVED\')" style="background:#10b981;color:#fff;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold;">Approve</button> <button onclick="act({r[0]},\'REJECTED\')" style="background:#eab308;color:#000;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;margin-left:4px;font-size:12px;font-weight:bold;">Reject</button>' if r[4] == "PENDING" else f'<b style="color:{col};">{r[4]}</b>'
                del_btn = f'<button onclick="delTx({r[0]})" style="background:#ef4444;color:#fff;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;font-size:12px;margin-left:6px;font-weight:bold;">🗑 Delete</button>'
                trs += f'<tr style="border-bottom:1px solid #334155;"><td style="font-weight:bold;">#{r[0]}</td><td style="font-family:monospace;font-weight:bold;">{r[1]}</td><td>₹{r[2]}</td><td>{im}</td><td style="color:{col};font-weight:bold;">{r[4]}</td><td style="font-size:11px;color:#94a3b8;">{r[5]}</td><td style="white-space:nowrap;">{act} {del_btn}</td></tr>'

            adm = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Admin Dashboard</title>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:#0f172a; color:#fff; font-family:sans-serif; padding:15px; margin:0; }}
        table {{ width:100%; background:#1e293b; border-collapse:collapse; border-radius:8px; overflow:hidden; margin-top:12px; }}
        th, td {{ padding:10px; text-align:left; }}
        th {{ background:#334155; font-size:13px; }}
        #imgModal {{ display:none; position:fixed; z-index:9999; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.9); justify-content:center; align-items:center; padding:15px; }}
        #imgModal img {{ max-width:95%; max-height:85vh; border-radius:8px; border:2px solid #38bdf8; object-fit:contain; }}
        #closeModal {{ position:absolute; top:20px; right:25px; color:#fff; font-size:32px; font-weight:bold; cursor:pointer; background:rgba(255,255,255,0.2); width:40px; height:40px; line-height:36px; text-align:center; border-radius:50%; }}
    </style>
</head>
<body>
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <h3>🛡️ Payment Admin Panel</h3>
        <div>
            <button onclick="location.reload()" style="background:#38bdf8;padding:8px 14px;border:none;border-radius:5px;font-weight:bold;cursor:pointer;">Refresh</button>
            <button onclick="document.cookie='admin_auth=; Max-Age=0; path=/;';location.href='/admin/login';" style="background:#ef4444;color:#fff;padding:8px 14px;border:none;border-radius:5px;cursor:pointer;margin-left:5px;">Logout</button>
        </div>
    </div>
    <div style="overflow-x:auto;">
        <table>
            <thead><tr><th>ID</th><th>UTR</th><th>Amt</th><th>Proof</th><th>Status</th><th>Date</th><th>Action</th></tr></thead>
            <tbody>{trs if trs else '<tr><td colspan="7" style="text-align:center;padding:25px;color:#94a3b8;">Koi record nahi hai.</td></tr>'}</tbody>
        </table>
    </div>
    <div id="imgModal" onclick="closeImg()"><span id="closeModal">&times;</span><img id="modalImg" src=""></div>
    <script>
    function viewImg(src) {{ document.getElementById('modalImg').src = src; document.getElementById('imgModal').style.display = 'flex'; }}
    function closeImg() {{ document.getElementById('imgModal').style.display = 'none'; }}
    function act(id, st) {{ fetch('/api/action', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{id:id, st:st}})}}).then(() => location.reload()); }}
    function delTx(id) {{ if (confirm('Record #' + id + ' delete karein?')) fetch('/api/delete', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{id:id}})}}).then(() => location.reload()); }}
    </script>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(adm.encode("utf-8"))

        # 3. OWNER URL (/owner)
        elif p == "/owner/login":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_login("👑 Owner Portal Login", "/api/owner/login", "/owner").encode("utf-8"))

        elif p == "/owner":
            if not self.is_auth("owner"):
                self.send_response(302)
                self.send_header("Location", "/owner/login")
                self.end_headers()
                return

            upi_id = get_setting("upi_id")
            name = get_setting("receiver_name")
            admin_user = get_setting("admin_user")
            admin_pass = get_setting("admin_pass")
            owner_user = get_setting("owner_user")

            conn = sqlite3.connect(DB_FILE)
            tot_rev = conn.cursor().execute("SELECT SUM(CAST(amt AS REAL)) FROM tx WHERE status='APPROVED'").fetchone()[0] or 0
            tot_cnt = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='APPROVED'").fetchone()[0] or 0
            tot_pend = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='PENDING'").fetchone()[0] or 0
            conn.close()

            owner_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Owner Control Panel</title>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:#090d16; color:#f8fafc; font-family:sans-serif; padding:15px; margin:0; }}
        .card {{ background:#1e293b; padding:18px; border-radius:12px; margin-bottom:15px; border:1px solid #334155; }}
        .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap:10px; margin-bottom:15px; }}
        .stat {{ background:#0f172a; padding:14px; border-radius:10px; border:1px solid #1e293b; text-align:center; }}
        .stat-val {{ font-size:22px; font-weight:bold; color:#38bdf8; margin-top:4px; }}
        input {{ width:100%; padding:12px; margin:6px 0 12px 0; background:#0f172a; border:1px solid #475569; border-radius:6px; color:#fff; font-size:16px !important; }}
        label {{ font-size:12px; color:#94a3b8; font-weight:bold; }}
        button {{ width:100%; padding:12px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:15px; }}
    </style>
</head>
<body>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
        <h2 style="margin:0;color:#facc15;">👑 Master Owner Panel</h2>
        <button onclick="document.cookie='owner_auth=; Max-Age=0; path=/;';location.href='/owner/login';" style="background:#ef4444;color:#fff;width:auto;padding:8px 14px;">Logout</button>
    </div>

    <!-- Revenue Analytics -->
    <div class="grid">
        <div class="stat"><div style="font-size:11px;color:#94a3b8;">Total Revenue</div><div class="stat-val" style="color:#10b981;">₹{tot_rev:,.0f}</div></div>
        <div class="stat"><div style="font-size:11px;color:#94a3b8;">Approved Orders</div><div class="stat-val">{tot_cnt}</div></div>
        <div class="stat"><div style="font-size:11px;color:#94a3b8;">Pending Approvals</div><div class="stat-val" style="color:#f59e0b;">{tot_pend}</div></div>
    </div>

    <!-- Payment Settings Form -->
    <div class="card">
        <h3 style="margin:0 0 12px 0;color:#38bdf8;">💳 UPI & Receiver Settings</h3>
        <label>UPI ID (QR & Links):</label>
        <input type="text" id="upi_id" value="{upi_id}">
        <label>Receiver Name:</label>
        <input type="text" id="receiver_name" value="{name}">
        <button style="background:#0284c7;color:#fff;" onclick="saveUpi()">Save UPI Settings</button>
    </div>

    <!-- Staff / Admin Credentials -->
    <div class="card">
        <h3 style="margin:0 0 12px 0;color:#a855f7;">🛡️ Admin Panel Login Credentials</h3>
        <label>Admin Mobile / User:</label>
        <input type="text" id="admin_user" value="{admin_user}">
        <label>Admin Password:</label>
        <input type="text" id="admin_pass" value="{admin_pass}">
        <button style="background:#9333ea;color:#fff;" onclick="saveAdmin()">Update Admin Credentials</button>
    </div>

    <!-- Owner Password Change -->
    <div class="card">
        <h3 style="margin:0 0 12px 0;color:#f59e0b;">🔒 Change Owner Password</h3>
        <label>Owner Username:</label>
        <input type="text" id="owner_user" value="{owner_user}">
        <label>New Owner Password:</label>
        <input type="password" id="owner_pass" placeholder="Enter new owner password">
        <button style="background:#d97706;color:#fff;" onclick="saveOwner()">Update Owner Password</button>
    </div>

    <div style="text-align:center;margin:20px 0;">
        <a href="/admin" style="color:#38bdf8;font-size:14px;text-decoration:none;margin-right:15px;">➔ Go to Admin Panel</a>
        <a href="/" target="_blank" style="color:#10b981;font-size:14px;text-decoration:none;">➔ View User Checkout Page</a>
    </div>

    <script>
    function postSetting(data) {{
        fetch('/api/owner/save-settings', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify(data)
        }}).then(r => r.json()).then(d => {{
            if(d.ok) alert('Settings successfully updated!');
            else alert('Error updating settings.');
        }});
    }}
    function saveUpi() {{
        postSetting({{ upi_id: document.getElementById('upi_id').value.trim(), receiver_name: document.getElementById('receiver_name').value.trim() }});
    }}
    function saveAdmin() {{
        postSetting({{ admin_user: document.getElementById('admin_user').value.trim(), admin_pass: document.getElementById('admin_pass').value.trim() }});
    }}
    function saveOwner() {{
        var p = document.getElementById('owner_pass').value.trim();
        var u = document.getElementById('owner_user').value.trim();
        if(!p) return alert('Kripya naya password daalein!');
        postSetting({{ owner_user: u, owner_pass: p }});
    }}
    </script>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(owner_html.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        l = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(l).decode("utf-8")) if l else {}

        if self.path == "/api/admin/login":
            u = d.get("user")
            p = d.get("pass")
            if u == get_setting("admin_user") and p == get_setting("admin_pass"):
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Set-Cookie", "admin_auth=logged_in; Path=/")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            else:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":false,"msg":"Galat Admin Credentials!"}')

        elif self.path == "/api/owner/login":
            u = d.get("user")
            p = d.get("pass")
            if u == get_setting("owner_user") and p == get_setting("owner_pass"):
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Set-Cookie", "owner_auth=logged_in; Path=/")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            else:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":false,"msg":"Galat Owner Credentials!"}')

        elif self.path == "/api/owner/save-settings":
            if not self.is_auth("owner"):
                self.send_response(403)
                self.end_headers()
                return
            for k, v in d.items():
                set_setting(k, v)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        elif self.path == "/api/submit":
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO tx (utr, amt, proof, status, dt) VALUES (?, ?, ?, 'PENDING', ?)",
                          (d.get("utr"), d.get("amt"), d.get("proof"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                res = {"ok": True}
            except sqlite3.IntegrityError:
                res = {"ok": False, "msg": "Yeh UTR pehle se darj hai!"}
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/action":
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE tx SET status=? WHERE id=?", (d.get("st"), d.get("id")))
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        elif self.path == "/api/delete":
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM tx WHERE id=?", (d.get("id"),))
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

print(f"Server starting on port {PORT}")
with socketserver.TCPServer(("", PORT), H) as s:
    s.serve_forever()
