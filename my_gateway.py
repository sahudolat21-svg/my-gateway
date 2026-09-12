import http.server
import socketserver
import json
import qrcode
import io
import base64
import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", 8080))
DB_FILE = "payments.db"

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
AMT = "100"

def get_qr():
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(f"upi://pay?pa={UPI_ID}&pn={NAME}&am={AMT}&cu=INR")
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image().save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

QR_IMG = get_qr()

class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        p = urlparse(self.path).path
        if p in ["/", "/pay"]:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>UPI Pay</title>
    <style>
        body {{ background:#0f172a; color:#f8fafc; font-family:sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; box-sizing:border-box; }}
        .c {{ background:#1e293b; padding:20px; border-radius:15px; max-width:360px; width:100%; text-align:center; border:1px solid #334155; }}
        .amt {{ font-size:22px; color:#38bdf8; font-weight:bold; margin:10px 0; }}
        .btn {{ display:block; width:100%; padding:10px; margin:6px 0; border-radius:6px; border:none; color:#fff; font-weight:bold; text-decoration:none; box-sizing:border-box; cursor:pointer; font-size:14px; }}
        input {{ width:100%; padding:8px; margin:4px 0 10px 0; background:#0f172a; border:1px solid #475569; border-radius:5px; color:#fff; box-sizing:border-box; }}
        .badge {{ margin: 10px auto; padding: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; font-size: 11px; color: #cbd5e1; text-align: left; }}
    </style>
</head>
<body>
    <div class="c">
        <h3>{NAME}</h3>
        <div style="color:#94a3b8;font-size:12px;">{UPI_ID}</div>
        <div class="amt">₹{AMT}</div>
        
        <div style="background:#fff;padding:8px;display:inline-block;border-radius:8px;">
            <img id="qrimg" src="data:image/png;base64,{QR_IMG}" style="max-width:180px;display:block;">
        </div>
        <br>
        <button type="button" onclick="downloadQR()" style="background:#16a34a;color:#fff;border:none;padding:6px 12px;border-radius:5px;margin-top:8px;font-weight:bold;cursor:pointer;">📥 Download QR Code</button>

        <div class="badge">
            <span style="color: #38bdf8; font-weight: bold;">💳 Supported:</span> RuPay Credit Card, Debit Card, & UPI Apps
        </div>

        <a class="btn" style="background:#5f259f;" href="phonepe://pay?pa={UPI_ID}&pn={NAME}&am={AMT}&cu=INR">Pay via PhonePe</a>
        <a class="btn" style="background:#1a73e8;" href="tez://upi/pay?pa={UPI_ID}&pn={NAME}&am={AMT}&cu=INR">Pay via Google Pay</a>
        <a class="btn" style="background:#00b9f1;" href="paytmmp://pay?pa={UPI_ID}&pn={NAME}&am={AMT}&cu=INR">Pay via Paytm</a>

        <div style="border-top:1px solid #334155;margin-top:15px;padding-top:10px;text-align:left;font-size:12px;">
            <label>12-Digit UTR Number:</label>
            <input type="text" id="u" maxlength="12" placeholder="Enter UTR number">
            
            <label>Payment Proof (Screenshot):</label>
            <input type="file" id="p" accept="image/*">
            
            <button class="btn" style="background:#10b981;" onclick="sendProof()">Submit Proof</button>
            <div id="st" style="margin-top:8px;font-weight:bold;text-align:center;"></div>
        </div>
    </div>

    <script>
    function downloadQR() {{
        var img = document.getElementById('qrimg');
        var canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth || 300;
        canvas.height = img.naturalHeight || 300;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        var a = document.createElement('a');
        a.href = canvas.toDataURL('image/png');
        a.download = 'upi_qr.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
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
                body: JSON.stringify({{ utr: u, proof: reader.result, amt: '{AMT}' }})
            }})
            .then(res => res.json())
            .then(d => {{
                if (d.ok) {{
                    s.innerHTML = '<span style="color:#10b981;">✅ Proof Submitted! Admin verify karenge.</span>';
                }} else {{
                    s.innerHTML = '<span style="color:#ef4444;">' + d.msg + '</span>';
                }}
            }})
            .catch(() => {{
                s.innerHTML = '<span style="color:#ef4444;">Upload error. Dobara koshish karein.</span>';
            }});
        }};
        reader.readAsDataURL(f);
    }}
    </script>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif p == "/admin":
            conn = sqlite3.connect(DB_FILE)
            rows = conn.cursor().execute("SELECT id, utr, amt, proof, status, dt FROM tx ORDER BY id DESC").fetchall()
            conn.close()
            
            trs = ""
            for r in rows:
                col = "#10b981" if r[4] == "APPROVED" else ("#ef4444" if r[4] == "REJECTED" else "#f59e0b")
                im = f'<a href="{r[3]}" target="_blank"><img src="{r[3]}" style="width:60px;max-height:60px;border-radius:4px;"></a>' if r[3] else "-"
                act = f'<button onclick="act({r[0]},\'APPROVED\')" style="background:#10b981;color:#fff;border:none;padding:4px 8px;border-radius:4px;cursor:pointer;">Approve</button> <button onclick="act({r[0]},\'REJECTED\')" style="background:#ef4444;color:#fff;border:none;padding:4px 8px;border-radius:4px;cursor:pointer;">Reject</button>' if r[4] == "PENDING" else f'<b>{r[4]}</b>'
                trs += f'<tr style="border-bottom:1px solid #334155;"><td>#{r[0]}</td><td style="font-family:monospace;font-weight:bold;">{r[1]}</td><td>₹{r[2]}</td><td>{im}</td><td style="color:{col};font-weight:bold;">{r[4]}</td><td style="font-size:11px;color:#94a3b8;">{r[5]}</td><td>{act}</td></tr>'

            adm = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>Admin Dashboard</title>
    <style>
        body {{ background:#0f172a; color:#fff; font-family:sans-serif; padding:15px; margin:0; }}
        table {{ width:100%; background:#1e293b; border-collapse:collapse; border-radius:8px; overflow:hidden; margin-top:12px; }}
        th, td {{ padding:10px; text-align:left; }}
        th {{ background:#334155; font-size:13px; }}
    </style>
</head>
<body>
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <h3>🛡️ Payment Admin Panel</h3>
        <button onclick="location.reload()" style="background:#38bdf8;padding:6px 12px;border:none;border-radius:5px;font-weight:bold;cursor:pointer;">Refresh</button>
    </div>
    <div style="overflow-x:auto;">
        <table>
            <thead><tr><th>ID</th><th>UTR</th><th>Amt</th><th>Proof</th><th>Status</th><th>Date</th><th>Action</th></tr></thead>
            <tbody>{trs if trs else '<tr><td colspan="7" style="text-align:center;padding:20px;">Koi proof jama nahi hua abhi tak.</td></tr>'}</tbody>
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
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if self.path == "/api/submit":
            try:
                c.execute("INSERT INTO tx (utr, amt, proof, status, dt) VALUES (?, ?, ?, 'PENDING', ?)",
                          (d.get("utr"), d.get("amt"), d.get("proof"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                res = {"ok": True}
            except sqlite3.IntegrityError:
                res = {"ok": False, "msg": "Yeh UTR pehle se darj hai!"}
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/action":
            c.execute("UPDATE tx SET status=? WHERE id=?", (d.get("st"), d.get("id")))
            conn.commit()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        conn.close()

print(f"Server starting on port {PORT}")
with socketserver.TCPServer(("", PORT), H) as s:
    s.serve_forever()
