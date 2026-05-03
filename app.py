from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import hashlib
import os
import random
import string
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "flask_secret_key_2024_fixed"

# ===================== Language Helper =====================
def get_lang():
    # Priority: form POST > cookie > default ar
    if request.method == 'POST':
        form_lang = request.form.get('lang', '')
        if form_lang in ('ar', 'en'):
            return form_lang
    return request.cookies.get('lang', 'ar')

def t(ar_text, en_text):
    """Return ar or en text based on current lang."""
    return en_text if get_lang() == 'en' else ar_text

# ===================== Email Config =====================
GMAIL_USER = "badreldinmarzoke73@gmail.com"
GMAIL_PASS = "eoatvnlfparvgkej"

# ===================== Gemini Config =====================
GEMINI_API_KEY =  "your-api-key-here"
GEMINI_MODEL   = "gemini-2.5-flash"

def get_ai_model():
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(GEMINI_MODEL)

# ===================== AES Encryption =====================
AES_KEY = b"FlaskApp2024Key!"  # 16 bytes key

def encrypt_message(text):
    try:
        cipher     = AES.new(AES_KEY, AES.MODE_CBC)
        ct_bytes   = cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))
        iv         = base64.b64encode(cipher.iv).decode("utf-8")
        ct         = base64.b64encode(ct_bytes).decode("utf-8")
        return iv + ":" + ct
    except Exception:
        return text

def decrypt_message(encrypted):
    try:
        iv_str, ct_str = encrypted.split(":")
        iv      = base64.b64decode(iv_str)
        ct      = base64.b64decode(ct_str)
        cipher  = AES.new(AES_KEY, AES.MODE_CBC, iv)
        pt      = unpad(cipher.decrypt(ct), AES.block_size)
        return pt.decode("utf-8")
    except Exception:
        return encrypted

# ===================== DB Connection =====================
def get_db():
    return mysql.connector.connect(
        host="localhost", user="root", password="", database="flask_app"
    )

def init_db():
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            first_name  VARCHAR(100) NOT NULL,
            last_name   VARCHAR(100) NOT NULL,
            email       VARCHAR(255) NOT NULL UNIQUE,
            password    VARCHAR(32)  NOT NULL,
            is_verified TINYINT(1)   DEFAULT 0,
            created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            email      VARCHAR(255) NOT NULL,
            code       VARCHAR(6)   NOT NULL,
            purpose    VARCHAR(20)  NOT NULL,
            created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            user_id    INT NOT NULL,
            title      VARCHAR(255) DEFAULT 'محادثة جديدة',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            session_id INT NOT NULL,
            role       VARCHAR(10) NOT NULL,
            message    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# ===================== Email Helper =====================
