import http.server
import socketserver
import json
import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", 8080))

if os.path.exists("/var/data"):
    DB_FILE = "/var/data/payments.db"
else:
    DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payments.db")

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS tx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utr TEXT UNIQUE,
        amt TEXT,
        proof TEXT,
        status TEXT DEFAULT 'PENDING',
        dt TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        val TEXT
    )""")
    
    defaults = {
        'upi_id': '7546982355-1@mbkns',
        'receiver_name': 'Rupa Kumari',
        'admin_user': '7546982355',
        'admin_pass': '7546982355',
        'owner_user': '7546982355',
        'owner_pass': '7546982355',
        'user_page_title': 'UPI Checkout',
        'user_bg_color': '#0f172a',
        'user_card_color': '#1e293b',
        'user_btn_color': '#0284c7',
        'user_badge_text': '💳 Supported: RuPay Credit Card, Debit Card & UPI Apps',
        'user_success_msg': 'Aapka payment verify aur approve kar diya gaya hai.',
        'admin_title': '🛡️ Payment Admin Panel',
        'admin_bg_color': '#0f172a',
        'admin_table_head': '#334155',
        'admin_btn_color': '#38bdf8',
        'user_hand_order': '["u_name","u_upi","u_amtbox","u_qr","u_downbtn","u_badge","u_phonepe","u_gpay","u_paytm","u_proofbox"]',
        'user_hand_texts': '{}',
        'admin_hand_order': '["a_header","a_table"]',
        'admin_hand_texts': '{}'
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, val) VALUES (?, ?)", (k, v))
    
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default=""):
    conn = get_db()
    r = conn.cursor().execute("SELECT val FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r[0] if r and r[0] is not None else default

def set_setting(key, val):
    conn = get_db()
    conn.cursor().execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

def render_pay_page():
    upi_id = get_setting("upi_id", "7546982355-1@mbkns")
    name = get_setting("receiver_name", "Rupa Kumari")
    page_title = get_setting("user_page_title", "UPI Checkout")
    bg_col = get_setting("user_bg_color", "#0f172a")
    card_col = get_setting("user_card_color", "#1e293b")
    btn_col = get_setting("user_btn_color", "#0284c7")
    badge_text = get_setting("user_badge_text", "💳 Supported: RuPay Credit Card, Debit Card & UPI Apps")
    success_msg = get_setting("user_success_msg", "Aapka payment verify aur approve kar diya gaya hai.")

    order_raw = get_setting("user_hand_order", '[]')
    try:
        order = json.loads(order_raw)
    except:
        order = ["u_name","u_upi","u_amtbox","u_qr","u_downbtn","u_badge","u_phonepe","u_gpay","u_paytm","u_proofbox"]

    texts_raw = get_setting("user_hand_texts", '{}')
    try:
        custom_texts = json.loads(texts_raw)
    except:
        custom_texts = {}

    txt_name = custom_texts.get("u_name", name)
    txt_upi = custom_texts.get("u_upi", upi_id)
    txt_down = custom_texts.get("u_downbtn", "📥 Download QR Code")
    txt_badge = custom_texts.get("u_badge", badge_text)
    txt_phonepe = custom_texts.get("u_phonepe", "Pay via PhonePe")
    txt_gpay = custom_texts.get("u_gpay", "Pay via Google Pay")
    txt_paytm = custom_texts.get("u_paytm", "Pay via Paytm")

    el_map = {
        "u_name": f'<h3 id="u_name" style="margin:0;">{txt_name}</h3>',
        "u_upi": f'<div id="u_upi" style="color:#94a3b8;font-size:12px;margin-top:4px;">{txt_upi}</div>',
        "u_amtbox": f'''<div id="u_amtbox">
            <div style="display:flex;justify-content:space-between;align-items:center;margin:12px 0 6px 0;">
                <span id="displayAmt" style="font-size:20px;color:{btn_col};font-weight:bold;">₹0</span>
                <button onclick="changeAmt()" style="background:transparent;border:1px solid #64748b;color:#94a3b8;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;">Edit Amount</button>
            </div>
        </div>''',
        "u_qr": '<div id="u_qr"><div id="qrcode"></div></div>',
        "u_downbtn": f'<button id="u_downbtn" type="button" onclick="downloadQR()" style="background:#16a34a;color:#fff;border:none;padding:10px 14px;border-radius:6px;margin-top:6px;font-weight:bold;cursor:pointer;width:100%;font-size:14px;">{txt_down}</button>',
        "u_badge": f'<div id="u_badge" class="badge">{txt_badge}</div>',
        "u_phonepe": f'<a id="btnPhonePe" class="btn" style="background:#5f259f;" href="#">{txt_phonepe}</a>',
        "u_gpay": f'<a id="btnGPay" class="btn" style="background:#1a73e8;" href="#">{txt_gpay}</a>',
        "u_paytm": f'<a id="btnPaytm" class="btn" style="background:#00b9f1;" href="#">{txt_paytm}</a>',
        "u_proofbox": '''<div id="u_proofbox" style="border-top:1px solid rgba(255,255,255,0.1);margin-top:15px;padding-top:10px;text-align:left;font-size:12px;">
            <label>12-Digit UTR Number:</label>
            <input type="text" id="u" maxlength="12" placeholder="Enter 12-digit UTR">
            <label>Payment Proof (Screenshot):</label>
            <input type="file" id="p" accept="image/*">
            <button class="btn" style="background:#10b981;" onclick="sendProof()">Submit Proof</button>
            <div id="st" style="margin-top:8px;font-weight:bold;text-align:center;"></div>
        </div>'''
    }

    ordered_step2 = ""
    for eid in order:
        if eid in el_map and eid not in ["u_name", "u_upi"]:
            ordered_step2 += el_map[eid]

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{page_title}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:{bg_col}; color:#f8fafc; font-family:sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:15px; }}
        .c {{ background:{card_col}; padding:22px; border-radius:16px; max-width:360px; width:100%; text-align:center; border:1px solid rgba(255,255,255,0.1); box-shadow:0 8px 24px rgba(0,0,0,0.3); }}
        .amt-box {{ margin:15px 0; text-align:left; }}
        .amt-box label {{ font-size:13px; color:#94a3b8; font-weight:bold; }}
        .amt-input {{ width:100%; padding:14px; margin-top:6px; background:#0f172a; border:2px solid {btn_col}; border-radius:8px; color:{btn_col}; font-size:22px !important; font-weight:bold; text-align:center; }}
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
        {el_map.get("u_name", "")}
        {el_map.get("u_upi", "")}
        
        <div id="step1">
            <div class="amt-box">
                <label>Enter Amount (₹):</label>
                <input type="number" id="amtInput" class="amt-input" placeholder="Enter amount" min="1">
            </div>
            <button class="btn" style="background:{btn_col};font-size:16px;padding:14px;" onclick="proceedToPay()">Proceed to Pay ➔</button>
            <div id="step1-err" style="color:#ef4444;font-size:13px;margin-top:8px;"></div>
        </div>

        <div id="step2">
            {ordered_step2}
        </div>

        <div id="success-modal">
            <h2 style="color:#34d399;margin:0 0 8px 0;">🎉 Payment Successful!</h2>
            <p style="margin:0;font-size:13px;color:#e2e8f0;">{success_msg}</p>
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

        var da = document.getElementById('displayAmt');
        if(da) da.innerText = "₹" + amt;
        
        var upiUri = "upi://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";

        var bp = document.getElementById('btnPhonePe');
        if(bp) bp.href = "phonepe://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";
        var bg = document.getElementById('btnGPay');
        if(bg) bg.href = "tez://upi/pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";
        var bpt = document.getElementById('btnPaytm');
        if(bpt) bpt.href = "paytmmp://pay?pa=" + encodeURIComponent(upiId) + "&pn=" + encodeURIComponent(name) + "&am=" + amt + "&cu=INR";

        var qrDiv = document.getElementById('qrcode');
        if(qrDiv) {{
            qrDiv.innerHTML = "";
            new QRCode(qrDiv, {{
                text: upiUri,
                width: 170,
                height: 170,
                correctLevel: QRCode.CorrectLevel.M
            }});
        }}

        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';
    }}

    function changeAmt() {{
        document.getElementById('step2').style.display = 'none';
        document.getElementById('step1').style.display = 'block';
    }}

    function downloadQR() {{
        var canvas = document.querySelector('#qrcode canvas');
        var img = document.querySelector('#qrcode img');
        var dataUrl = "";

        if (canvas) {{
            dataUrl = canvas.toDataURL("image/png");
        }} else if (img && img.src) {{
            dataUrl = img.src;
        }}

        if (!dataUrl) {{
            alert("QR Code abhi taiyar nahi hai, kripya thoda ruk kar dubara dabayein.");
            return;
        }}

        var a = document.createElement('a');
        a.href = dataUrl;
        a.download = 'upi_payment_qr.png';
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
                body: JSON.stringify({{ utr: u, proof: reader.result, amt: currentAmt }})
            }})
            .then(res => res.json())
            .then(d => {{
                if (d.ok) {{
                    s.innerHTML = '<span style="color:#f59e0b;">⏳ Verification Pending... Admin approval ka intezar karein.</span>';
                    setInterval(() => {{
                        fetch('/api/check-status?utr=' + u).then(r => r.json()).then(res => {{
                            if (res.status === 'APPROVED') {{
                                var pb = document.getElementById('u_proofbox');
                                if(pb) pb.style.display = 'none';
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
        <input type="text" id="user" placeholder="Mobile Number / Username">
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
        
        # USER URL
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
            conn = get_db()
            r = conn.cursor().execute("SELECT status FROM tx WHERE utr=?", (utr,)).fetchone()
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": r[0] if r else "NOT_FOUND"}).encode("utf-8"))

        # ADMIN URL
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

            admin_title = get_setting("admin_title", "🛡️ Payment Admin Panel")
            admin_bg = get_setting("admin_bg_color", "#0f172a")
            admin_th = get_setting("admin_table_head", "#334155")
            admin_btn = get_setting("admin_btn_color", "#38bdf8")

            adm_texts_raw = get_setting("admin_hand_texts", '{}')
            try:
                adm_texts = json.loads(adm_texts_raw)
            except:
                adm_texts = {}
            final_adm_title = adm_texts.get("a_title_text", admin_title)
            final_ref_text = adm_texts.get("a_ref_text", "Refresh")
            final_logout_text = adm_texts.get("a_logout_text", "Logout")

            adm_order_raw = get_setting("admin_hand_order", '["a_header","a_table"]')
            try:
                adm_order = json.loads(adm_order_raw)
            except:
                adm_order = ["a_header","a_table"]

            conn = get_db()
            rows = conn.cursor().execute("SELECT id, utr, amt, proof, status, dt FROM tx ORDER BY id DESC").fetchall()
            conn.close()
            
            trs = ""
            for r in rows:
                col = "#10b981" if r[4] == "APPROVED" else ("#ef4444" if r[4] == "REJECTED" else "#f59e0b")
                im = f'<img src="{r[3]}" onclick="viewImg(\'{r[3]}\')" style="width:55px;height:55px;object-fit:cover;border-radius:6px;cursor:pointer;border:1px solid #475569;">' if r[3] else "-"
                act = f'<button onclick="act({r[0]},\'APPROVED\')" style="background:#10b981;color:#fff;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold;">Approve</button> <button onclick="act({r[0]},\'REJECTED\')" style="background:#eab308;color:#000;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;margin-left:4px;font-size:12px;font-weight:bold;">Reject</button>' if r[4] == "PENDING" else f'<b style="color:{col};">{r[4]}</b>'
                del_btn = f'<button onclick="delTx({r[0]})" style="background:#ef4444;color:#fff;border:none;padding:6px 10px;border-radius:4px;cursor:pointer;font-size:12px;margin-left:6px;font-weight:bold;">🗑 Delete</button>'
                trs += f'<tr style="border-bottom:1px solid #334155;"><td style="font-weight:bold;">#{r[0]}</td><td style="font-family:monospace;font-weight:bold;">{r[1]}</td><td>₹{r[2]}</td><td>{im}</td><td style="color:{col};font-weight:bold;">{r[4]}</td><td style="font-size:11px;color:#94a3b8;">{r[5]}</td><td style="white-space:nowrap;">{act} {del_btn}</td></tr>'

            blocks = {
                "a_header": f"""<div id="a_header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <h3 id="a_title_text" style="margin:0;">{final_adm_title}</h3>
                    <div id="a_actions">
                        <button id="a_ref_text" onclick="location.reload()" style="background:{admin_btn};padding:8px 14px;border:none;border-radius:5px;font-weight:bold;cursor:pointer;color:#000;">{final_ref_text}</button>
                        <button id="a_logout_text" onclick="document.cookie='admin_auth=; Max-Age=0; path=/;';location.href='/admin/login';" style="background:#ef4444;color:#fff;padding:8px 14px;border:none;border-radius:5px;cursor:pointer;margin-left:5px;">{final_logout_text}</button>
                    </div>
                </div>""",
                "a_table": f"""<div id="a_table" style="overflow-x:auto;">
                    <table>
                        <thead><tr><th>ID</th><th>UTR</th><th>Amt</th><th>Proof</th><th>Status</th><th>Date</th><th>Action</th></tr></thead>
                        <tbody>{trs if trs else '<tr><td colspan="7" style="text-align:center;padding:25px;color:#94a3b8;">Koi record nahi hai.</td></tr>'}</tbody>
                    </table>
                </div>"""
            }

            rendered_body = ""
            for k in adm_order:
                if k in blocks:
                    rendered_body += blocks[k]

            adm = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{final_adm_title}</title>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:{admin_bg}; color:#fff; font-family:sans-serif; padding:15px; margin:0; }}
        table {{ width:100%; background:#1e293b; border-collapse:collapse; border-radius:8px; overflow:hidden; }}
        th, td {{ padding:10px; text-align:left; }}
        th {{ background:{admin_th}; font-size:13px; }}
        #imgModal {{ display:none; position:fixed; z-index:9999; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.9); justify-content:center; align-items:center; padding:15px; }}
        #imgModal img {{ max-width:95%; max-height:85vh; border-radius:8px; border:2px solid {admin_btn}; object-fit:contain; }}
        #closeModal {{ position:absolute; top:20px; right:25px; color:#fff; font-size:32px; font-weight:bold; cursor:pointer; background:rgba(255,255,255,0.2); width:40px; height:40px; line-height:36px; text-align:center; border-radius:50%; }}
    </style>
</head>
<body>
    {rendered_body}
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

        # OWNER URL
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

            today_str = datetime.now().strftime("%Y-%m-%d")

            conn = get_db()
            day_rev = conn.cursor().execute("SELECT SUM(CAST(amt AS REAL)) FROM tx WHERE status='APPROVED' AND dt LIKE ?", (f"{today_str}%",)).fetchone()[0] or 0
            day_app = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='APPROVED' AND dt LIKE ?", (f"{today_str}%",)).fetchone()[0] or 0
            day_rej = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='REJECTED' AND dt LIKE ?", (f"{today_str}%",)).fetchone()[0] or 0
            day_pend = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='PENDING' AND dt LIKE ?", (f"{today_str}%",)).fetchone()[0] or 0

            all_rev = conn.cursor().execute("SELECT SUM(CAST(amt AS REAL)) FROM tx WHERE status='APPROVED'").fetchone()[0] or 0
            all_app = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='APPROVED'").fetchone()[0] or 0
            all_rej = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='REJECTED'").fetchone()[0] or 0
            all_pend = conn.cursor().execute("SELECT COUNT(*) FROM tx WHERE status='PENDING'").fetchone()[0] or 0

            all_rows = conn.cursor().execute("SELECT id, utr, amt, status, dt FROM tx ORDER BY id DESC").fetchall()
            conn.close()

            upi_id = get_setting("upi_id")
            name = get_setting("receiver_name")
            admin_user = get_setting("admin_user")
            admin_pass = get_setting("admin_pass")
            owner_user = get_setting("owner_user")

            u_title = get_setting("user_page_title", "UPI Checkout")
            u_bg = get_setting("user_bg_color", "#0f172a")
            u_card = get_setting("user_card_color", "#1e293b")
            u_btn = get_setting("user_btn_color", "#0284c7")
            u_badge = get_setting("user_badge_text", "💳 Supported: RuPay Credit Card, Debit Card & UPI Apps")
            u_msg = get_setting("user_success_msg", "Aapka payment verify aur approve kar diya gaya hai.")

            user_hand_order = get_setting("user_hand_order", '["u_name","u_upi","u_amtbox","u_qr","u_downbtn","u_badge","u_phonepe","u_gpay","u_paytm","u_proofbox"]')
            user_hand_texts = get_setting("user_hand_texts", '{}')
            admin_hand_order = get_setting("admin_hand_order", '["a_header","a_table"]')
            admin_hand_texts = get_setting("admin_hand_texts", '{}')

            all_trs_html = ""
            for r in all_rows:
                col = "#10b981" if r[3] == "APPROVED" else ("#ef4444" if r[3] == "REJECTED" else "#f59e0b")
                del_btn_owner = f'<button onclick="delTxOwner({r[0]})" style="background:#ef4444;color:#fff;border:none;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:bold;">🗑 Delete</button>'
                all_trs_html += f'<tr style="border-bottom:1px solid #334155;"><td style="padding:8px;">#{r[0]}</td><td style="font-family:monospace;">{r[1]}</td><td>₹{r[2]}</td><td style="color:{col};font-weight:bold;">{r[3]}</td><td style="font-size:11px;color:#94a3b8;">{r[4]}</td><td style="text-align:center;">{del_btn_owner}</td></tr>'

            owner_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Owner Control Panel</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.31/jspdf.plugin.autotable.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.0/Sortable.min.js"></script>
    <style>
        * {{ touch-action: manipulation; -webkit-text-size-adjust: 100%; box-sizing: border-box; }}
        body {{ background:#090d16; color:#f8fafc; font-family:sans-serif; padding:15px; margin:0; }}
        .card {{ background:#1e293b; padding:18px; border-radius:12px; margin-bottom:15px; border:1px solid #334155; }}
        .grid {{ display:grid; grid-template-columns: repeat(2, 1fr); gap:10px; margin-bottom:15px; }}
        .stat {{ background:#0f172a; padding:14px; border-radius:10px; border:1px solid #1e293b; text-align:center; }}
        .stat-val {{ font-size:22px; font-weight:bold; margin-top:4px; }}
        input[type="text"], input[type="password"] {{ width:100%; padding:12px; margin:6px 0 12px 0; background:#0f172a; border:1px solid #475569; border-radius:6px; color:#fff; font-size:16px !important; }}
        .color-row {{ display:flex; align-items:center; justify-content:space-between; margin:8px 0 12px 0; background:#0f172a; padding:8px 12px; border-radius:6px; border:1px solid #475569; }}
        .color-row input[type="color"] {{ border:none; width:45px; height:35px; border-radius:4px; cursor:pointer; background:transparent; }}
        label {{ font-size:12px; color:#94a3b8; font-weight:bold; }}
        button {{ width:100%; padding:12px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:15px; }}

        .hand-modal {{ display:none; position:fixed; z-index:9999; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.92); justify-content:center; align-items:center; padding:15px; }}
        .hand-modal-content {{ background:#1e293b; width:100%; max-width:440px; max-height:94vh; border-radius:16px; border:1px solid #38bdf8; display:flex; flex-direction:column; padding:16px; overflow-y:auto; }}
        
        .phone-mockup {{ width:100%; max-width:340px; margin:10px auto; background:{u_bg}; border:3px solid #38bdf8; border-radius:22px; padding:15px; box-shadow:0 8px 25px rgba(0,0,0,0.6); }}
        .canvas-card {{ background:{u_card}; padding:14px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); }}
        
        .live-draggable-item {{ 
            margin:8px 0; 
            cursor:grab; 
            position:relative; 
            border:1.5px dashed rgba(56,189,248,0.4); 
            border-radius:8px; 
            padding:5px; 
            background:rgba(255,255,255,0.02);
        }}
        .live-draggable-item:active {{ cursor:grabbing; border-color:#f59e0b; background:rgba(245,158,11,0.1); }}
        .live-draggable-item [contenteditable="true"] {{ outline:none; }}
        .live-draggable-item [contenteditable="true"]:focus {{ background:rgba(56,189,248,0.25); border-radius:4px; }}
        
        .canvas-btn {{ display:block; width:100%; padding:10px; border-radius:6px; color:#fff; font-weight:bold; text-align:center; font-size:14px; text-decoration:none; }}
        .canvas-badge {{ padding:8px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.15); border-radius:8px; font-size:11px; color:#cbd5e1; text-align:left; }}
        
        #allRecordsModal {{ display:none; position:fixed; z-index:9999; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.92); justify-content:center; align-items:center; padding:15px; }}
        .modal-content {{ background:#1e293b; width:100%; max-width:650px; max-height:92vh; border-radius:12px; border:1px solid #38bdf8; display:flex; flex-direction:column; padding:18px; }}
    </style>
</head>
<body>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div>
            <h2 style="margin:0;color:#facc15;">👑 Master Owner Panel</h2>
            <div style="font-size:11px;color:#38bdf8;margin-top:2px;">📅 Today's Live Stats (Auto Reset 24H)</div>
        </div>
        <button onclick="document.cookie='owner_auth=; Max-Age=0; path=/;';location.href='/owner/login';" style="background:#ef4444;color:#fff;width:auto;padding:8px 14px;">Logout</button>
    </div>

    <!-- 24H Today Analytics -->
    <div class="grid">
        <div class="stat"><div style="font-size:11px;color:#94a3b8;">Today's Revenue</div><div class="stat-val" style="color:#10b981;">₹{day_rev:,.0f}</div></div>
        <div class="stat"><div style="font-size:11px;color:#94a3b8;">Approved Orders</div><div class="stat-val" style="color:#38bdf8;">{day_app}</div></div>
        <div class="stat"><div style="font-size:11px;color:#94a3b8;">Pending Approvals</div><div class="stat-val" style="color:#f59e0b;">{day_pend}</div></div>
        <div class="stat"><div style="font-size:11px;color:#94a3b8;">Rejected Orders</div><div class="stat-val" style="color:#ef4444;">{day_rej}</div></div>
    </div>

    <div style="margin-bottom:15px;">
        <button onclick="openAllRecords()" style="background:#6366f1;color:#fff;display:flex;justify-content:center;align-items:center;gap:8px;font-size:16px;box-shadow:0 4px 12px rgba(99,102,241,0.3);">
            📊 View All-Time Record (Lifetime History)
        </button>
    </div>

    <!-- Settings Form -->
    <div class="card">
        <h3 style="margin:0 0 12px 0;color:#38bdf8;">💳 UPI & Receiver Settings</h3>
        <label>UPI ID (QR & Links):</label>
        <input type="text" id="upi_id" value="{upi_id}">
        <label>Receiver Name:</label>
        <input type="text" id="receiver_name" value="{name}">
        <button style="background:#0284c7;color:#fff;" onclick="saveUpi()">Save UPI Settings</button>
    </div>

    <!-- Staff Credentials -->
    <div class="card">
        <h3 style="margin:0 0 12px 0;color:#a855f7;">🛡️ Admin Panel Login Credentials</h3>
        <label>Admin Mobile / User:</label>
        <input type="text" id="admin_user" value="{admin_user}">
        <label>Admin Password:</label>
        <input type="text" id="admin_pass" value="{admin_pass}">
        <button style="background:#9333ea;color:#fff;" onclick="saveAdmin()">Update Admin Credentials</button>
    </div>

    <!-- Owner Password -->
    <div class="card">
        <h3 style="margin:0 0 12px 0;color:#f59e0b;">🔒 Change Owner Password</h3>
        <label>Owner Username:</label>
        <input type="text" id="owner_user" value="{owner_user}">
        <label>New Owner Password:</label>
        <input type="password" id="owner_pass" placeholder="Enter new owner password">
        <button style="background:#d97706;color:#fff;" onclick="saveOwner()">Update Owner Password</button>
    </div>

    <!-- Colors Customization with Reset Option -->
    <div class="card" style="border-left:4px solid #10b981;">
        <h3 style="margin:0 0 12px 0;color:#10b981;">🎨 Customize Theme Colors</h3>
        <label>Page Title:</label>
        <input type="text" id="user_page_title" value="{u_title}">
        <div class="color-row"><span>User Background Color</span><input type="color" id="user_bg_color" value="{u_bg}"></div>
        <div class="color-row"><span>User Card Color</span><input type="color" id="user_card_color" value="{u_card}"></div>
        <div class="color-row"><span>Button Color</span><input type="color" id="user_btn_color" value="{u_btn}"></div>
        <label>Payment Success Msg:</label>
        <input type="text" id="user_success_msg" value="{u_msg}">
        
        <div style="display:flex;gap:10px;margin-top:8px;">
            <button style="background:#10b981;color:#fff;flex:2;" onclick="saveUserCustomization()">💾 Save Theme Colors</button>
            <button style="background:#475569;color:#fff;flex:1;" onclick="resetThemeColors()">🔄 Reset Colors</button>
        </div>
    </div>

    <!-- HAND CONTROL BUTTONS -->
    <div class="card" style="border-left:4px solid #f59e0b;">
        <h3 style="margin:0 0 10px 0;color:#f59e0b;">🖐️ Hand Control Customizer</h3>
        <p style="font-size:12px;color:#94a3b8;margin:0 0 12px 0;">Buttons par click karke interactive modal me customization kholein:</p>
        
        <button onclick="openUserHandModal()" style="background:#f59e0b;color:#000;margin-bottom:10px;display:flex;justify-content:center;align-items:center;gap:8px;">
            📱 Open Hand Control (User Panel)
        </button>

        <button onclick="openAdminHandModal()" style="background:#38bdf8;color:#000;display:flex;justify-content:center;align-items:center;gap:8px;">
            ⚙️ Open Hand Control (Admin Panel)
        </button>
    </div>

    <div style="text-align:center;margin:25px 0 10px 0;">
        <a href="/admin" target="_blank" style="color:#38bdf8;font-size:14px;text-decoration:none;margin-right:15px;">➔ Open Admin Panel</a>
        <a href="/" target="_blank" style="color:#10b981;font-size:14px;text-decoration:none;">➔ Open User Checkout Page</a>
    </div>

    <!-- 1. POPUP MODAL: USER SCREEN HAND CONTROL -->
    <div id="userHandModal" class="hand-modal">
        <div class="hand-modal-content">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <h3 style="margin:0;color:#f59e0b;font-size:16px;">🖐️ Hand Control (User Screen)</h3>
                <span onclick="closeUserHandModal()" style="font-size:24px;color:#fff;cursor:pointer;font-weight:bold;padding:0 8px;">&times;</span>
            </div>
            <p style="font-size:11px;color:#94a3b8;margin:0 0 10px 0;">
                👉 Ungli se button pakad kar upar-niche karein. Text par tap karke live badlein.
            </p>

            <div class="phone-mockup">
                <div class="canvas-card">
                    <div id="liveCanvasItems"></div>
                </div>
            </div>

            <div style="display:flex;gap:10px;margin-top:12px;">
                <button style="background:#10b981;color:#fff;flex:2;" onclick="saveLiveCanvas()">💾 Save Layout</button>
                <button style="background:#475569;color:#fff;flex:1;" onclick="resetLiveCanvas()">🔄 Reset</button>
            </div>
        </div>
    </div>

    <!-- 2. POPUP MODAL: ADMIN SCREEN HAND CONTROL -->
    <div id="adminHandModal" class="hand-modal">
        <div class="hand-modal-content">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <h3 style="margin:0;color:#38bdf8;font-size:16px;">🖐️ Hand Control (Admin Screen)</h3>
                <span onclick="closeAdminHandModal()" style="font-size:24px;color:#fff;cursor:pointer;font-weight:bold;padding:0 8px;">&times;</span>
            </div>
            <p style="font-size:11px;color:#94a3b8;margin:0 0 10px 0;">
                Admin header aur table ka order ungli se change karein.
            </p>

            <div id="adminHandList" style="background:#0f172a;border:2px dashed #475569;border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:8px;"></div>

            <div style="display:flex;gap:10px;margin-top:12px;">
                <button style="background:#0284c7;color:#fff;flex:2;" onclick="saveAdminHand()">💾 Save Layout</button>
                <button style="background:#475569;color:#fff;flex:1;" onclick="resetAdminHand()">🔄 Reset</button>
            </div>
        </div>
    </div>

    <!-- All-Time Records Modal -->
    <div id="allRecordsModal">
        <div class="modal-content">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <h3 style="margin:0;color:#38bdf8;">📊 Lifetime All-Day Records</h3>
                <span onclick="closeAllRecords()" style="font-size:24px;color:#fff;cursor:pointer;font-weight:bold;padding:0 8px;">&times;</span>
            </div>

            <!-- CENTER ALL RECORD DELETE BUTTON -->
            <div style="text-align:center;margin-bottom:12px;">
                <button onclick="openDeleteAllModal()" style="background:#dc2626;color:#fff;font-size:13px;padding:8px 16px;border-radius:6px;width:auto;display:inline-flex;align-items:center;gap:6px;box-shadow:0 3px 10px rgba(220,38,38,0.4);">
                    🚨 Delete All Records
                </button>
            </div>
            
            <div class="grid" style="margin-bottom:12px;">
                <div class="stat"><div style="font-size:10px;color:#94a3b8;">Total Revenue</div><div class="stat-val" style="color:#10b981;font-size:18px;">₹{all_rev:,.0f}</div></div>
                <div class="stat"><div style="font-size:10px;color:#94a3b8;">Total Approved</div><div class="stat-val" style="color:#38bdf8;font-size:18px;">{all_app}</div></div>
                <div class="stat"><div style="font-size:10px;color:#94a3b8;">Total Pending</div><div class="stat-val" style="color:#f59e0b;font-size:18px;">{all_pend}</div></div>
                <div class="stat"><div style="font-size:10px;color:#94a3b8;">Total Rejected</div><div class="stat-val" style="color:#ef4444;font-size:18px;">{all_rej}</div></div>
            </div>

            <div style="overflow-y:auto;flex:1;background:#0f172a;border-radius:8px;border:1px solid #334155;">
                <table id="recordsTable" style="width:100%;border-collapse:collapse;font-size:12px;text-align:left;">
                    <thead style="background:#1e293b;position:sticky;top:0;">
                        <tr><th style="padding:8px;">ID</th><th>UTR</th><th>Amt</th><th>Status</th><th>Date</th><th style="text-align:center;">Action</th></tr>
                    </thead>
                    <tbody>
                        {all_trs_html if all_trs_html else '<tr><td colspan="6" style="text-align:center;padding:15px;color:#94a3b8;">Koi record nahi mila.</td></tr>'}
                    </tbody>
                </table>
            </div>

            <button onclick="closeAllRecords()" style="margin-top:12px;background:#475569;color:#fff;padding:11px;">Close Records</button>
            <button onclick="downloadPDF()" style="margin-top:8px;background:#10b981;color:#fff;padding:12px;font-weight:bold;display:flex;justify-content:center;align-items:center;gap:8px;">
                📥 Download Record PDF
            </button>
        </div>
    </div>

    <!-- TYPE CONFIRMATION MODAL FOR DELETING ALL RECORDS -->
    <div id="deleteAllModal" class="hand-modal">
        <div class="hand-modal-content" style="max-width:380px;text-align:center;">
            <div style="font-size:36px;margin-bottom:6px;">⚠️</div>
            <h3 style="margin:0 0 8px 0;color:#ef4444;">Warning: Delete All Records</h3>
            <p style="font-size:12px;color:#cbd5e1;line-height:1.4;margin:0 0 10px 0;">
                Agar aap sach me saara record permanently delete karna chahte hain, toh niche diye gaye box me exact ye text likhein:
            </p>
            <div style="background:#0f172a;padding:8px;border-radius:6px;border:1px dashed #ef4444;color:#facc15;font-weight:bold;font-size:13px;user-select:all;margin-bottom:12px;">
                Haa Me Delet kar raha hoo all record
            </div>
            
            <input type="text" id="confirmDeleteInput" placeholder="Yahan type karein..." style="text-align:center;border-color:#ef4444;">
            <div id="deleteErr" style="color:#ef4444;font-size:12px;margin-bottom:10px;font-weight:bold;"></div>

            <div style="display:flex;gap:10px;">
                <button onclick="confirmDeleteAll()" style="background:#dc2626;color:#fff;flex:2;">Confirm Delete</button>
                <button onclick="closeDeleteAllModal()" style="background:#475569;color:#fff;flex:1;">Cancel</button>
            </div>
        </div>
    </div>

    <script>
    var lifetimeRevenue = "{all_rev:,.0f}";
    var lifetimeApproved = "{all_app}";
    var lifetimePending = "{all_pend}";
    var lifetimeRejected = "{all_rej}";

    function openAllRecords() {{ document.getElementById('allRecordsModal').style.display = 'flex'; }}
    function closeAllRecords() {{ document.getElementById('allRecordsModal').style.display = 'none'; }}

    function openUserHandModal() {{ document.getElementById('userHandModal').style.display = 'flex'; }}
    function closeUserHandModal() {{ document.getElementById('userHandModal').style.display = 'none'; }}

    function openAdminHandModal() {{ document.getElementById('adminHandModal').style.display = 'flex'; }}
    function closeAdminHandModal() {{ document.getElementById('adminHandModal').style.display = 'none'; }}

    function openDeleteAllModal() {{
        document.getElementById('confirmDeleteInput').value = "";
        document.getElementById('deleteErr').innerText = "";
        document.getElementById('deleteAllModal').style.display = 'flex';
    }}
    function closeDeleteAllModal() {{
        document.getElementById('deleteAllModal').style.display = 'none';
    }}

    function confirmDeleteAll() {{
        var val = document.getElementById('confirmDeleteInput').value.trim();
        var requiredText = "Haa Me Delet kar raha hoo all record";
        if (val !== requiredText) {{
            document.getElementById('deleteErr').innerText = "❌ text not match";
            return;
        }}
        fetch('/api/delete-all', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ confirmation: val }})
        }}).then(r => r.json()).then(d => {{
            if (d.ok) {{
                alert('Saare records successfully delete kar diye gaye!');
                location.reload();
            }} else {{
                document.getElementById('deleteErr').innerText = d.msg;
            }}
        }});
    }}

    function delTxOwner(id) {{
        if(confirm('Kya aap sach me record #' + id + ' delete karna chahte hain?')) {{
            fetch('/api/delete', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{id: id}})
            }}).then(() => location.reload());
        }}
    }}

    function downloadPDF() {{
        var btn = event.target;
        var originalText = btn.innerHTML;
        btn.innerText = "⏳ Generating PDF...";
        btn.disabled = true;
        try {{
            const {{ jsPDF }} = window.jspdf;
            const doc = new jsPDF();
            doc.setFontSize(18);
            doc.setTextColor(30, 41, 59);
            doc.text("Payment Gateway - Lifetime Records", 14, 18);
            var now = new Date();
            doc.setFontSize(10);
            doc.setTextColor(100, 116, 139);
            doc.text("Generated on: " + now.toLocaleDateString() + ' ' + now.toLocaleTimeString(), 14, 25);
            doc.autoTable({{
                startY: 30,
                head: [['Metric', 'Value']],
                body: [
                    ['Total Lifetime Revenue', 'Rs. ' + lifetimeRevenue],
                    ['Total Approved Orders', lifetimeApproved],
                    ['Total Pending Orders', lifetimePending],
                    ['Total Rejected Orders', lifetimeRejected]
                ],
                theme: 'grid',
                styles: {{ fontSize: 10, cellPadding: 3 }},
                headStyles: {{ fillColor: [56, 189, 248], textColor: 255, fontStyle: 'bold' }},
                margin: {{ left: 14, right: 14 }}
            }});
            doc.autoTable({{
                html: '#recordsTable',
                startY: doc.lastAutoTable.finalY + 10,
                columns: [0, 1, 2, 3, 4],
                styles: {{ fontSize: 9, cellPadding: 3 }},
                headStyles: {{ fillColor: [30, 41, 59], textColor: 255, fontStyle: 'bold' }},
                alternateRowStyles: {{ fillColor: [248, 250, 252] }},
                margin: {{ left: 14, right: 14 }}
            }});
            doc.save("payment_records_" + now.toISOString().slice(0, 10) + ".pdf");
        }} catch(e) {{
            alert("PDF error: " + e.message);
        }} finally {{
            btn.innerHTML = originalText;
            btn.disabled = false;
        }}
    }}

    function postSetting(data, cb) {{
        fetch('/api/owner/save-settings', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify(data)
        }}).then(r => r.json()).then(d => {{
            if(d.ok) {{
                if(cb) cb();
                else alert('Settings successfully updated!');
            }} else alert('Error updating settings.');
        }});
    }}

    function saveUpi() {{ postSetting({{ upi_id: document.getElementById('upi_id').value.trim(), receiver_name: document.getElementById('receiver_name').value.trim() }}); }}
    function saveAdmin() {{ postSetting({{ admin_user: document.getElementById('admin_user').value.trim(), admin_pass: document.getElementById('admin_pass').value.trim() }}); }}
    function saveOwner() {{
        var p = document.getElementById('owner_pass').value.trim();
        var u = document.getElementById('owner_user').value.trim();
        if(!p) return alert('Kripya naya password daalein!');
        postSetting({{ owner_user: u, owner_pass: p }});
    }}
    function saveUserCustomization() {{
        postSetting({{
            user_page_title: document.getElementById('user_page_title').value.trim(),
            user_bg_color: document.getElementById('user_bg_color').value,
            user_card_color: document.getElementById('user_card_color').value,
            user_btn_color: document.getElementById('user_btn_color').value,
            user_success_msg: document.getElementById('user_success_msg').value.trim()
        }});
    }}

    function resetThemeColors() {{
        if(confirm('Kya aap theme colors ko pehle jaisa default banana chahte hain?')) {{
            postSetting({{
                user_page_title: 'UPI Checkout',
                user_bg_color: '#0f172a',
                user_card_color: '#1e293b',
                user_btn_color: '#0284c7',
                user_success_msg: 'Aapka payment verify aur approve kar diya gaya hai.'
            }}, function() {{
                location.reload();
            }});
        }}
    }}

    /* VISUAL SCREEN BUILDER ENGINE */
    var userSavedOrder = {user_hand_order};
    var userSavedTexts = {user_hand_texts};

    var visualTemplates = {{
        "u_name": function(txt) {{
            return '<h3 style="margin:0;text-align:center;"><span class="editable-target" contenteditable="true">' + (txt || "{name}") + '</span></h3>';
        }},
        "u_upi": function(txt) {{
            return '<div style="color:#94a3b8;font-size:12px;margin-top:4px;text-align:center;"><span class="editable-target" contenteditable="true">' + (txt || "{upi_id}") + '</span></div>';
        }},
        "u_amtbox": function(txt) {{
            return '<div style="display:flex;justify-content:space-between;align-items:center;margin:6px 0;"><span style="font-size:18px;color:{u_btn};font-weight:bold;">₹100</span><span style="font-size:11px;color:#94a3b8;border:1px solid #64748b;padding:2px 6px;border-radius:4px;">Edit Amount</span></div>';
        }},
        "u_qr": function(txt) {{
            return '<div style="background:#fff;padding:8px;border-radius:8px;width:120px;height:120px;margin:5px auto;display:flex;justify-content:center;align-items:center;color:#000;font-size:11px;font-weight:bold;text-align:center;">🔳 QR Code Live View</div>';
        }},
        "u_downbtn": function(txt) {{
            return '<button type="button" class="canvas-btn" style="background:#16a34a;"><span class="editable-target" contenteditable="true">' + (txt || "📥 Download QR Code") + '</span></button>';
        }},
        "u_badge": function(txt) {{
            return '<div class="canvas-badge"><span class="editable-target" contenteditable="true">' + (txt || "{u_badge}") + '</span></div>';
        }},
        "u_phonepe": function(txt) {{
            return '<div class="canvas-btn" style="background:#5f259f;"><span class="editable-target" contenteditable="true">' + (txt || "Pay via PhonePe") + '</span></div>';
        }},
        "u_gpay": function(txt) {{
            return '<div class="canvas-btn" style="background:#1a73e8;"><span class="editable-target" contenteditable="true">' + (txt || "Pay via Google Pay") + '</span></div>';
        }},
        "u_paytm": function(txt) {{
            return '<div class="canvas-btn" style="background:#00b9f1;"><span class="editable-target" contenteditable="true">' + (txt || "Pay via Paytm") + '</span></div>';
        }},
        "u_proofbox": function(txt) {{
            return '<div style="border-top:1px solid rgba(255,255,255,0.1);margin-top:8px;padding-top:6px;font-size:11px;color:#94a3b8;text-align:left;">' +
                   '<label>12-Digit UTR:</label><input type="text" placeholder="12-digit UTR" style="margin:4px 0;padding:6px;font-size:12px !important;" disabled>' +
                   '<div class="canvas-btn" style="background:#10b981;padding:8px;font-size:12px;margin-top:4px;">Submit Proof</div>' +
                   '</div>';
        }}
    }};

    function renderLiveCanvas() {{
        var container = document.getElementById('liveCanvasItems');
        container.innerHTML = "";
        userSavedOrder.forEach(function(key) {{
            if (visualTemplates[key]) {{
                var wrapper = document.createElement('div');
                wrapper.className = "live-draggable-item";
                wrapper.setAttribute('data-id', key);
                var customTxt = userSavedTexts[key] || "";
                wrapper.innerHTML = visualTemplates[key](customTxt);
                container.appendChild(wrapper);
            }}
        }});
    }}

    renderLiveCanvas();
    new Sortable(document.getElementById('liveCanvasItems'), {{
        animation: 200,
        ghostClass: 'sortable-ghost'
    }});

    function saveLiveCanvas() {{
        var items = document.getElementById('liveCanvasItems').children;
        var order = [];
        var texts = {{}};
        for (var i = 0; i < items.length; i++) {{
            var el = items[i];
            var id = el.getAttribute('data-id');
            order.push(id);
            var editable = el.querySelector('.editable-target');
            if (editable) {{
                texts[id] = editable.innerText.trim();
            }}
        }}
        postSetting({{
            user_hand_order: JSON.stringify(order),
            user_hand_texts: JSON.stringify(texts)
        }}, function() {{
            alert('Live User Screen Layout successfully save ho gaya!');
            closeUserHandModal();
        }});
    }}

    function resetLiveCanvas() {{
        if (confirm('Kya aap screen ko bilkul default (pehle jaisa) banana chahte hain?')) {{
            var defOrder = ["u_name","u_upi","u_amtbox","u_qr","u_downbtn","u_badge","u_phonepe","u_gpay","u_paytm","u_proofbox"];
            postSetting({{
                user_hand_order: JSON.stringify(defOrder),
                user_hand_texts: JSON.stringify({{}})
            }}, function() {{
                location.reload();
            }});
        }}
    }}

    /* Admin Hand Control */
    var adminItemsDef = {{
        "a_header": {{ label: "Admin Title & Buttons Header", defText: "🛡️ Payment Admin Panel" }},
        "a_table": {{ label: "Transaction Orders Table", defText: "Table Grid (Orders & Actions)" }}
    }};

    var adminSavedOrder = {admin_hand_order};
    var adminSavedTexts = {admin_hand_texts};

    function buildAdminHandList() {{
        var box = document.getElementById('adminHandList');
        box.innerHTML = "";
        adminSavedOrder.forEach(function(key) {{
            if(adminItemsDef[key]) {{
                var item = adminItemsDef[key];
                var curText = adminSavedTexts[key] || item.defText;
                var div = document.createElement('div');
                div.style = "background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px;display:flex;align-items:center;justify-content:space-between;cursor:grab;";
                div.setAttribute('data-id', key);
                div.innerHTML = '<span style="font-size:20px;color:#94a3b8;margin-right:10px;">☰</span> <span style="font-size:12px;color:#94a3b8;min-width:110px;">' + item.label + ':</span> <span class="editable-text" contenteditable="true" style="outline:none;border-bottom:1px dashed #64748b;padding:2px 4px;flex:1;margin-left:6px;">' + curText + '</span>';
                box.appendChild(div);
            }}
        }});
    }}

    buildAdminHandList();
    new Sortable(document.getElementById('adminHandList'), {{ animation: 150 }});

    function saveAdminHand() {{
        var list = document.getElementById('adminHandList').children;
        var order = [];
        var texts = {{}};
        for(var i=0; i<list.length; i++) {{
            var el = list[i];
            var id = el.getAttribute('data-id');
            order.push(id);
            var txt = el.querySelector('.editable-text').innerText.trim();
            texts[id] = txt;
        }}
        postSetting({{
            admin_hand_order: JSON.stringify(order),
            admin_hand_texts: JSON.stringify(texts)
        }}, function() {{
            alert('Admin Panel Layout successfully save ho gaya!');
            closeAdminHandModal();
        }});
    }}

    function resetAdminHand() {{
        if(confirm('Kya aap Admin Panel ko pehle jaisa default banana chahte hain?')) {{
            var defOrder = ["a_header","a_table"];
            postSetting({{
                admin_hand_order: JSON.stringify(defOrder),
                admin_hand_texts: JSON.stringify({{}})
            }}, function() {{
                location.reload();
            }});
        }}
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
            conn = get_db()
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
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE tx SET status=? WHERE id=?", (d.get("st"), d.get("id")))
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        elif self.path == "/api/delete":
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM tx WHERE id=?", (d.get("id"),))
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        elif self.path == "/api/delete-all":
            if not self.is_auth("owner"):
                self.send_response(403)
                self.end_headers()
                return
            conf = d.get("confirmation", "").strip()
            if conf != "Haa Me Delet kar raha hoo all record":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":false,"msg":"Text not match!"}')
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM tx")
            c.execute("DELETE FROM sqlite_sequence WHERE name='tx'")
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

print(f"Server starting on port {PORT}")
with socketserver.TCPServer(("", PORT), H) as s:
    s.serve_forever()
