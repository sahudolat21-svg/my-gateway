import http.server
import socketserver
import json
import qrcode
import io
import base64
import re
from urllib.parse import parse_qs, urlparse

PORT = 5000

MY_UPI_ID = "7546982355-1@mbkns"
MY_NAME = "Rupa Kumari"

# Received payments store (In-memory database)
received_payments = {}

HTML_PAGE = """<!DOCTYPE html>
<html lang="hi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rupa Kumari - Secure Gateway</title>
  <style>
    body {
      margin: 0; background: #0b0f19;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh;
      padding: 15px; box-sizing: border-box;
    }
    .card {
      background: #151d2f; padding: 24px; border-radius: 20px; width: 100%; max-width: 380px;
      text-align: center; border: 1px solid #243049; box-shadow: 0 15px 35px rgba(0,0,0,0.6);
    }
    .logo {
      width: 50px; height: 50px; background: #5f259f; border-radius: 50%;
      font-size: 24px; font-weight: bold; color: white; display: inline-flex;
      align-items: center; justify-content: center; margin-bottom: 10px;
    }
    .input-box {
      width: 100%; box-sizing: border-box; padding: 12px; margin-bottom: 12px;
      border-radius: 10px; border: 1px solid #334155; background: #0b0f19; color: white; font-size: 16px;
    }
    .btn {
      width: 100%; padding: 12px; border: none; border-radius: 10px;
      background: #0284c7; color: white; font-size: 16px; font-weight: bold; cursor: pointer;
    }
    #pay-box { display: none; margin-top: 15px; border-top: 1px dashed #334155; padding-top: 15px; }
    .qr-container { background: white; padding: 10px; border-radius: 12px; display: inline-block; margin: 10px 0; }
    .qr-img { width: 170px; height: 170px; display: block; }
    
    /* App Specific Buttons */
    .app-btn-group { display: flex; flex-direction: column; gap: 10px; margin-top: 15px; }
    .app-btn {
      display: flex; align-items: center; justify-content: center;
      padding: 12px; border-radius: 10px; text-decoration: none;
      color: white; font-weight: bold; font-size: 15px; transition: transform 0.1s;
    }
    .phonepe-btn { background: #5f259f; }
    .gpay-btn { background: #1a73e8; }
    .paytm-btn { background: #00b9f5; color: #0b0f19; font-weight: 800; }
    
    .verify-box { margin-top: 18px; background: #0f172a; padding: 15px; border-radius: 12px; }
    .status-msg { margin-top: 10px; font-size: 14px; font-weight: bold; word-break: break-word; }
  </style>
</head>
<body>

  <div class="card">
    <div class="logo">पे</div>
    <h2 style="margin: 0;">Rupa Kumari</h2>
    <p style="color: #94a3b8; font-size: 13px; margin: 5px 0 15px;">7546982355-1@mbkns</p>

    <div id="step-1">
      <input type="number" id="amt" class="input-box" placeholder="Amount (₹)" value="100">
      <button class="btn" onclick="generateQR()">Pay Now</button>
    </div>

    <div id="pay-box">
      <div style="font-weight: bold; color: #38bdf8; font-size: 18px;" id="disp-amt"></div>
      
      <div class="qr-container">
        <img id="qr-img" class="qr-img" src="" alt="UPI QR">
      </div>
      <p style="font-size: 12px; color: #94a3b8; margin: 0 0 10px;">Scan karein ya direct app choose karein:</p>

      <!-- Three Dedicated Buttons -->
      <div class="app-btn-group">
        <a id="btn-phonepe" class="app-btn phonepe-btn" href="#">Pay with PhonePe</a>
        <a id="btn-gpay" class="app-btn gpay-btn" href="#">Pay with Google Pay</a>
        <a id="btn-paytm" class="app-btn paytm-btn" href="#">Pay with Paytm</a>
      </div>

      <div class="verify-box">
        <div style="font-size: 13px; margin-bottom: 8px;">Payment ke baad 12-digit UTR daalein:</div>
        <input type="text" id="utr-input" class="input-box" placeholder="Enter 12-digit UTR" maxlength="12">
        <button class="btn" style="background: #16a34a;" onclick="verifyPayment()">Verify Payment</button>
        <div id="status-msg" class="status-msg"></div>
      </div>
    </div>
  </div>

  <script>
    let currentAmount = 0;

    async function generateQR() {
      currentAmount = document.getElementById('amt').value;
      if (!currentAmount || currentAmount <= 0) return alert("Sahi amount daalein");

      const res = await fetch(`/create_order?amount=${currentAmount}`);
      const data = await res.json();

      document.getElementById('disp-amt').innerText = `Amount: ₹${data.amount}`;
      document.getElementById('qr-img').src = data.qr_base64;

      // Setting app specific intent links
      document.getElementById('btn-phonepe').href = data.phonepe_link;
      document.getElementById('btn-gpay').href = data.gpay_link;
      document.getElementById('btn-paytm').href = data.paytm_link;

      document.getElementById('step-1').style.display = 'none';
      document.getElementById('pay-box').style.display = 'block';
    }

    async function verifyPayment() {
      const utr = document.getElementById('utr-input').value.trim();
      const status = document.getElementById('status-msg');

      if (utr.length < 10) {
        status.style.color = '#ef4444';
        status.innerText = "Kripya sahi 12-digit UTR daalein";
        return;
      }

      status.style.color = '#f59e0b';
      status.innerText = "Checking payment status...";

      const res = await fetch(`/verify?utr=${utr}&amount=${currentAmount}`);
      const data = await res.json();

      if (data.success) {
        status.style.color = '#22c55e';
        status.innerText = "SUCCESS: " + data.message;
      } else {
        status.style.color = '#ef4444';
        status.innerText = "FAILED: " + data.message;
      }
    }
  </script>

</body>
</html>
"""

class GatewayHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        url_parts = urlparse(self.path)

        if url_parts.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))

        elif url_parts.path == "/create_order":
            params = parse_qs(url_parts.query)
            amount = params.get("amount", ["0"])[0]

            # Standard UPI parameters
            params_str = f"pa={MY_UPI_ID}&pn={MY_NAME.replace(' ', '%20')}&am={amount}&cu=INR&tn=OrderPay"
            
            # Universal UPI URI for QR
            upi_uri = f"upi://pay?{params_str}"

            # Specific Intents for Apps
            phonepe_uri = f"phonepe://pay?{params_str}"
            gpay_uri = f"tez://upi/pay?{params_str}"
            paytm_uri = f"paytmmp://pay?{params_str}"

            qr = qrcode.QRCode(box_size=6, border=1)
            qr.add_data(upi_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()

            res = {
                "amount": amount,
                "qr_base64": img_str,
                "phonepe_link": phonepe_uri,
                "gpay_link": gpay_uri,
                "paytm_link": paytm_uri
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif url_parts.path == "/verify":
            params = parse_qs(url_parts.query)
            utr = params.get("utr", [""])[0].strip()
            amount = params.get("amount", ["0"])[0].strip()

            if utr in received_payments:
                rec_amount = received_payments[utr]
                if str(rec_amount) == str(amount):
                    del received_payments[utr]
                    res = {"success": True, "message": f"Payment Verified! ₹{amount} received."}
                else:
                    res = {"success": False, "message": f"UTR match hua par amount alag hai (Expected: ₹{amount}, Found: ₹{rec_amount})"}
            else:
                res = {"success": False, "message": "Fake UTR ya payment abhi bank me nahi aayi hai."}

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

    def do_POST(self):
        if self.path == "/sms_hook":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            
            print(f"[Incoming Bank Alert]: {body}")
            utr_match = re.search(r'\b\d{12}\b', body)
            amt_match = re.search(r'(?:rs\.?|inr)\s*([\d\.]+)', body, re.IGNORECASE)
            
            if utr_match and amt_match:
                utr = utr_match.group(0)
                amt = amt_match.group(1).split('.')[0]
                received_payments[utr] = amt
                print(f"[PAYMENT LOGGED]: UTR={utr}, Amount=₹{amt}")
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

socketserver.TCPServer.allow_reuse_address = True
print(f"Gateway running on http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), GatewayHandler) as httpd:
    httpd.serve_forever()