def send_email(to_email, subject, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def generate_otp():
    return "".join(random.choices(string.digits, k=6))

def save_otp(email, code, purpose):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM otp_codes WHERE email=%s AND purpose=%s", (email, purpose))
    cursor.execute("INSERT INTO otp_codes (email, code, purpose) VALUES (%s,%s,%s)", (email, code, purpose))
    conn.commit()
    cursor.close()
    conn.close()

def verify_otp(email, code, purpose):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM otp_codes WHERE email=%s AND code=%s AND purpose=%s "
        "AND created_at >= NOW() - INTERVAL 15 MINUTE",
        (email, code, purpose)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row is not None

def delete_otp(email, purpose):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM otp_codes WHERE email=%s AND purpose=%s", (email, purpose))
    conn.commit()
    cursor.close()
    conn.close()

# ===================== Routes =====================

@app.route("/")
def index():
    return redirect(url_for("login"))

# ── Register Step 1 ──
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name","").strip()
        last_name  = request.form.get("last_name", "").strip()
        email      = request.form.get("email",     "").strip()
        password   = request.form.get("password",  "").strip()

        if not all([first_name, last_name, email, password]):
            return render_template("register.html", error=t("يرجى ملء جميع الحقول", "Please fill in all fields"))
        if len(password) < 8:
            return render_template("register.html", error=t("كلمة السر قصيرة جداً (8 أحرف على الأقل)", "Password is too short (at least 8 characters)"))

        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND is_verified=1", (email,))
        existing = cursor.fetchone()
        cursor.close()
        conn.close()
        if existing:
            return render_template("register.html", error=t("البريد الإلكتروني مسجل مسبقاً", "This email is already registered"))

        session["reg_first_name"] = first_name
        session["reg_last_name"]  = last_name
        session["reg_email"]      = email
        session["reg_password"]   = password

        otp  = generate_otp()
        save_otp(email, otp, "verify")
        if get_lang() == 'en':
            html = f"""
            <div style="font-family:Arial,sans-serif;direction:ltr;text-align:left;max-width:500px;margin:auto">
              <h2 style="color:#6c63ff">Email Verification</h2>
              <p>Hello {first_name},</p>
              <p>Your verification code is:</p>
              <div style="font-size:36px;font-weight:bold;letter-spacing:10px;color:#6c63ff;
                          background:#f0eeff;padding:20px;border-radius:12px;text-align:center">{otp}</div>
              <p style="color:#888;font-size:13px;margin-top:16px">Valid for 15 minutes only.</p>
            </div>"""
            subject = "Registration Verification Code"
        else:
            html = f"""
            <div style="font-family:Arial,sans-serif;direction:rtl;text-align:right;max-width:500px;margin:auto">
              <h2 style="color:#6c63ff">تأكيد البريد الإلكتروني</h2>
              <p>مرحباً {first_name}،</p>
              <p>رمز التأكيد الخاص بك هو:</p>
              <div style="font-size:36px;font-weight:bold;letter-spacing:10px;color:#6c63ff;
                          background:#f0eeff;padding:20px;border-radius:12px;text-align:center">{otp}</div>
              <p style="color:#888;font-size:13px;margin-top:16px">صالح لمدة 15 دقيقة فقط.</p>
            </div>"""
            subject = "رمز تأكيد التسجيل"
        if not send_email(email, subject, html):
            return render_template("register.html", error=t("فشل إرسال الإيميل", "Failed to send email"))
        return redirect(url_for("verify_email"))

    return render_template("register.html")

# ── Register Step 2 ──
@app.route("/verify-email", methods=["GET","POST"])
def verify_email():
    email  = session.get("reg_email")
    resent = request.args.get("resent")
    if not email:
        return redirect(url_for("register"))

    if request.method == "POST":
        code = request.form.get("code","").strip()
        if not verify_otp(email, code, "verify"):
            return render_template("verify_email.html", email=email,
                                   error=t("الرمز غير صحيح أو انتهت صلاحيته (15 دقيقة)", "Invalid or expired code (15 minutes)"))

        hashed = hashlib.md5(session["reg_password"].encode()).hexdigest()
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email=%s AND is_verified=0", (email,))
        cursor.execute(
            "INSERT INTO users (first_name,last_name,email,password,is_verified) VALUES (%s,%s,%s,%s,1)",
            (session["reg_first_name"], session["reg_last_name"], email, hashed)
        )
        conn.commit()
        cursor.close()
        conn.close()
        delete_otp(email, "verify")
        for k in ["reg_first_name","reg_last_name","reg_email","reg_password"]:
            session.pop(k, None)
        return redirect(url_for("login") + "?registered=1")

    return render_template("verify_email.html", email=email, resent=resent)

@app.route("/resend-otp")
def resend_otp():
    email = session.get("reg_email")
    if not email:
        return redirect(url_for("register"))
    otp  = generate_otp()
    save_otp(email, otp, "verify")
    if get_lang() == 'en':
        html = f"""
        <div style="font-family:Arial,sans-serif;direction:ltr;text-align:left">
          <h2 style="color:#6c63ff">New Verification Code</h2>
          <div style="font-size:36px;font-weight:bold;letter-spacing:10px;color:#6c63ff;
                      background:#f0eeff;padding:20px;border-radius:12px;text-align:center">{otp}</div>
          <p style="color:#888;font-size:13px">Valid for 15 minutes.</p>
        </div>"""
        send_email(email, "New Verification Code", html)
    else:
        html = f"""
        <div style="font-family:Arial,sans-serif;direction:rtl;text-align:right">
          <h2 style="color:#6c63ff">رمز تأكيد جديد</h2>
          <div style="font-size:36px;font-weight:bold;letter-spacing:10px;color:#6c63ff;
                      background:#f0eeff;padding:20px;border-radius:12px;text-align:center">{otp}</div>
          <p style="color:#888;font-size:13px">صالح لمدة 15 دقيقة.</p>
        </div>"""
        send_email(email, "رمز تأكيد جديد", html)
    return redirect(url_for("verify_email") + "?resent=1")

# ── Password Strength ──
@app.route("/check_password", methods=["POST"])
def check_password():
    password = request.json.get("password","")
    lang = get_lang()
    if not password:
        return jsonify({"score":0,"label": "Empty" if lang=="en" else "فارغة","feedback":"","color":"#555"})
    try:
        model    = get_ai_model()
        if lang == "en":
            prompt = (
                f"Rate the strength of this password from 0 to 100 in English.\n"
                f"Password: {password}\n"
                f"Reply with JSON only, no extra text or backticks:\n"
                f"{{\"score\":85,\"label\":\"Strong\",\"feedback\":\"short tip\"}}"
            )
        else:
            prompt = (
                f"قيّم قوة كلمة السر التالية من 0 إلى 100 باللغة العربية.\n"
                f"كلمة السر: {password}\n"
                f"الرد JSON فقط بدون أي نص إضافي أو backticks:\n"
                f"{{\"score\":85,\"label\":\"قوية\",\"feedback\":\"نصيحة قصيرة\"}}"
            )
        response = model.generate_content(prompt)
        import json, re
        text  = response.text.strip()
        clean = re.sub(r"```json|```","",text).strip()
        data  = json.loads(clean)
        score = int(data.get("score",50))
        default_label = "Medium" if lang=="en" else "متوسطة"
        return jsonify({"score":score,"label":data.get("label", default_label),
                        "feedback":data.get("feedback",""),"color":score_to_color(score)})
    except Exception:
        score, label, color = basic_strength(password, lang)
        return jsonify({"score":score,"label":label,"feedback":"","color":color})

# ── Generate Password ──
@app.route("/generate_password", methods=["POST"])
def generate_password():
    try:
        model    = get_ai_model()
        prompt   = "أنشئ كلمة سر قوية 16 حرفاً. الرد JSON فقط بدون backticks: {\"password\":\"...\"}"
        response = model.generate_content(prompt)
        import json, re
        text  = response.text.strip()
        clean = re.sub(r"```json|```","",text).strip()
        data  = json.loads(clean)
        return jsonify({"password":data.get("password","Str0ng!Pass#2024")})
    except Exception:
        import secrets
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return jsonify({"password":"".join(secrets.choice(chars) for _ in range(16))})

# ── Login ──
@app.route("/login", methods=["GET","POST"])
def login():
    registered = request.args.get("registered")
    reset_done = request.args.get("reset")
    if request.method == "POST":
        email    = request.form.get("email",   "").strip()
        password = request.form.get("password","").strip()
        if not email or not password:
            return render_template("login.html", error=t("يرجى ملء جميع الحقول", "Please fill in all fields"))
        hashed = hashlib.md5(password.encode()).hexdigest()
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s AND is_verified=1",
                       (email, hashed))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            session["user_id"]   = user["id"]
            session["user_name"] = user["first_name"]
            return redirect(url_for("chatbot"))
        return render_template("login.html", error=t("البريد أو كلمة السر غير صحيحة", "Invalid email or password"))
    return render_template("login.html", registered=registered, reset_done=reset_done)

