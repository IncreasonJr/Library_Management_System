from flask import current_app, render_template
from flask_mail import Message
from app import mail
from threading import Thread

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Error sending email async: {e}")
            print("--- EMAIL FALLBACK PRINT ---")
            print(f"To: {msg.recipients}")
            print(f"Subject: {msg.subject}")
            print(f"Body: {msg.html}")
            print("----------------------------")

def send_email(subject, recipients, template, **kwargs):
    if isinstance(recipients, str):
        recipients = [recipients]
    
    app = current_app._get_current_object()
    msg = Message(subject, recipients=recipients)
    msg.html = render_template(f"email/{template}.html", **kwargs)
    
    # In testing mode, run synchronously to enable outbox message recording
    if app.config.get("TESTING"):
        send_async_email(app, msg)
        return
        
    # If no mail username or password, print to console instead of failing
    if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
        print(f"SMTP not configured. Printing email to console:")
        print("--- EMAIL PREVIEW ---")
        print(f"To: {recipients}")
        print(f"Subject: {subject}")
        with app.app_context():
            print(f"Body:\n{msg.html}")
        print("----------------------")
        return

    
    thread = Thread(target=send_async_email, args=(app, msg))
    thread.start()

def send_welcome_email(user):
    send_email(
        subject="Welcome to Library!",
        recipients=[user.email],
        template="welcome",
        user=user
    )

def send_due_reminder(user, book, due_date):
    send_email(
        subject=f"Upcoming Due Date: {book.title}",
        recipients=[user.email],
        template="due_reminder",
        user=user,
        book=book,
        due_date=due_date
    )

def send_overdue_notice(user, book, days_overdue, fine):
    send_email(
        subject=f"Overdue Notice: {book.title}",
        recipients=[user.email],
        template="overdue_notice",
        user=user,
        book=book,
        days_overdue=days_overdue,
        fine=fine
    )

def send_return_confirmation(user, book, fine):
    send_email(
        subject=f"Book Returned: {book.title}",
        recipients=[user.email],
        template="return_confirmation",
        user=user,
        book=book,
        fine=fine
    )

def send_password_reset(user, token):
    send_email(
        subject="Reset Your Library Password",
        recipients=[user.email],
        template="password_reset",
        user=user,
        token=token
    )

def send_reservation_available_email(user, book, expiry_date):
    send_email(
        subject=f"Reserved Book Available: {book.title}",
        recipients=[user.email],
        template="reservation_available",
        user=user,
        book=book,
        expiry_date=expiry_date
    )

