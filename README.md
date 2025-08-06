
# MailSense — Smart Email Platform with Groq & LLaMA

**MailSense** is a secure, modern email web application built with **Flask** and **SQLite**.  
It combines everyday email features with intelligent tools powered by the **Groq API** and **LLaMA 3.1** for better communication and productivity.


## Key Features

###  Core Email Features
- **Secure Login & Registration** — User accounts are protected with Bcrypt password hashing.
- **Internal & External Messaging** — Send messages to other platform users or external addresses.
- **Separate Inbox & Sent Views** — Quickly switch between received and sent emails.
- **Read Receipts** — See when your internal messages are opened.

###  Smart Tools (Powered by Groq API)
- **Tone Classification** — Detects one of 14 tones (e.g., Friendly, Urgent, Formal, Apologetic).
- **Spam Detection** — Automatically flags unwanted or suspicious messages.
- **Email Summaries** — Generates a quick summary for received messages.
- **Tone Rewriter** — Adjusts your email tone before sending (e.g., Polite, Sarcastic).

###  Dashboards & Interface
- **Admin Dashboard**
  - Overview cards for Active Users, Total Emails, Spam Count, and Read Count.
  - Charts for email trends, internal vs. external messages, and tone distribution.
  - Tools to view and manage users and messages.
- **Clean, Responsive UI** — Built with Bootstrap 5 for an intuitive user experience.

---

##  Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Rushilch/Email.git
cd Email
```

### 2. Create a Virtual Environment & Install Dependencies

```bash
python -m venv .venv
# Activate it:
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r backend/requirements.txt
```

### 3. Set Up Environment Variables

Create a file named `.env` in the project root (`Email/.env`):

```env
GROQ_API="groq_api_key"
SENDER_EMAIL="your-gmail@gmail.com"
EMAIL_PASS="your-gmail-app-password-key"
```

> **Note:** Never commit `.env` to version control.
> Get your Groq API key at: [https://groq.com/](https://groq.com/)

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

##  Project Structure

```
Email/
├── .venv                 # Virtual environment
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

##  Screenshots

* **Login Page**
  <img width="1919" height="912" alt="Login page" src="https://github.com/user-attachments/assets/f66989ea-1c87-4858-8a9a-9559f64b8558" />

* **Register Page**
  <img width="1919" height="912" alt="Registration page" src="https://github.com/user-attachments/assets/61ad56da-e4b4-4261-91de-ee289b0fdbd8" />

* **Sender Dashboard** 
  <img width="1919" height="912" alt="Compose" src="https://github.com/user-attachments/assets/4626443f-b8af-4482-875b-438c4fcda244" />

  <img width="1919" height="912" alt="Ai analysis" src="https://github.com/user-attachments/assets/07488ec6-ae70-4796-becd-56f20f1ee5f3" />

  <img width="1919" height="912" alt="Rewrite feature" src="https://github.com/user-attachments/assets/268f7211-9efd-4eb4-b77c-2b3e256dcda6" />

* **Inbox** 
  <img width="1919" height="912" alt="Inbox" src="https://github.com/user-attachments/assets/ce65fe15-cfc3-4841-b1ec-96eb7e40006a" />

  <img width="1919" height="912" alt="View mail" src="https://github.com/user-attachments/assets/21afbe3c-d1a9-4fc9-9a85-a14721ff3251" />

  <img width="1919" height="912" alt="Reply" src="https://github.com/user-attachments/assets/74da3982-1165-453c-a7d9-901923752dfa" />

* **Admin Dashboard**
  <img width="1919" height="912" alt="User statistics and source breakdown" src="https://github.com/user-attachments/assets/56fda49d-81d9-4feb-93b6-1571e7738e47" />
  
  <img width="1919" height="912" alt="Tone analysis and user management" src="https://github.com/user-attachments/assets/7bdeedd2-4dcb-48e8-9e66-fd2c4ce1a2eb" />

  <img width="1919" height="912" alt="Mail controls" src="https://github.com/user-attachments/assets/131818b2-9ccd-4010-8b1b-163d1d60b5df" />

  <img width="1919" height="912" alt="View mail" src="https://github.com/user-attachments/assets/9e21a1b9-dfad-4fb2-9d8c-69108cee2109" />



---

##  Planned Enhancements

*  File attachments
*  Dockerized deployment
*  Real‑time new message alerts

```
