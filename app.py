from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import os, random, time
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

# ==================== ⚙️ إعدادات ====================
ADMIN_PASSWORD = "admin123"

# ⚠️ ضع رابط قاعدة البيانات هنا (بعد استبدال كلمة السر)
# ⚠️ أو قم بتعيينه كـ Environment Variable في Render باسم MONGO_URI
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority")

client = AsyncIOMotorClient(MONGO_URI)
db = client.cpm_vault
accounts_col = db.accounts
ips_col = db.ips

# ==================== 🎨 الواجهة الرئيسية ====================
HTML_MAIN = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Secret CPM Vault</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800;900&display=swap" rel="stylesheet">
    <style>
        :root { --primary: #8a2be2; --glow: rgba(138, 43, 226, 0.4); --bg: #020204; }
        * { box-sizing: border-box; font-family: 'Outfit', sans-serif; margin: 0; padding: 0; }
        body { background-color: var(--bg); color: #fff; height: 100vh; display: flex; justify-content: center; align-items: center; overflow: hidden; position: relative; }
        .stars { position: absolute; width: 100%; height: 100%; z-index: 0; overflow: hidden; }
        .star { position: absolute; background: white; border-radius: 50%; opacity: 0.5; animation: twinkle infinite alternate; }
        @keyframes twinkle { from { opacity: 0.1; transform: scale(0.8); } to { opacity: 0.8; transform: scale(1.2); box-shadow: 0 0 10px white; } }
        .vault-card { position: relative; z-index: 10; width: 100%; max-width: 400px; background: rgba(10, 10, 15, 0.7); backdrop-filter: blur(20px); border: 1px solid rgba(138, 43, 226, 0.3); border-radius: 30px; padding: 40px 30px; text-align: center; box-shadow: 0 0 50px rgba(138, 43, 226, 0.15); animation: floatCard 6s ease-in-out infinite; }
        @keyframes floatCard { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-15px); } }
        .orb { width: 100px; height: 100px; margin: 0 auto 25px auto; border-radius: 50%; background: radial-gradient(circle, rgba(138, 43, 226, 0.8) 0%, transparent 70%); border: 2px solid var(--primary); display: flex; justify-content: center; align-items: center; font-size: 40px; box-shadow: 0 0 30px var(--glow); animation: pulseOrb 2s infinite alternate; }
        @keyframes pulseOrb { from { box-shadow: 0 0 20px var(--glow); } to { box-shadow: 0 0 60px var(--glow), 0 0 100px var(--primary); transform: scale(1.05); } }
        h1 { font-size: 28px; font-weight: 900; margin-bottom: 10px; color: #fff; text-shadow: 0 0 10px var(--glow); }
        p { font-size: 14px; color: #888; margin-bottom: 30px; line-height: 1.6; }
        .btn { width: 100%; padding: 18px; border: none; border-radius: 16px; background: linear-gradient(45deg, #4b0082, #8a2be2); color: #fff; font-size: 18px; font-weight: 800; cursor: pointer; box-shadow: 0 0 20px var(--glow); transition: 0.3s; }
        .btn:hover { transform: scale(1.02); box-shadow: 0 0 40px var(--glow); }
        
        .account-box { display: none; text-align: right; margin-top: 20px; animation: slideUp 0.5s ease; }
        .data-row { background: rgba(0,0,0,0.5); padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; }
        .data-row span { font-family: monospace; font-size: 15px; color: #00ffcc; direction: ltr; }
        .copy-btn { background: rgba(255,255,255,0.1); border: none; color: #fff; padding: 5px 10px; border-radius: 6px; cursor: pointer; }
        .copy-btn:hover { background: var(--primary); }
        
        #error-box { display: none; background: rgba(255, 0, 0, 0.2); border: 1px solid red; color: #ff9999; padding: 15px; border-radius: 12px; margin-top: 20px; font-weight: bold; line-height: 1.6; }
        
        .trust-msg { margin-top: 20px; padding: 15px; background: rgba(255, 215, 0, 0.1); border: 1px dashed #ffd700; border-radius: 12px; color: #ffd700; font-size: 14px; font-weight: 600; display: none; animation: blink 2s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="stars" id="stars"></div>
    <div class="vault-card">
        <div class="orb">🔐</div>
        <h1>CPM SECRET VAULT</h1>
        <p>خزنة الحسابات السرية. اضغط للحصول على حسابك العشوائي قبل نفاد الكمية.</p>
        
        <button class="btn" id="main-btn" onclick="getAccount()">احصل على حساب الآن 🚀</button>
        
        <div id="error-box"></div>

        <div class="account-box" id="account-box">
            <div class="data-row">
                <div><b>Email:</b><br><span id="res-email"></span></div>
                <button class="copy-btn" onclick="copy('res-email')">نسخ</button>
            </div>
            <div class="data-row">
                <div><b>Password:</b><br><span id="res-pass"></span></div>
                <button class="copy-btn" onclick="copy('res-pass')">نسخ</button>
            </div>
        </div>
        <div class="trust-msg" id="trust-msg">⚠️ لا تنسَ ترك "إثبات" أو "كلمة ثقة" في التعليقات لدعمنا! 🙏</div>
    </div>

    <script>
        const starsContainer = document.getElementById('stars');
        for(let i=0; i<50; i++) {
            let star = document.createElement('div'); star.className = 'star';
            star.style.width = Math.random() * 3 + 'px'; star.style.height = star.style.width;
            star.style.left = Math.random() * 100 + '%'; star.style.top = Math.random() * 100 + '%';
            star.style.animationDuration = (Math.random() * 3 + 1) + 's'; star.style.animationDelay = Math.random() * 2 + 's';
            starsContainer.appendChild(star);
        }

        async function getAccount() {
            const btn = document.getElementById('main-btn');
            const errBox = document.getElementById('error-box');
            const accBox = document.getElementById('account-box');
            const trustMsg = document.getElementById('trust-msg');

            btn.innerText = "⏳ جاري السحب...";
            btn.disabled = true;
            errBox.style.display = 'none';
            accBox.style.display = 'none';
            trustMsg.style.display = 'none';

            try {
                const res = await fetch('/api/get_account', { method: 'POST' });
                const data = await res.json();
                
                btn.disabled = false;
                btn.innerText = "احصل على حساب آخر 🚀";

                if (data.success) {
                    accBox.style.display = 'block';
                    trustMsg.style.display = 'block';
                    document.getElementById('res-email').innerText = data.email;
                    document.getElementById('res-pass').innerText = data.password;
                } else {
                    errBox.innerText = "❌ " + data.error;
                    errBox.style.display = 'block';
                }
            } catch(e) {
                btn.disabled = false;
                btn.innerText = "احصل على حساب الآن 🚀";
                errBox.innerText = "❌ حدث خطأ في الاتصال بالسيرفر.";
                errBox.style.display = 'block';
            }
        }

        function copy(id) {
            navigator.clipboard.writeText(document.getElementById(id).innerText);
            alert("تم النسخ بنجاح!");
        }
    </script>
</body>
</html>
"""

# ==================== 👑 لوحة الأدمن ====================
ADMIN_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>Admin - Stock</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { background: #020204; color: #fff; font-family: 'Outfit', sans-serif; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .box { width: 100%; max-width: 600px; background: #111; padding: 30px; border-radius: 24px; border: 1px solid #8a2be2; }
        h1 { text-align: center; color: #8a2be2; margin-bottom: 20px; }
        .tabs { display: flex; margin-bottom: 20px; border-bottom: 1px solid #333; }
        .tab { flex: 1; text-align: center; padding: 10px; cursor: pointer; color: #888; font-weight: bold; }
        .tab.active { color: #8a2be2; border-bottom: 2px solid #8a2be2; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        textarea { width: 100%; height: 150px; padding: 15px; margin-bottom: 15px; background: #000; border: 1px dashed #555; border-radius: 12px; color: #fff; font-family: monospace; box-sizing: border-box; resize: vertical; }
        input[type="file"] { width: 100%; padding: 15px; margin-bottom: 15px; background: #000; border: 1px dashed #555; border-radius: 12px; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 15px; background: #8a2be2; color: #fff; font-weight: bold; border: none; border-radius: 12px; cursor: pointer; font-size: 16px; }
        button:hover { background: #6a1b9a; }
        .stats { text-align: center; margin-top: 20px; padding: 15px; background: rgba(0, 255, 0, 0.1); border: 1px solid lime; border-radius: 12px; color: lime; font-weight: bold; font-size: 18px; }
        .back-link { display: block; text-align: center; margin-top: 20px; color: #aaa; text-decoration: none; }
    </style>
</head>
<body>
    <div class="box">
        <h1>إدارة المخزون</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="switchTab('manual')">إدخال يدوي</div>
            <div class="tab" onclick="switchTab('file')">رفع ملف txt</div>
        </div>

        <div id="manual" class="tab-content active">
            <form action="/admin/add_manual" method="post">
                <input type="hidden" name="passkey" value="__PASSKEY__">
                <textarea name="accounts_data" placeholder="الصق الحسابات هنا بهذا الشكل:&#10;email1@gmail.com:pass123&#10;email2@gmail.com:pass456" required></textarea>
                <button type="submit">إضافة الحسابات للمخزون ➕</button>
            </form>
        </div>

        <div id="file" class="tab-content">
            <form action="/admin/upload" method="post" enctype="multipart/form-data">
                <input type="hidden" name="passkey" value="__PASSKEY__">
                <input type="file" name="file" accept=".txt" required>
                <button type="submit">رفع الملف 🚀</button>
            </form>
        </div>

        <div class="stats">📦 الحسابات المتوفرة حالياً: __COUNT__</div>
        <a href="/admin?passkey=__PASSKEY__" class="back-link">🔄 تحديث الصفحة</a>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }
    </script>
</body>
</html>
"""

# ==================== 🛠️ مسارات الموقع ====================
@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_MAIN

@app.post("/api/get_account")
async def get_account(request: Request):
    client_ip = request.client.host
    now = time.time()

    # 1. التحقق من الـ IP في قاعدة البيانات
    ip_doc = await ips_col.find_one({"_id": client_ip})
    if ip_doc:
        time_passed = now - ip_doc["last_claimed"]
        if time_passed < 86400: # 24 ساعة
            remain_sec = 86400 - time_passed
            hours = int(remain_sec // 3600)
            minutes = int((remain_sec % 3600) // 60)
            return {
                "success": False, 
                "error": f"عذراً، يمكنك الحصول على حساب واحد فقط كل 24 ساعة.\nمتبقي لك: {hours} ساعة و {minutes} دقيقة."
            }

    # 2. سحب حساب عشوائي وتحديث حالته إلى "مأخوذ" (بشكل ذري لمنع التعارض)
    acc = await accounts_col.find_one_and_update(
        {"is_taken": False},
        {"$set": {"is_taken": True}}
    )
    
    if not acc:
        return {"success": False, "error": "المخزون فارغ! المطور لم يقم بإضافة حسابات جديدة بعد."}

    # 3. تسجيل الـ IP في قاعدة البيانات
    await ips_col.update_one(
        {"_id": client_ip},
        {"$set": {"last_claimed": now}},
        upsert=True
    )

    return {"success": True, "email": acc["email"], "password": acc["password"]}

# ==================== 👑 مسارات الأدمن ====================
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(passkey: str = ""):
    if passkey != ADMIN_PASSWORD: 
        return HTMLResponse("<h1 style='color:red;text-align:center;font-family:sans-serif;'>🚫 ممنوع</h1>", status_code=403)
    
    # عد الحسابات المتوفرة (غير المأخوذة)
    count = await accounts_col.count_documents({"is_taken": False})
    return HTMLResponse(ADMIN_HTML_TEMPLATE.replace("__PASSKEY__", passkey).replace("__COUNT__", str(count)))

@app.post("/admin/add_manual")
async def admin_add_manual(passkey: str = Form(...), accounts_data: str = Form(...)):
    if passkey != ADMIN_PASSWORD: raise HTTPException(status_code=403)
    
    lines = accounts_data.splitlines()
    docs = []
    for line in lines:
        line = line.strip()
        if ":" in line:
            e, p = line.split(":", 1)
            if e and p:
                docs.append({"email": e.strip(), "password": p.strip(), "is_taken": False})
                
    if docs:
        await accounts_col.insert_many(docs)
        
    return HTMLResponse(f"<script>alert('تم إضافة {len(docs)} حساب بنجاح إلى السحابة!'); window.location.href='/admin?passkey={passkey}';</script>")

@app.post("/admin/upload")
async def admin_upload(passkey: str = Form(...), file: UploadFile = File(...)):
    if passkey != ADMIN_PASSWORD: raise HTTPException(status_code=403)
    
    content = await file.read()
    lines = content.decode("utf-8", errors="ignore").splitlines()
    
    docs = []
    for line in lines:
        if ":" in line:
            e, p = line.split(":", 1)
            if e and p:
                docs.append({"email": e.strip(), "password": p.strip(), "is_taken": False})
                
    if docs:
        await accounts_col.insert_many(docs)
        
    return HTMLResponse(f"<script>alert('تم إضافة {len(docs)} حساب بنجاح إلى السحابة!'); window.location.href='/admin?passkey={passkey}';</script>")

# ==================== 🚀 التشغيل ====================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)