# ── Forgot Password Step 1 ──
@app.route("/forgot-password", methods=["GET","POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        if not email:
            return render_template("forgot_password.html", error=t("أدخل بريدك الإلكتروني", "Please enter your email"))
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND is_verified=1", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user:
            return render_template("forgot_password.html", error=t("البريد غير مسجل أو غير مفعّل", "Email not found or not verified"))

        otp = generate_otp()
        save_otp(email, otp, "reset")
        session["reset_email"] = email

        if get_lang() == 'en':
            html = f"""
            <div style="font-family:Arial,sans-serif;direction:ltr;text-align:left;max-width:500px;margin:auto">
              <h2 style="color:#e74c3c">Reset Your Password</h2>
              <p>Hello {user['first_name']},</p>
              <p>Your password reset code is:</p>
              <div style="font-size:36px;font-weight:bold;letter-spacing:10px;color:#e74c3c;
                          background:#ffeeed;padding:20px;border-radius:12px;text-align:center">{otp}</div>
              <p style="color:#888;font-size:13px;margin-top:16px">Valid for 15 minutes only.</p>
            </div>"""
            subject = "Password Reset Code"
        else:
            html = f"""
            <div style="font-family:Arial,sans-serif;direction:rtl;text-align:right;max-width:500px;margin:auto">
              <h2 style="color:#e74c3c">إعادة تعيين كلمة السر</h2>
              <p>مرحباً {user['first_name']}،</p>
              <p>رمز إعادة التعيين هو:</p>
              <div style="font-size:36px;font-weight:bold;letter-spacing:10px;color:#e74c3c;
                          background:#ffeeed;padding:20px;border-radius:12px;text-align:center">{otp}</div>
              <p style="color:#888;font-size:13px;margin-top:16px">صالح لمدة 15 دقيقة فقط.</p>
            </div>"""
            subject = "رمز إعادة تعيين كلمة السر"
        if not send_email(email, subject, html):
            return render_template("forgot_password.html", error=t("فشل إرسال الإيميل", "Failed to send email"))
        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")

# ── Forgot Password Step 2 ──
@app.route("/reset-password", methods=["GET","POST"])
def reset_password():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        code      = request.form.get("code",     "").strip()
        new_pass  = request.form.get("password", "").strip()
        new_pass2 = request.form.get("password2","").strip()

        if not code or not new_pass or not new_pass2:
            return render_template("reset_password.html", email=email, error=t("يرجى ملء جميع الحقول", "Please fill in all fields"))
        if new_pass != new_pass2:
            return render_template("reset_password.html", email=email, error=t("كلمتا السر غير متطابقتين", "Passwords do not match"))
        if len(new_pass) < 8:
            return render_template("reset_password.html", email=email, error=t("كلمة السر قصيرة جداً", "Password is too short"))
        if not verify_otp(email, code, "reset"):
            return render_template("reset_password.html", email=email,
                                   error=t("الرمز غير صحيح أو انتهت صلاحيته", "Invalid or expired code"))

        hashed = hashlib.md5(new_pass.encode()).hexdigest()
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, email))
        conn.commit()
        cursor.close()
        conn.close()
        delete_otp(email, "reset")
        session.pop("reset_email", None)
        return redirect(url_for("login") + "?reset=1")

    return render_template("reset_password.html", email=email)

