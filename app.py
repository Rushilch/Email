from flask import Flask, request, jsonify, render_template, session, url_for, redirect, flash
from flask_cors import CORS
import sqlite3
import bcrypt
import re
from datetime import datetime
from backend.llama_utils import generate_llama_response, classify_email_tone, detect_spam, summarize_email

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'
CORS(app, supports_credentials=True)

DATABASE = 'Sbox.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
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
    admin_email = "admin@Sbox.com"
    admin_pass = bcrypt.hashpw("Admin@123".encode(), bcrypt.gensalt()).decode()
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
        if session.get('is_admin'):
            return render_template('admin_dashboard.html')
        else:
            return redirect(url_for('sender_dashboard'))
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

        email = data['email']
        password = data['password']

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, password_hash, is_admin FROM users WHERE email = ?', (email,))
        row = c.fetchone()
        conn.close()

        if row and verify_password(password, row[1]):
            session['user_id'] = row[0]
            session['is_admin'] = bool(row[2])
            session['email'] = email
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
    cur.execute('SELECT is_active FROM users WHERE id = ?', (data['sender_id'],))
    user = cur.fetchone()
    if not user or not user['is_active']:
        conn.close()
        return jsonify({'status': 'error', 'message': 'User account is disabled'}), 403

    body_text = data['body']
    tone = classify_email_tone(body_text)
    is_spam = 1 if detect_spam(body_text) else 0
    summary = summarize_email(body_text)
    cur.execute("""
        INSERT INTO emails (sender_id, recipient_email, subject, body, tone, sent_at, is_spam, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['sender_id'],
        data['recipient'],
        data['subject'],
        data['body'],
        tone,
        datetime.now(),
        is_spam,
        summary
    ))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Email sent', 'is_spam': bool(is_spam)}), 200

@app.route('/sent_emails', methods=['GET'])
def get_user_sent_emails():
    sender_id = request.args.get('sender_id')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            e.id,
            e.recipient_email,
            e.subject,
            e.body,
            e.sent_at,
            e.opened_at,
            e.is_spam,
            e.tone
        FROM emails e
        WHERE e.sender_id = ?
        ORDER BY e.sent_at DESC
    """, (sender_id,))
    emails = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(emails)

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

@app.route('/mark_email_read/<int:email_id>', methods=['POST'])
def mark_email_read(email_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    current_email = session.get('email')
    current_time = datetime.now()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM emails 
        WHERE id = ? AND recipient_email = ?
    """, (email_id, current_email))
    if not cur.fetchone():
        conn.close()
        return jsonify({'status': 'error', 'message': 'Email not found or not authorized'}), 404
    cur.execute("""
        UPDATE emails SET opened_at = ?
        WHERE id = ? AND opened_at IS NULL
    """, (current_time, email_id))
    conn.commit()
    cur.execute("""
        SELECT e.opened_at, u.email AS sender_email, e.tone, e.is_spam, e.summary
        FROM emails e
        JOIN users u ON e.sender_id = u.id
        WHERE e.id = ?
    """, (email_id,))
    updated_email = dict(cur.fetchone())
    conn.close()
    # Return accurate values from database (not canned strings)
    return jsonify({
        "status": "success",
        "message": "Email marked as read",
        "opened_at": updated_email.get('opened_at'),
        "sender_email": updated_email.get('sender_email'),
        "tone": updated_email.get('tone'),
        "is_spam": bool(updated_email.get('is_spam')),
        "summary": updated_email.get('summary')
    })

@app.route('/sender_dashboard')
def sender_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    current_email = session.get('email')
    user_id = session.get('user_id')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            e.id, e.recipient_email, e.subject, e.body,
            strftime('%Y-%m-%d %H:%M', e.sent_at) as sent_at,
            CASE WHEN e.opened_at IS NULL THEN NULL ELSE strftime('%Y-%m-%d %H:%M', e.opened_at) END as opened_at,
            e.is_spam, e.tone
        FROM emails e
        WHERE e.sender_id = ?
        ORDER BY e.sent_at DESC
    """, (user_id,))
    sent_emails = cur.fetchall()
    conn.close()
    return render_template('sender_dashboard.html',
                          current_user=current_email,
                          current_id=user_id,
                          emails=sent_emails)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('You must be logged in as an admin to view this page', 'error')
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id, email, is_active, is_admin FROM users ORDER BY email')
    users = cur.fetchall()
    cur.execute('''
        SELECT e.*, u.email as sender_email 
        FROM emails e
        JOIN users u ON e.sender_id = u.id
        ORDER BY e.sent_at DESC
    ''')
    all_emails = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
    stats = {
        "active_users": cur.execute('SELECT COUNT(*) FROM users WHERE is_active = 1').fetchone()[0],
        "total_emails": cur.execute('SELECT COUNT(*) FROM emails').fetchone()[0],
        "spam_emails": cur.execute('SELECT COUNT(*) FROM emails WHERE is_spam = 1').fetchone()[0],
        "read_emails": cur.execute('SELECT COUNT(*) FROM emails WHERE opened_at IS NOT NULL').fetchone()[0]
    }
    conn.close()
    return render_template('admin_dashboard.html', users=users, stats=stats,
                          all_emails=all_emails, current_user=session.get('email'))

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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
