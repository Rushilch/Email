````markdown
# 📬 MailSense — Smart Email Platform with Groq & LLaMA

**MailSense** is a secure, modern email web application built with **Flask** and **SQLite**.  
It combines everyday email features with intelligent tools powered by the **Groq API** and **LLaMA 3.1** for better communication and productivity.

---

## ✨ Key Features

### 📌 Core Email Features
- **Secure Login & Registration** — User accounts are protected with Bcrypt password hashing.
- **Internal & External Messaging** — Send messages to other platform users or external addresses.
- **Separate Inbox & Sent Views** — Quickly switch between received and sent emails.
- **Read Receipts** — See when your internal messages are opened.

### 🧠 Smart Tools (Powered by Groq API)
- **Tone Classification** — Detects one of 14 tones (e.g., Friendly, Urgent, Formal, Apologetic).
- **Spam Detection** — Automatically flags unwanted or suspicious messages.
- **Email Summaries** — Generates a quick summary for received messages.
- **Tone Rewriter** — Adjusts your email tone before sending (e.g., Polite, Sarcastic).

### 📊 Dashboards & Interface
- **Admin Dashboard**
  - Overview cards for Active Users, Total Emails, Spam Count, and Read Count.
  - Charts for email trends, internal vs. external messages, and tone distribution.
  - Tools to view and manage users and messages.
- **Clean, Responsive UI** — Built with Bootstrap 5 for an intuitive user experience.

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/MailSense.git
cd MailSense
```

### 2. Create a Virtual Environment & Install Dependencies

```bash
python -m venv .venv
# Activate it:
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a file named `.env` in the project root (`MailSense/.env`):

```env
# Groq API Key
GROQ_API="your_gsk_..._api_key"

# Optional: Email Sending via Gmail
SENDER_EMAIL="your-gmail@gmail.com"
EMAIL_PASS="your-gmail-app-password"
```

> **Note:** Never commit `.env` to version control.
> Get your Groq API key at: [https://console.groq.com/keys](https://console.groq.com/keys)

### 4. Run the Application

```bash
python app.py
```

The app will run at **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

**Default Admin Login:**
Email: `admin@sbox.com`
Password: `admin@123`

---

## 🧪 Tech Stack

| Layer        | Technologies Used                |
| ------------ | -------------------------------- |
| **Backend**  | Python, Flask, SQLite            |
| **AI/NLP**   | Groq API (LLaMA 3.1 8B)          |
| **Frontend** | HTML, CSS, Bootstrap 5, Chart.js |
| **Security** | Flask Sessions, Bcrypt           |

---

## 📂 Project Structure

```
MailSense/
├── .venv/                 # Virtual environment
├── .env                   # API keys & config
├── app.py                 # Main Flask app
├── backend/
│   ├── llama_utils.py     # Groq API integration
│   └── requirements.txt   # Dependencies
├── templates/             # HTML templates
│   ├── login.html
│   ├── register.html
│   ├── sender_dashboard.html
│   ├── received_emails.html
│   └── admin_dashboard.html
└── Sbox.db                # SQLite database
```

---

## 📸 Screenshots

* **Login Page**
* **Sender Dashboard** (Compose + AI Tools)
* **Inbox** (with summaries)
* **Admin Dashboard** (metrics & charts)

---

## 🔮 Planned Enhancements

* 📎 File attachments
* 🌍 Dockerized deployment
* 🔔 Real‑time new message alerts
* 📈 Upgrade to LLaMA 3.1 70B for richer AI capabilities

```
```