# ── Chatbot ──
@app.route("/chatbot")
def chatbot():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("chatbot.html", user_name=session.get("user_name",""), lang=get_lang())

# ── Get past sessions (last 7 days) ──
@app.route("/get_sessions")
def get_sessions():
    if "user_id" not in session:
        return jsonify([])
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, title, created_at FROM chat_sessions
        WHERE user_id=%s AND created_at >= NOW() - INTERVAL 7 DAY
        ORDER BY created_at DESC
    """, (session["user_id"],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([{"id": r["id"], "title": r["title"],
                     "date": r["created_at"].strftime("%Y-%m-%d %H:%M")} for r in rows])

# ── Get messages of a session ──
@app.route("/get_session_messages/<int:session_id>")
def get_session_messages(session_id):
    if "user_id" not in session:
        return jsonify([])
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    # verify ownership
    cursor.execute("SELECT id FROM chat_sessions WHERE id=%s AND user_id=%s",
                   (session_id, session["user_id"]))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify([])
    cursor.execute("SELECT role, message FROM chat_messages WHERE session_id=%s ORDER BY id ASC",
                   (session_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([{"role": r["role"], "message": decrypt_message(r["message"])} for r in rows])

# ── Chat ──
@app.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"error":"غير مسجل"}), 401

    user_msg   = request.json.get("message","").strip()
    history    = request.json.get("history",[])
    session_id = request.json.get("session_id", None)

    if not user_msg:
        return jsonify({"reply":"الرسالة فارغة!"})

    # Create new session if needed
    conn   = get_db()
    cursor = conn.cursor()
    if not session_id:
        title = user_msg[:40] + ("..." if len(user_msg) > 40 else "")
        cursor.execute("INSERT INTO chat_sessions (user_id, title) VALUES (%s,%s)",
                       (session["user_id"], title))
        conn.commit()
        session_id = cursor.lastrowid

    # Save user message (encrypted)
    cursor.execute("INSERT INTO chat_messages (session_id, role, message) VALUES (%s,%s,%s)",
                   (session_id, "user", encrypt_message(user_msg)))
    conn.commit()
    cursor.close()
    conn.close()

    try:
        model = get_ai_model()
        chat_history = []
        for msg in history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})

        convo    = model.start_chat(history=chat_history)
        response = convo.send_message(user_msg)
        reply    = response.text

        # Save bot reply (encrypted)
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_messages (session_id, role, message) VALUES (%s,%s,%s)",
                       (session_id, "bot", encrypt_message(reply)))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"reply": reply, "session_id": session_id})
    except Exception as e:
        return jsonify({"reply": t(f"حدث خطأ: {str(e)}", f"An error occurred: {str(e)}"), "session_id": session_id})

# ── Logout ──
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ===================== Helpers =====================
def basic_strength(pwd, lang="ar"):
    score = 0
    if len(pwd) >= 8:  score += 20
    if len(pwd) >= 12: score += 20
    if any(c.isupper() for c in pwd): score += 20
    if any(c.isdigit() for c in pwd): score += 20
    if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in pwd): score += 20
    if lang == "en":
        if score <= 20: return score, "Very Weak",   "#e74c3c"
        if score <= 40: return score, "Weak",        "#e67e22"
        if score <= 60: return score, "Medium",      "#f1c40f"
        if score <= 80: return score, "Good",        "#2ecc71"
        return score, "Very Strong", "#1abc9c"
    else:
        if score <= 20: return score, "ضعيفة جداً", "#e74c3c"
        if score <= 40: return score, "ضعيفة",      "#e67e22"
        if score <= 60: return score, "متوسطة",     "#f1c40f"
        if score <= 80: return score, "جيدة",       "#2ecc71"
        return score, "قوية جداً", "#1abc9c"

def score_to_color(score):
    if score <= 20: return "#e74c3c"
    if score <= 40: return "#e67e22"
    if score <= 60: return "#f1c40f"
    if score <= 80: return "#2ecc71"
    return "#1abc9c"

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
