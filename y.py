from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio, aiohttp, json, base64, struct, random, re, ssl, html, os, time

try:
    import brotli
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    print("⚠️ يرجى تثبيت brotli و pycryptodome")

app = FastAPI()

# ==================== إعدادات المطور ====================
ADMIN_PASSWORD = "admin123" # غير كلمة سر لوحة التحكم هنا
DB_FILE = "website_db.json"

# ==================== إعدادات الطابور والحماية ====================
# السماح بإنشاء حسابين فقط في نفس اللحظة (الباقي ينتظر في الطابور)
create_semaphore = asyncio.Semaphore(2)
# قفل لحماية ملف قاعدة البيانات من التلف
db_lock = asyncio.Lock()

# ==================== إعدادات API للعبة ====================
API_KEY = "AIzaSyAe_aOVT1gSfmHKBrorFvX4fRwN5nODXVA"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SEND_OOB_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}"
UPDATE_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={API_KEY}"
SAVE_URL = "https://europe-west1-cp-multiplayer.cloudfunctions.net/SavePlayerRecordsPartially8"
RANK_URLS = [
    "https://us-central1-cp-multiplayer.cloudfunctions.net/SetUserRating6",
    "https://europe-west1-cp-multiplayer.cloudfunctions.net/SetUserRating6"
]
HDR = {"Accept": "*/*", "Accept-Encoding": "gzip", "Content-Type": "application/json", "User-Agent": "UnityPlayer/2022.3.62f2", "X-Unity-Version": "2022.3.62f2"}

# ==================== قاعدة البيانات ====================
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"total_created": 0, "maintenance": False, "ips": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

async def save_db_safe(data):
    async with db_lock:
        save_db(data)

# ==================== دوال التشفير ====================
def xk(f):
    c = list(str(f or ""))
    if len(c) >= 9: c[1], c[8] = c[8], c[1]
    if len(c) >= 3: c.pop(2)
    if len(c) >= 5: c.append(c[4])
    return "".join(c).encode() or b"0"
def xd(d, k):
    kl = len(k); return bytes(b ^ k[i % kl] for i, b in enumerate(d))
class W:
    def __init__(s): s.p = []
    def byte(s, v): s.p.append(bytes([int(v or 0) & 0xFF]))
    def i32(s, v): s.p.append(struct.pack("<i", int(v or 0)))
    def string(s, x):
        if x is None: s.p.append(struct.pack("<i", -1)); return
        x = str(x)
        if x == "": s.p.append(struct.pack("<i", 0)); return
        e = x.encode("utf-8"); s.p.append(struct.pack("<ii", -(len(e)) - 1, len(x)) + e)
    def build(s): return b"".join(s.p)
def pf(fid, val):
    w = W()
    if fid in (1, 3, 5): w.string(val)
    elif fid in (2, 4): w.i32(val or 0)
    return w.build()
def bf(rec, fuid):
    picked = []
    for fid, key in [(1, "localID"), (3, "Name"), (2, "money"), (4, "coin")]:
        if key in rec: picked.append((fid, pf(fid, rec[key])))
    body = [struct.pack("<i", len(picked))]
    for fid, blob in picked:
        body.append(struct.pack("<hi", fid, len(blob))); body.append(blob)
    packed = b"".join(body)
    comp = brotli.compress(packed, quality=1)
    return base64.b64encode(xd(comp, xk(fuid))).decode("ascii")

# ==================== دوال البريد ====================
def get_ssl_ctx():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    return ctx
async def get_temp_email():
    ctx = get_ssl_ctx()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as session:
        try:
            async with session.get("https://api.guerrillamail.com/ajax.php?f=get_email_address") as r:
                data = await r.json()
                return (data["email_addr"], data["sid_token"]) if "email_addr" in data else (None, None)
        except: return None, None
