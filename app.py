from flask import Flask, request, jsonify, render_template, session, url_for, redirect, flash
from flask_cors import CORS
import sqlite3
import bcrypt
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from backend.llama_utils import classify_email_tone, detect_spam, summarize_email, rewrite_email_tone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from collections import Counter

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'
CORS(app, supports_credentials=True)

load_dotenv()
DATABASE = 'Sbox.db'

# --- DATABASE INITIALIZATION AND HELPERS ---
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1, is_admin BOOLEAN DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL, recipient_email TEXT NOT NULL,
            subject TEXT, body TEXT, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            opened_at TIMESTAMP NULL, is_spam BOOLEAN DEFAULT 0, tone TEXT, summary TEXT,
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS external_emails (
            id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL, sender_name TEXT NOT NULL,
            recipient_email TEXT NOT NULL, subject TEXT, body TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, tone TEXT, is_spam BOOLEAN DEFAULT 0, summary TEXT,
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    ''')
    admin_email = "admin@sbox.com"
    admin_pass = bcrypt.hashpw("admin@123".encode(), bcrypt.gensalt()).decode()
    c.execute('INSERT OR IGNORE INTO users (email, password_hash, is_admin) VALUES (?, ?, 1)', (admin_email, admin_pass))
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# --- USER AUTHENTICATION & CORE ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'sender_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"status": "fail", "message": "Missing or invalid data"}), 400
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()
        conn.close()
        if user and verify_password(data['password'], user['password_hash']):
            session['user_id'] = user['id']
            session['is_admin'] = bool(user['is_admin'])
            session['email'] = user['email']
            return jsonify({'status': 'success', 'redirect': '/admin_dashboard' if user['is_admin'] else '/sender_dashboard'})
        return jsonify({'status': 'fail', 'message': 'Invalid email or password'}), 401
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = f"{username}@sbox.com"
        password = request.form.get('password')
        if not username or not password: return jsonify({"status": "fail", "error": "All fields are required"}), 400
        if not re.match(r"^[a-zA-Z0-9_.-]+$", username): return jsonify({"status": "fail", "error": "Invalid username"}), 400
        if len(password) < 6: return jsonify({"status": "fail", "error": "Password must be at least 6 characters"}), 400
        conn = get_db()
        if conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
            conn.close()
            return jsonify({"status": "fail", "error": "Username already taken"}), 400
        hashed_password = hash_password(password)
        conn.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', (email, hashed_password))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "User registered successfully"})
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def send_external_email(to_email, subject, body, sbox_sender_name):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("EMAIL_PASS")

    if not sender_email or not sender_password:
        print("Error: Missing SENDER_EMAIL or EMAIL_PASS in .env file.")
        return False

    msg = MIMEMultipart()
    msg["From"] = formataddr((f"{sbox_sender_name} (via Sbox)", sender_email))
    msg["To"] = to_email
    msg["Subject"] = f"(Sbox: {sbox_sender_name}) {subject}"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True
    except Exception as e:
        print("Error sending Gmail:", e)
        return False

# --- DASHBOARD ROUTES ---
@app.route('/sender_dashboard')
def sender_dashboard():
    if 'user_id' not in session: return redirect(url_for('index'))
    user_id = session.get('user_id')
    conn = get_db()
    internal_sent = conn.execute("SELECT e.id, e.recipient_email, e.subject, e.body, strftime('%Y-%m-%d %H:%M', e.sent_at) AS sent_at, CASE WHEN e.opened_at IS NULL THEN NULL ELSE strftime('%Y-%m-%d %H:%M', e.opened_at) END AS opened_at, e.is_spam, e.tone, 'Internal' AS source FROM emails e WHERE e.sender_id = ? ORDER BY e.sent_at DESC", (user_id,)).fetchall()
    external_sent = conn.execute("SELECT ee.id, ee.recipient_email, ee.subject, ee.body, strftime('%Y-%m-%d %H:%M', ee.sent_at) AS sent_at, NULL AS opened_at, ee.is_spam, ee.tone, 'External' AS source FROM external_emails ee WHERE ee.sender_id = ? ORDER BY ee.sent_at DESC", (user_id,)).fetchall()
    conn.close()
    return render_template('sender_dashboard.html', current_user=session.get('email'), current_id=user_id, emails=internal_sent + external_sent)

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('index'))
    conn = get_db()
    users = conn.execute('SELECT id, email, is_active, is_admin FROM users ORDER BY email').fetchall()
    internal_emails = [dict(row) for row in conn.execute('SELECT e.*, u.email as sender_email FROM emails e JOIN users u ON e.sender_id = u.id ORDER BY e.sent_at DESC').fetchall()]
    external_emails = [dict(row) for row in conn.execute('SELECT ee.*, u.email as sender_email FROM external_emails ee JOIN users u ON ee.sender_id = u.id ORDER BY ee.sent_at DESC').fetchall()]
    stats = {
        "active_users": sum(1 for user in users if user['is_active']),
        "total_emails": len(internal_emails) + len(external_emails),
        "spam_emails": sum(1 for email in internal_emails if email['is_spam']) + sum(1 for email in external_emails if email['is_spam']),
        "read_emails": sum(1 for email in internal_emails if email['opened_at'] is not None)
    }
    all_emails = internal_emails + external_emails
    ALL_TONES = sorted(["polite", "urgent", "neutral", "formal", "angry", "friendly", "apologetic", "appreciative", "sarcastic", "confused", "demanding", "encouraging", "threatening", "dismissive"])
    existing_tone_counts = Counter(email['tone'] for email in all_emails if email.get('tone'))
    tone_data = {
        'labels': [tone.capitalize() for tone in ALL_TONES],
        'counts': [existing_tone_counts.get(tone, 0) for tone in ALL_TONES],
        'keys': ALL_TONES
    }
    conn.close()
    return render_template('admin_dashboard.html', users=users, stats=stats, internal_emails=internal_emails, external_emails=external_emails, tone_data=tone_data)

@app.route('/received_emails')
def received_emails():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_email = session.get('email')
    current_id = session.get('user_id')  # Make sure this is set during login
    
    conn = get_db()
    emails = conn.execute("""
        SELECT 
            e.id, e.subject, e.body, e.summary, 
            strftime('%Y-%m-%d %H:%M', e.sent_at) AS sent_at, 
            e.opened_at, e.tone, e.is_spam,
            u.email AS sender_email
        FROM emails e
        JOIN users u ON e.sender_id = u.id
        WHERE e.recipient_email = ?
        ORDER BY e.sent_at DESC
    """, (current_email,)).fetchall()
    conn.close()
    
    return render_template('received_emails.html', 
                         emails=emails, 
                         current_user=current_email,
                         current_id=current_id)  # Pass current_id to template

# --- API AND ACTION ROUTES ---
@app.route('/send', methods=['POST'])
def send_email():
    if 'user_id' not in session: return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    data = request.json
    conn = get_db()
    sender_email_db = conn.execute('SELECT email FROM users WHERE id = ?', (data['sender_id'],)).fetchone()
    if not sender_email_db: return jsonify({'status': 'error', 'message': 'Sender not found'}), 404
    sbox_sender_name = sender_email_db[0].split("@")[0]
    recipient_user = conn.execute('SELECT id FROM users WHERE email = ?', (data['recipient'],)).fetchone()
    
    body_text = data['body']
    tone = classify_email_tone(body_text)
    is_spam = 1 if detect_spam(body_text) else 0
    summary = summarize_email(body_text)

    if recipient_user:
        conn.execute("INSERT INTO emails (sender_id, recipient_email, subject, body, tone, sent_at, is_spam, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",(data['sender_id'], data['recipient'], data['subject'], body_text, tone, datetime.now(), is_spam, summary))
    else:
        # NOTE: External sending via SMTP is commented out, assuming it might not be configured.
        send_external_email(data['recipient'], data['subject'], data['body'], sbox_sender_name)
        conn.execute("INSERT INTO external_emails (sender_id, sender_name, recipient_email, subject, body, tone, sent_at, is_spam, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (data['sender_id'], sbox_sender_name, data['recipient'], data['subject'], body_text, tone, datetime.now(), is_spam, summary))
    
    conn.commit()
    conn.close()
    return jsonify({'message': 'Email processed', 'is_spam': bool(is_spam)}), 200

@app.route('/rewrite_tone', methods=['POST'])
def rewrite_tone_route():
    if 'user_id' not in session: return jsonify({'error': 'Not authenticated'}), 401
    data = request.json
    text = data.get('text')
    tone = data.get('tone')
    if not text or not tone: return jsonify({'error': 'Missing text or tone'}), 400
    rewritten_text = rewrite_email_tone(text, tone)
    return jsonify({'rewritten_text': rewritten_text})

@app.route('/llama_generate_tone', methods=['POST'])
def llama_generate_tone():
    text = request.json.get('text', '')
    result = classify_email_tone(text)
    return jsonify({'tone': result})

@app.route('/llama_generate_spam', methods=['POST'])
def llama_generate_spam():
    text = request.json.get('text', '')
    result = detect_spam(text)
    return jsonify({'spam': result})

@app.route('/summarize_email', methods=["POST"])
def summarize_email_route():
    if 'user_id' not in session: return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    email_id = data.get("email_id")
    if not email_id: return jsonify({"error": "Missing email_id"}), 400
    conn = get_db()
    email = conn.execute("SELECT body, summary FROM emails WHERE id = ? AND recipient_email = ?", (email_id, session.get('email'))).fetchone()
    conn.close()
    if not email: return jsonify({"error": "Email not found or not authorized"}), 404
    if email['summary']:
        return jsonify({"summary": email['summary']})
    else:
        summary = summarize_email(email['body'])
        return jsonify({"summary": summary})

@app.route('/mark_email_read/<int:email_id>', methods=['POST'])
def mark_email_read(email_id):
    if 'user_id' not in session: return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    user_email = session.get('email')
    conn = get_db()
    conn.execute("UPDATE emails SET opened_at = ? WHERE id = ? AND recipient_email = ? AND opened_at IS NULL", (datetime.now(), email_id, user_email))
    conn.commit()
    email_info = conn.execute("SELECT tone, is_spam FROM emails WHERE id = ?", (email_id,)).fetchone()
    conn.close()
    return jsonify({
        'status': 'success',
        'tone': email_info['tone'] if email_info else None,
        'is_spam': bool(email_info['is_spam']) if email_info else False
    })

@app.route("/admin/delete_email/<int:email_id>", methods=["DELETE"])
def delete_email(email_id):
    # This is a placeholder for deleting internal/external emails
    # A more robust implementation would check both tables
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM emails WHERE id = ?", (email_id,))
    cur.execute("DELETE FROM external_emails WHERE id = ?", (email_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


if __name__ == '__main__':
    app.run(debug=True)