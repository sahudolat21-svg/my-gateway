import http.server
import socketserver
import json
import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", 8080))
DB_FILE = "payments.db"

ADMIN_USER = "7546982355"
ADMIN_PASSWORD = "7546982355"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS tx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utr TEXT UNIQUE,
        amt TEXT,
        proof TEXT,
        status TEXT DEFAULT 'PENDING',
        dt TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

UPI_ID = "7546982355-1@mbkns"
NAME = "Rupa Kumari"

PAY_PAGE = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>UPI Checkout</title>
    <!-- Lightweight QR Library for instant real-time dynamic QR generation -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:#0f172a; color:#f8fafc; font-family:sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }}
        .c {{ background:#1e293b; padding:20px; border-radius:15px; max-width:360px; width:100%; text-align:center; border:1px solid #334155; }}
        .amt-box {{ margin:12px 0; text-align:left; }}
        .amt-box label {{ font-size:13px; color:#94a3b8; font-weight:bold; }}
        .amt-input {{ width:100%; padding:12px; margin-top:5px; background:#0f172a; border:2px solid #38bdf8; border-radius:8px; color:#38bdf8; font-size:20px !important; font-weight:bold; text-align:center; }}
        .btn {{ display:block; width:100%; padding:12px; margin:6px 0; border-radius:6px; border:none; color:#fff; font-weight:bold; text-decoration:none; cursor:pointer; font-size:15px; text-align:center; }}
        input {{ width:100%; padding:12px; margin:6px 0 12px 0; background:#0f172a; border:1px solid #475569; border-radius:5px; color:#fff; font-size:16px !important; }}
        .badge {{ margin: 10px auto; padding: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; font-size: 11px; color: #cbd5e1; text-align: left; }}
        #success-modal {{ display:none; background:#064e3b; border:1px solid #10b981; padding:15px; border-radius:10px; margin-top:15px; }}
        #qrcode {{ display:flex; justify-content:center; margin:10px auto; background:#fff; padding:10px; border-radius:8px; width:fit-content; }}
    </style>
</head>
<body>
    <div class="c">
        <h3 style="margin:0;">{NAME}</h3>
        <div style="color:#94a3b8;font-size:12px;margin-top:4px;">{UPI_ID}</div>
        
        <!-- Amount Input Box -->
        <div class="amt-box">
            <label>Amount (₹):</label>
            <input type="number" id="amtInput" class="amt-input" value="100" min="1" oninput="updatePaymentLinks()">
        </div>
        
        <div id="qrcode"></div>
        <button type="button" onclick="downloadQR()" style="background:#16a34a;color:#fff;border:none;padding:8px 14px;border-radius:5px;margin-top:8px;font-weight:bold;cursor:pointer;">📥 Download QR Code</button>

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

        <div id="success-modal">
            <h2 style="color:#34d399;margin:0 0 8px 0;">🎉 Payment Successful!</h2>
            <p style="margin:0;font-size:13px;color:#e2e8f0;">Aapka payment verify aur approve kar diya gaya hai.</p>
        </div>
    </div>

    <script>
    var upiId = "{UPI_ID}";
    var name = "{NAME}";
    var qrObj = null;
    var currentUtr = "";
    var checkTimer = null;

    function updatePaymentLinks() {{
        var amt = document.getElementById('amtInput').value.trim() || "1";
        var upiUri = "upi://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";

        document.getElementById('btnPhonePe').href = "phonepe://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";
        document.getElementById('btnGPay').href = "tez://upi/pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";
        document.getElementById('btnPaytm').href = "paytmmp://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";

        var qrDiv = document.getElementById('qrcode');
        qrDiv.innerHTML = "";
        qrObj = new QRCode(qrDiv, {{
            text: upiUri,
            width: 170,
            height: 170,
            correctLevel: QRCode.CorrectLevel.M
        }});
    }}

    // Init with default amount
    updatePaymentLinks();

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
        var amt = document.getElementById('amtInput').value.trim() || "100";
        var s = document.getElementById('st');
        if (u.length !== 12) {{
            s.innerHTML = '<span style="color:#ef4444;">12-Digit valid UTR daalein</span>';
            return;
        }}
        if (!f) {{
            s.innerHTML = '<span style="color:#ef4444;">Screenshot chunein</span>';
            return;
        }}
        currentUtr = u;
        s.innerHTML = '<span style="color:#38bdf8;">Uploading proof...</span>';
        var reader = new FileReader();
        reader.onload = function() {{
            fetch('/api/submit', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ utr: u, proof: reader.result, amt: amt }})
            }})
            .then(res => res.json())
            .then(d => {{
                if (d.ok) {{
                    s.innerHTML = '<span style="color:#f59e0b;">⏳ Verification Pending... Admin approval ka intezar karein.</span>';
                    startCheckingStatus(u);
                }} else {{
                    s.innerHTML = '<span style="color:#ef4444;">' + d.msg + '</span>';
                }}
            }})
            .catch(() => {{
                s.innerHTML = '<span style="color:#ef4444;">Error aaya, dobara koshish karein.</span>';
            }});
        }};
        reader.readAsDataURL(f);
    }}

    function startCheckingStatus(utr) {{
        if (checkTimer) clearInterval(checkTimer);
        checkTimer = setInterval(function() {{
            fetch('/api/check-status?utr=' + utr)
            .then(r => r.json())
            .then(res => {{
                if (res.status === 'APPROVED') {{
                    clearInterval(checkTimer);
                    document.getElementById('form-container').style.display = 'none';
                    document.getElementById('success-modal').style.display = 'block';
                }} else if (res.status === 'REJECTED') {{
                    clearInterval(checkTimer);
                    document.getElementById('st').innerHTML = '<span style="color:#ef4444;">❌ Payment Rejected by Admin.</span>';
                }}
            }});
        }}, 3000);
    }}
    </script>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Admin Login</title>
    <style>
        * { touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }
        body { background:#0f172a; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }
        .box { background:#1e293b; padding:25px; border-radius:12px; width:100%; max-width:320px; text-align:center; border:1px solid #334155; }
        input { width:100%; padding:12px; margin:8px 0; background:#0f172a; border:1px solid #475569; border-radius:5px; color:#fff; font-size:16px !important; }
        button { width:100%; padding:12px; background:#38bdf8; border:none; border-radius:6px; font-weight:bold; cursor:pointer; margin-top:8px; font-size:15px; }
    </style>
</head>
<body>
    <div class="box">
        <h3>🔒 Admin Panel Login</h3>
        <input type="text" id="user" placeholder="Mobile Number">
        <input type="password" id="pass" placeholder="Password">
        <button onclick="login()">Login</button>
        <div id="err" style="color:#ef4444;font-size:13px;margin-top:10px;"></div>
    </div>
    <script>
    function login() {
        var u = document.getElementById('user').value.trim();
        var p = document.getElementById('pass').value.trim();
        fetch('/api/admin/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user: u, pass: p})
        })
        .then(r => r.json())
        .then(d => {
            if(d.ok) {
                document.cookie = "admin_auth=logged_in; path=/";
                location.href = '/admin';
            } else {
                document.getElementById('err').innerText = d.msg;
            }
        });
    }
    </script>
</body>
</html>"""

class H(http.server.SimpleHTTPRequestHandler):
    def is_auth(self):
        cookies = self.headers.get('Cookie', '')
        return 'admin_auth=logged_in' in cookies

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ["/", "/pay"]:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAY_PAGE.encode("utf-8"))

        elif p == "/api/check-status":
            q = urlparse(self.path).query
            utr = ""
            for item in q.split("&"):
                if item.startswith("utr="):
                    utr = item.split("=")[1]
            conn = sqlite3.connect(DB_FILE)
            r = conn.cursor().execute("SELECT status FROM tx WHERE utr=?", (utr,)).fetchone()
            conn.close()
            status = r[0] if r else "NOT_FOUND"
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": status}).encode("utf-8"))

        elif p in ["/admin/login", "/admin/forget"]:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(LOGIN_HTML.encode("utf-8"))

        elif p == "/admin":
            if not self.is_auth():
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
                im = f'<a href="{r[3]}" target="_blank"><img src="{r[3]}" style="width:60px;max-height:60px;border-radius:4px;"></a>' if r[3] else "-"
                act = f'<button onclick="act({r[0]},\'APPROVED\')" style="background:#10b981;color:#fff;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;">Approve</button> <button onclick="act({r[0]},\'REJECTED\')" style="background:#ef4444;color:#fff;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;margin-left:4px;">Reject</button>' if r[4] == "PENDING" else f'<b>{r[4]}</b>'
                trs += f'<tr style="border-bottom:1px solid #334155;"><td>#{r[0]}</td><td style="font-family:monospace;font-weight:bold;">{r[1]}</td><td>₹{r[2]}</td><td>{im}</td><td style="color:{col};font-weight:bold;">{r[4]}</td><td style="font-size:11px;color:#94a3b8;">{r[5]}</td><td>{act}</td></tr>'

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
            <tbody>{trs if trs else '<tr><td colspan="7" style="text-align:center;padding:20px;">Koi proof nahi hai.</td></tr>'}</tbody>
        </table>
    </div>
    <script>
    function act(id, st) {{
        fetch('/api/action', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ id: id, st: st }})
        }}).then(() => location.reload());
    }}
    </script>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(adm.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        l = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(l).decode("utf-8")) if l else {}

        if self.path == "/api/admin/login":
            u = d.get("user")
            p = d.get("pass")
            if u == ADMIN_USER and p == ADMIN_PASSWORD:
                res = {"ok": True}
            else:
                res = {"ok": False, "msg": "Galat Mobile Number ya Password!"}
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

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

print(f"Server starting on port {PORT}")
with socketserver.TCPServer(("", PORT), H) as s:
    s.serve_forever()