async def check_email_for_code(sid_token):
    ctx = get_ssl_ctx()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as session:
        for _ in range(15):
            await asyncio.sleep(3)
            try:
                async with session.get(f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid_token}") as r:
                    data = await r.json()
                    if data.get("list"):
                        mail_id = data["list"][0]["mail_id"]
                        async with session.get(f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={mail_id}&sid_token={sid_token}") as r2:
                            body = html.unescape((await r2.json()).get("mail_body", ""))
                            match = re.search(r'oobCode=([a-zA-Z0-9_-]+)', body)
                            if match: return match.group(1)
            except: pass
    return None

# ==================== قالب الواجهة (HTML) ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl" id="htmlRoot">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KAKASHI CPM | World Sale</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        :root { --primary: #ffd700; --bg: #050505; --card: rgba(25, 25, 25, 0.7); }
        * { box-sizing: border-box; }
        body {
            background-color: var(--bg);
            background-image: radial-gradient(circle at 50% 0%, #2a2400 0%, #000 70%);
            color: #fff; font-family: 'Cairo', sans-serif; margin: 0; padding: 20px;
            min-height: 100vh; display: flex; flex-direction: column; align-items: center;
        }
        .top-bar { width: 100%; max-width: 800px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .lang-btn { background: transparent; color: var(--primary); border: 1px solid var(--primary); padding: 8px 15px; border-radius: 8px; cursor: pointer; font-family: inherit; font-weight: bold; transition: 0.3s; }
        .lang-btn:hover { background: var(--primary); color: #000; }
        .counter { background: rgba(255, 215, 0, 0.1); border: 1px solid rgba(255, 215, 0, 0.3); padding: 8px 15px; border-radius: 20px; font-size: 14px; }
        .main-card {
            background: var(--card); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 215, 0, 0.2); border-radius: 20px;
            padding: 40px 20px; width: 100%; max-width: 600px; text-align: center;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(255, 215, 0, 0.1);
        }
        h1 { color: var(--primary); text-shadow: 0 0 10px rgba(255, 215, 0, 0.5); margin-top: 0; font-size: 32px; }
        .create-btn {
            background: linear-gradient(135deg, #ffd700, #b8860b);
            color: #000; padding: 18px 40px; border: none; border-radius: 12px;
            font-size: 20px; font-weight: 900; font-family: inherit; cursor: pointer;
            width: 100%; margin-top: 20px; box-shadow: 0 5px 15px rgba(255, 215, 0, 0.4);
            transition: 0.3s; text-transform: uppercase;
        }
        .create-btn:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(255, 215, 0, 0.6); }
        .create-btn:disabled { background: #333; color: #777; cursor: not-allowed; box-shadow: none; }
        .loader-box { display: none; margin-top: 20px; }
        .loader { border: 4px solid rgba(255, 215, 0, 0.1); border-top: 4px solid var(--primary); border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 0 auto 10px auto; }
        .queue-text { color: var(--primary); font-size: 14px; font-weight: bold; animation: pulse 1.5s infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .result-box { display: none; margin-top: 20px; padding: 20px; background: rgba(0,0,0,0.6); border-radius: 12px; border: 1px solid #00ff00; text-align: right; }
        .copy-btn { background: #333; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-family: inherit; margin-right: 10px; }
        .contact-section { margin-top: 40px; text-align: center; width: 100%; }
        .contact-title { color: #aaa; margin-bottom: 15px; }
        .social-links { display: flex; justify-content: center; gap: 20px; }
        .social-btn { display: flex; align-items: center; justify-content: center; width: 50px; height: 50px; border-radius: 50%; background: #222; text-decoration: none; color: white; font-size: 24px; transition: 0.3s; }
        .social-btn.telegram:hover { background: #0088cc; box-shadow: 0 0 15px #0088cc; }
        .social-btn.facebook:hover { background: #1877f2; box-shadow: 0 0 15px #1877f2; }
    </style>
</head>
<body>
    <div class="top-bar">
        <button class="lang-btn" onclick="toggleLang()">English 🌐</button>
        <div class="counter">👥 <span data-ar="حسابات تم إنشاؤها:" data-en="Accounts Created:">حسابات تم إنشاؤها:</span> <b>__TOTAL_CREATED__</b></div>
    </div>

    <div class="main-card">
        <h1>👑 KAKASHI CPM 👑</h1>
        <p data-ar="افتح المتجر العالمي (World Sale) واحصل على رتبة ملك فوراً." data-en="Unlock World Sale & Get King Rank instantly.">افتح المتجر العالمي (World Sale) واحصل على رتبة ملك فوراً.</p>
        <p style="color:#aaa; font-size:12px;" data-ar="⚠️ يمكنك إنشاء حساب واحد فقط كل 12 ساعة." data-en="⚠️ You can create only 1 account every 12 hours.">⚠️ يمكنك إنشاء حساب واحد فقط كل 12 ساعة.</p>
        
        __MAINTENANCE_HTML__
        
        <button class="create-btn" id="createBtn" onclick="createAccount()" __BTN_DISABLED__ data-ar="🚀 إنشاء حساب ملك الآن" data-en="🚀 Create King Account Now">🚀 إنشاء حساب ملك الآن</button>
        
        <div id="loaderBox" class="loader-box">
            <div class="loader"></div>
            <div class="queue-text" id="queueText" data-ar="⏳ جاري تجهيز الحساب..." data-en="⏳ Creating account...">⏳ جاري تجهيز الحساب...</div>
        </div>
        
        <div id="result" class="result-box">
            <h3 style="color:#00ff00; text-align:center; margin-top:0;" data-ar="✅ تم الإنشاء بنجاح!" data-en="✅ Created Successfully!">✅ تم الإنشاء بنجاح!</h3>
            <p><b data-ar="الإيميل:" data-en="Email:">الإيميل:</b> <span id="resEmail" style="color:var(--primary);"></span> <button class="copy-btn" onclick="copyText('resEmail')" data-ar="نسخ" data-en="Copy">نسخ</button></p>
            <p><b data-ar="الباسورد:" data-en="Password:">الباسورد:</b> <span id="resPass" style="color:var(--primary);"></span> <button class="copy-btn" onclick="copyText('resPass')" data-ar="نسخ" data-en="Copy">نسخ</button></p>
        </div>
    </div>

    <div class="contact-section">
        <div class="contact-title" data-ar="تواصل مع المطور:" data-en="Contact Developer:">تواصل مع المطور:</div>
        <div class="social-links">
            <a href="https://t.me/@kakashi_cpm" target="_blank" class="social-btn telegram">✈️</a>
            <a href="https://facebook.com/profile.php?id=100090541056982" target="_blank" class="social-btn facebook">f</a>
        </div>
    </div>

    <script>
        let isAr = true;
        function toggleLang() {
            isAr = !isAr;
            document.getElementById('htmlRoot').dir = isAr ? 'rtl' : 'ltr';
            document.querySelectorAll('[data-ar]').forEach(el => {
                el.innerText = isAr ? el.getAttribute('data-ar') : el.getAttribute('data-en');
            });
        }

        function copyText(id) {
            const text = document.getElementById(id).innerText;
            navigator.clipboard.writeText(text);
            alert(isAr ? 'تم نسخ النص بنجاح!' : 'Copied successfully!');
        }

        async function createAccount() {
            document.getElementById('createBtn').style.display = 'none';
            document.getElementById('result').style.display = 'none';
            document.getElementById('loaderBox').style.display = 'block';
            
            // تغيير النص لإظهار أن المستخدم في الطابور
            document.getElementById('queueText').innerText = isAr ? '⏳ أنت في الطابور... يرجى الانتظار' : '⏳ You are in queue... Please wait';

            try {
                const response = await fetch('/create', { method: 'POST' });
                const data = await response.json();
                
                document.getElementById('loaderBox').style.display = 'none';
                
                if (data.success) {
                    document.getElementById('result').style.display = 'block';
                    document.getElementById('resEmail').innerText = data.email;
                    document.getElementById('resPass').innerText = data.password;
                } else {
                    alert((isAr ? 'تنبيه: ' : 'Alert: ') + data.error);
                    document.getElementById('createBtn').style.display = 'block';
                }
            } catch (e) {
                document.getElementById('loaderBox').style.display = 'none';
                document.getElementById('createBtn').style.display = 'block';
                alert('Connection Error');
            }
        }
    </script>
</body>
</html>
"""

# ==================== تشغيل الموقع ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    db = load_db()
    
    total = str(db.get('total_created', 0))
    maint_html = "<p style='color:red; font-weight:bold;'>الموقع تحت الصيانة حالياً.</p>" if db.get("maintenance") else ""
    btn_dis = "disabled" if db.get("maintenance") else ""
    
    final_html = HTML_TEMPLATE.replace("__TOTAL_CREATED__", total)\
                              .replace("__MAINTENANCE_HTML__", maint_html)\
                              .replace("__BTN_DISABLED__", btn_dis)
                              
    return HTMLResponse(content=final_html)

@app.post("/create")
async def create_account(request: Request):
    # استخدام الطابور (Semaphore) لمنع انهيار السيرفر
    async with create_semaphore:
        db = load_db()
        if db.get("maintenance"): 
            return {"success": False, "error": "الموقع تحت الصيانة حالياً."}

        client_ip = request.client.host
        now = time.time()
        ips = db.setdefault("ips", {})
        
        # التحقق من الحد الزمني (12 ساعة وحساب واحد فقط)
        if client_ip in ips:
            ip_data = ips[client_ip]
            time_passed = now - ip_data["last_time"]
            
            if time_passed < 43200: # 43200 ثانية = 12 ساعة
                if ip_data["count"] >= 1:
                    remain_sec = 43200 - time_passed
                    hours = int(remain_sec // 3600)
                    mins = int((remain_sec % 3600) // 60)
                    return {"success": False, "error": f"عذراً، يمكنك إنشاء حساب واحد فقط كل 12 ساعة. متبقي لك: {hours} ساعة و {mins} دقيقة."}
            else:
                # إذا مرت 12 ساعة، نصفّر العداد
                ips[client_ip] = {"count": 0, "last_time": now}

        try:
            temp_email, sid_token = await get_temp_email()
            if not temp_email: 
                return {"success": False, "error": "فشل الاتصال بخدمة البريد. حاول مجدداً."}

            password = f"King_{random.randint(10000,99999)}_A1!"
            game_name = f"King_{random.randint(1000,9999)}"

            async with aiohttp.ClientSession() as session:
                async with session.post(SIGNUP_URL, json={"email": temp_email, "password": password, "returnSecureToken": True}) as resp:
                    res = await resp.json()
                    if "idToken" not in res: 
                        return {"success": False, "error": "فشل إنشاء الحساب (قد يكون السيرفر مزدحماً)."}
                    tok, fuid = res["idToken"], res["localId"]

                await session.post(SEND_OOB_URL, json={"requestType": "VERIFY_EMAIL", "idToken": tok})
                oob_code = await check_email_for_code(sid_token)
                if oob_code: 
                    await session.post(UPDATE_URL, json={"oobCode": oob_code})

                payload_data = bf({"localID": fuid[:8].upper(), "Name": game_name, "money": 50000000, "coin": 29000}, fuid)
                await session.post(SAVE_URL, json={"data": {"data": payload_data, "deviceId": fuid[:8]}}, headers={**HDR, "Authorization": "Bearer " + tok})

                rating = {"time": 999999999999, "cars": 999999, "car_fix": 999999, "drift_max": 9999999, "race_win": 999999, "levels": 99999, "gifts": 99999}
                for url in RANK_URLS:
                    await session.post(url, json={"data": json.dumps({"RatingData": rating})}, headers={**HDR, "Authorization": "Bearer " + tok})

            # حفظ آمن في قاعدة البيانات
            ips[client_ip] = {"count": 1, "last_time": now}
            db["total_created"] = db.get("total_created", 0) + 1
            await save_db_safe(db)

            return {"success": True, "email": temp_email, "password": password}
            
        except Exception as e:
            return {"success": False, "error": "حدث خطأ غير متوقع. حاول لاحقاً."}

# ==================== لوحة تحكم المطور (Admin) ====================
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>Admin Panel</title>
<style>
    body { background: #050505; color: white; font-family: 'Cairo', sans-serif; padding: 20px; }
    .box { background: #1a1a1a; padding: 30px; border-radius: 15px; max-width: 600px; margin: auto; border: 1px solid #ffd700; box-shadow: 0 0 20px rgba(255,215,0,0.1); }
    h1 { color: #ffd700; text-align: center; }
    .btn { background: #ffd700; color: black; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; margin-top: 10px; font-family: inherit; }
    .btn:hover { background: #e6c200; }
</style>
</head>
<body>
    <div class="box">
        <h1>⚡ لوحة تحكم المطور</h1>
        <p style="font-size:18px;">👥 إجمالي الحسابات المنشأة: <b style="color:#ffd700;">__TOTAL__</b></p>
        <p style="font-size:18px;">🛠️ حالة الموقع: <b style="color:__COLOR__;">__STATUS__</b></p>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/admin/toggle?passkey=__PASSKEY__" class="btn">🔄 تغيير حالة الموقع (تشغيل/إيقاف)</a>
            <a href="/" class="btn" style="background:#333; color:white; margin-right:10px;">🔙 العودة للموقع</a>
        </div>
        
        <h3 style="margin-top: 40px; border-bottom: 1px solid #333; padding-bottom: 10px;">🌐 إحصائيات الـ IP:</h3>
        <ul style="background:#000; padding:20px; border-radius:8px; list-style-type: none; border: 1px solid #222;">
            __IPS_LIST__
        </ul>
    </div>
</body>
</html>
"""

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, passkey: str = ""):
    if passkey != ADMIN_PASSWORD:
        return HTMLResponse("<h1 style='color:red;text-align:center;margin-top:50px;font-family:sans-serif;'>🚫 ممنوع الدخول. أضف كلمة السر في الرابط: /admin?passkey=YOUR_PASSWORD</h1>", status_code=403)

    db = load_db()
    ips_list = "".join([f"<li style='margin-bottom:5px;'>IP: <b>{ip}</b> | الحسابات: {data['count']}</li>" for ip, data in db.get("ips", {}).items()])
    if not ips_list: ips_list = '<li style="color:#888;">لا توجد بيانات بعد.</li>'

    color = "red" if db.get("maintenance") else "#00ff00"
    status = "متوقف (صيانة)" if db.get("maintenance") else "يعمل بشكل ممتاز"

    final_html = ADMIN_TEMPLATE.replace("__TOTAL__", str(db.get("total_created", 0)))\
                               .replace("__COLOR__", color)\
                               .replace("__STATUS__", status)\
                               .replace("__PASSKEY__", passkey)\
                               .replace("__IPS_LIST__", ips_list)
                               
    return HTMLResponse(content=final_html)

@app.get("/admin/toggle")
async def toggle_maintenance(request: Request, passkey: str = ""):
    if passkey != ADMIN_PASSWORD: raise HTTPException(status_code=403, detail="Forbidden")
    db = load_db()
    db["maintenance"] = not db.get("maintenance", False)
    await save_db_safe(db)
    return HTMLResponse("<script>window.location.href = '/admin?passkey=" + passkey + "';</script>")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)