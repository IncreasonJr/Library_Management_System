# 📚 BookNest

> **Effortless library control.**

BookNest is a premium, modern, and mobile-responsive Library Management System built with **Flask**, **SQLite/PostgreSQL**, and styled with a beautiful **glassmorphic dark/light UI**. It simplifies catalog search, borrowing activities, reservation waitlists, and provides interactive statistics charts and automated notifications.

---

## ✨ Features

- **Cozy Glassmorphic Interface**: High-fidelity translucent cards and smooth scroll animations.
- **Unified Catalog Browser**: Live search, category filtering, and sorting parameters for books.
- **End-to-End Borrowing Flow**: Keeps track of active borrowings, renewals (extends due date by 7 days), returns, and dynamically calculates overdue fines. Enforces a **3-book limit** per member.
- **Smart Reservation Queue**: When a book's availability reaches 0, members can reserve it. When returned, the system places it on a **48-hour hold** for the first reserver and shoots them an email notification.
- **Interactive Dashboards**: Role-based views (Admin, Librarian, Member). Displays monthly borrowing trends and popular books powered by **Chart.js**.
- **Admin Management & Reports**: CSV exports for overdue books, popular lists, member activity logs, and manual waitlist control.
- **Automated CLI Reminders**: Custom commands to cycle reservations and send overdue alerts.
- **Fully Mobile Responsive**: Sidebar collapses into a hamburger overlay navigation menu on small screens.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.12, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Mail, Flask-WTF, Flask-Bcrypt
- **Frontend**: HTML5, CSS3 (Vanilla Glassmorphism), JavaScript (ES6+), Chart.js
- **Database**: SQLite (Development) / PostgreSQL (Production)

---

## 🚀 Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/IncreasonJr/Library_Management_System.git
cd Library_Management_System
```

### 2. Configure Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Variables Configuration
Create a `.env` file in the root directory:
```env
SECRET_KEY=your-secret-key-here
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=BookNest your-email@gmail.com
```

### 5. Initialize & Seed Database
```bash
python seed.py
```

### 6. Run the Application
```bash
python wsgi.py
```
Visit the application at `http://127.0.0.1:5000`.

---

## 📧 Automated Reminders & Reservation Expirations
Run the automated reminders command via cron job or scheduler:
```bash
python wsgi.py send-reminders
```
This script processes:
- Overdue notices for members.
- Expiration of unclaimed holds (holds expire after 48 hours, notifying the next user on the waitlist).

---

## 👥 Seeded Test Credentials

- **Admin Account**:
  - Email: `admin@library.com`
  - Password: `password123`
- **Member Account**:
  - Email: `member@library.com`
  - Password: `password123`

---

## 📄 License
© 2026 BookNest. All rights reserved.
