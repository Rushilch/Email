from flask import Flask, request, jsonify, render_template, session, url_for, redirect, flash
from flask_cors import CORS
import sqlite3
import bcrypt
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from backend.llama_utils import generate_llama_response, classify_email_tone, detect_spam, summarize_email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'
CORS(app, supports_credentials=True)

load_dotenv()
DATABASE = 'Sbox.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Internal emails
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            is_admin BOOLEAN DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY,
            sender_id INTEGER NOT NULL,
            recipient_email TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            opened_at TIMESTAMP NULL,
            is_spam BOOLEAN DEFAULT 0,
            tone TEXT,
            summary TEXT,
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    ''')
    # External emails
    c.execute('''
        CREATE TABLE IF NOT EXISTS external_emails (
            id INTEGER PRIMARY KEY,
            sender_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tone TEXT,
            is_spam BOOLEAN DEFAULT 0,
            summary TEXT,
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    ''')
    
    # Create admin account
    admin_email = "admin@sbox.com"
    admin_pass = bcrypt.hashpw("admin@123".encode(), bcrypt.gensalt()).decode()
    c.execute('''
        INSERT OR IGNORE INTO users (email, password_hash, is_admin)
        VALUES (?, ?, 1)
    ''', (admin_email, admin_pass))
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

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'sender_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {
            'email': request.form.get('email'),
            'password': request.form.get('password')
        }
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"status": "fail", "message": "Missing or invalid data"}), 400

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, password_hash, is_admin FROM users WHERE email = ?', (data['email'],))
        row = c.fetchone()
        conn.close()

        if row and verify_password(data['password'], row[1]):
            session['user_id'] = row[0]
            session['is_admin'] = bool(row[2])
            session['email'] = data['email']
            return jsonify({
                'status': 'success',
                'redirect': '/admin_dashboard' if row[2] else '/sender_dashboard'
            })

        return jsonify({'status': 'fail', 'message': 'Invalid email or password'}), 401
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = f"{username}@sbox.com"
        password = request.form.get('password')

        if not username or not password:
            return jsonify({"status": "fail", "error": "All fields are required"}), 400
        if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
            return jsonify({"status": "fail", "error": "Invalid username"}), 400
        if len(password) < 6:
            return jsonify({"status": "fail", "error": "Password must be at least 6 characters"}), 400

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE email = ?', (email,))
        if c.fetchone():
            conn.close()
            return jsonify({"status": "fail", "error": "Username already taken"}), 400

        hashed_password = hash_password(password)
        c.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', (email, hashed_password))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "User registered successfully"})
    return render_template('register.html')

@app.route('/send', methods=['POST'])
def send_email():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401

    data = request.json
    required_keys = ['sender_id', 'recipient', 'subject', 'body']
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        return jsonify({'status': 'error', 'message': f"Missing fields: {', '.join(missing_keys)}"}), 400

    conn = get_db()
    cur = conn.cursor()

    # Get sender name from DB
    cur.execute('SELECT email FROM users WHERE id = ?', (data['sender_id'],))
    sender_email_db = cur.fetchone()
    if not sender_email_db:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Sender not found'}), 404

    sbox_sender_name = sender_email_db[0].split("@")[0]

    # Check if recipient exists internally
    cur.execute('SELECT id FROM users WHERE email = ?', (data['recipient'],))
    recipient_user = cur.fetchone()

    if recipient_user:
        body_text = data['body']
        tone = classify_email_tone(body_text)
        is_spam = 1 if detect_spam(body_text) else 0
        summary = summarize_email(body_text)
        cur.execute("""
            INSERT INTO emails (sender_id, recipient_email, subject, body, tone, sent_at, is_spam, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['sender_id'], data['recipient'], data['subject'], data['body'],
            tone, datetime.now(), is_spam, summary
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Email sent internally', 'is_spam': bool(is_spam)}), 200

    # External email via Gmail SMTP
    if send_external_email(data['recipient'], data['subject'], data['body'], sbox_sender_name):
        tone = classify_email_tone(data['body'])
        is_spam = 1 if detect_spam(data['body']) else 0
        summary = summarize_email(data['body'])
        cur.execute("""
            INSERT INTO external_emails (sender_id, sender_name, recipient_email, subject, body, tone, sent_at, is_spam, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['sender_id'], sbox_sender_name, data['recipient'], data['subject'], data['body'],
            tone, datetime.now(), is_spam, summary
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': f'External email sent via Gmail as {sbox_sender_name}'}), 200
    else:
        conn.close()
        return jsonify({'message': 'Failed to send email externally'}), 500

def send_external_email(to_email, subject, body, sbox_sender_name):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("EMAIL_PASS")

    if not sender_email or not sender_password:
        print("Error: Missing email credentials in environment variables.")
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
@app.route('/sender_dashboard')
def sender_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    current_email = session.get('email')
    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()

    # Internal sent emails
    cur.execute("""
        SELECT 
            e.id, e.recipient_email, e.subject, e.body,
            strftime('%Y-%m-%d %H:%M', e.sent_at) AS sent_at,
            CASE WHEN e.opened_at IS NULL THEN NULL 
                 ELSE strftime('%Y-%m-%d %H:%M', e.opened_at) 
            END AS opened_at,
            e.is_spam, e.tone,
            'Internal' AS source
        FROM emails e
        WHERE e.sender_id = ?
        ORDER BY e.sent_at DESC
    """, (user_id,))
    internal_sent = cur.fetchall()

    # External sent emails
    cur.execute("""
        SELECT 
            ee.id, ee.recipient_email, ee.subject, ee.body,
            strftime('%Y-%m-%d %H:%M', ee.sent_at) AS sent_at,
            NULL AS opened_at,
            ee.is_spam, ee.tone,
            'External' AS source
        FROM external_emails ee
        WHERE ee.sender_id = ?
        ORDER BY ee.sent_at DESC
    """, (user_id,))
    external_sent = cur.fetchall()

    conn.close()

    # Merge both internal & external
    all_sent = internal_sent + external_sent

    return render_template(
        'sender_dashboard.html',
        current_user=current_email,
        current_id=user_id,
        emails=all_sent  # Combined list
    )



@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('You must be logged in as an admin to view this page', 'error')
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()

    # Users
    cur.execute('SELECT id, email, is_active, is_admin FROM users ORDER BY email')
    users = cur.fetchall()

    # Internal emails
    cur.execute('''
        SELECT e.*, u.email as sender_email 
        FROM emails e
        JOIN users u ON e.sender_id = u.id
        ORDER BY e.sent_at DESC
    ''')
    internal_emails = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]

    # External emails
    cur.execute('''
        SELECT ee.*, u.email as sender_email 
        FROM external_emails ee
        JOIN users u ON ee.sender_id = u.id
        ORDER BY ee.sent_at DESC
    ''')
    external_emails = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]

    # Stats
    stats = {
        "active_users": cur.execute('SELECT COUNT(*) FROM users WHERE is_active = 1').fetchone()[0],
        "total_emails": cur.execute('SELECT COUNT(*) FROM emails').fetchone()[0] + 
                        cur.execute('SELECT COUNT(*) FROM external_emails').fetchone()[0],
        "spam_emails": cur.execute('SELECT COUNT(*) FROM emails WHERE is_spam = 1').fetchone()[0] +
                       cur.execute('SELECT COUNT(*) FROM external_emails WHERE is_spam = 1').fetchone()[0],
        "read_emails": cur.execute('SELECT COUNT(*) FROM emails WHERE opened_at IS NOT NULL').fetchone()[0]
    }

    conn.close()

    return render_template(
        'admin_dashboard.html',
        users=users,
        stats=stats,
        internal_emails=internal_emails,
        external_emails=external_emails,
        current_user=session.get('email')
    )


@app.route('/admin/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM emails WHERE sender_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'User permanently removed'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/llama_generate_tone', methods=['POST'])
def llama_generate_tone():
    try:
        text = request.json.get('text', '')
        result = classify_email_tone(text)
        raw = generate_llama_response(f"Email: {text}\nAnswer:", max_tokens=10)
        return jsonify({'tone': result, 'raw': raw})
    except Exception as e:
        return jsonify({'error': 'LLaMA Tone Generation Failed', 'details': str(e)}), 500

@app.route('/llama_generate_spam', methods=['POST'])
def llama_generate_spam():
    try:
        text = request.json.get('text', '')
        result = detect_spam(text)
        raw = generate_llama_response(f"Email: {text}\nAnswer:", max_tokens=5)
        return jsonify({'spam': result, 'raw': raw})
    except Exception as e:
        return jsonify({'error': 'LLaMA Spam Detection Failed', 'details': str(e)}), 500

@app.route('/summarize_email/<int:email_id>')
def summarize_email_by_id(email_id):
    """
    Summarize an email from DB by its id, matching JS inbox fetch(`/summarize_email/${id}`).
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    conn = get_db()
    cur = conn.cursor()
    # Only allow access to their received emails
    user_email = session.get('email')
    cur.execute("SELECT body, summary FROM emails WHERE id = ? AND recipient_email = ?", (email_id, user_email))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Email not found or not authorized'}), 404
    # Use precomputed summary if present, else use the llama_utils fallback
    summary = row['summary'] or summarize_email(row['body'])
    conn.close()
    return jsonify({'summary': summary})

@app.route('/summarize_email', methods=["POST"])
def summarize_email_route():
    data = request.get_json()
    email_text = data.get("email_text", "")
    if not email_text:
        return jsonify({"error": "Missing email_text"}), 400
    summary = summarize_email(email_text)
    return jsonify({"summary": summary})

def send_external_email(to_email, subject, body, sbox_sender_name):
    sender_email = os.getenv("SENDER_EMAIL")  # Gmail sending account
    sender_password = os.getenv("EMAIL_PASS") # Gmail App Password

    if not sender_email or not sender_password:
        print("Error: Missing email credentials in environment variables.")
        return False

    msg = MIMEMultipart()
    # Show "John (via Sbox)" as the sender name
    msg["From"] = formataddr((f"{sbox_sender_name} (via Sbox)", sender_email))
    msg["To"] = to_email
    # Add "(Sbox: John)" in subject
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

@app.route("/admin/delete_email/<int:email_id>", methods=["DELETE"])
def delete_email(email_id):
    try:
        conn = get_db()
        cur = conn.cursor()

        # Delete the email
        cur.execute("DELETE FROM emails WHERE id = ?", (email_id,))
        conn.commit()

        if cur.rowcount == 0:
            # No email found with given ID
            return jsonify({"status": "error", "message": "Email not found"}), 404

        return jsonify({"status": "success", "message": "Email deleted successfully"}), 200

    except Exception as e:
        print("Error deleting email:", e)
        return jsonify({"status": "error", "message": "Server error"}), 500

    finally:
        conn.close()

@app.route('/received_emails')
def received_emails():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_email = session.get('email')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            e.id, e.subject, e.body, e.summary, e.sent_at, e.opened_at, 
            u.email AS sender_email
        FROM emails e
        JOIN users u ON e.sender_id = u.id
        WHERE e.recipient_email = ?
        ORDER BY e.sent_at DESC
    """, (current_email,))
    emails = cur.fetchall()
    conn.close()
    return render_template('received_emails.html', emails=emails, current_user=current_email)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
@app.route('/mark_email_read/<int:email_id>', methods=['POST'])
def mark_email_read(email_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401

    user_email = session.get('email')
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE emails
        SET opened_at = ?
        WHERE id = ? AND recipient_email = ? AND opened_at IS NULL
    """, (datetime.now(), email_id, user_email))

    conn.commit()

    # Fetch tone & spam info for modal update
    cur.execute("SELECT tone, is_spam FROM emails WHERE id = ?", (email_id,))
    row = cur.fetchone()
    conn.close()

    return jsonify({
        'status': 'success',
        'message': 'Email marked as read',
        'tone': row['tone'] if row else None,
        'is_spam': bool(row['is_spam']) if row else False
    })

if __name__ == '__main__':
    app.run(debug=True)