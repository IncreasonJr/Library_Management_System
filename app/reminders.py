from datetime import datetime, timedelta
from app.models import Borrowing, Reservation
from app.email import send_due_reminder, send_overdue_notice, send_reservation_available_email
from app import db

def check_reservation_expirations():
    now = datetime.utcnow()
    expired_reservations = Reservation.query.filter(
        Reservation.status == "notified",
        Reservation.expiry_date < now
    ).all()
    
    expired_count = 0
    new_notifications_count = 0
    
    for res in expired_reservations:
        res.status = "expired"
        expired_count += 1
        
        # Find next waiting reservation for this book
        next_res = Reservation.query.filter_by(
            book_id=res.book_id,
            status="waiting"
        ).order_by(Reservation.reservation_date.asc()).first()
        
        if next_res:
            next_res.status = "notified"
            next_res.notified_date = now
            next_res.expiry_date = now + timedelta(hours=48)
            new_notifications_count += 1
            
            if next_res.user.email_notifications:
                send_reservation_available_email(next_res.user, next_res.book, next_res.expiry_date)
                
    db.session.commit()
    print(f"Reservation expiry check complete. Expired {expired_count} reservations. Notified {new_notifications_count} next-in-line users.")

def send_reminders_run():
    now = datetime.utcnow()
    borrowings = Borrowing.query.filter_by(status="borrowed").all()
    
    reminders_sent_count = 0
    overdue_notices_sent_count = 0
    
    for b in borrowings:
        if not b.user or not b.book:
            continue
        if b.is_overdue():
            if not b.overdue_notice_sent:
                days_overdue = (now - b.due_date).days
                if days_overdue <= 0:
                    days_overdue = 1
                fine = b.calculate_fine()
                if b.user.email_notifications:
                    send_overdue_notice(b.user, b.book, days_overdue, fine)
                    overdue_notices_sent_count += 1
                b.overdue_notice_sent = True
        else:
            if not b.reminder_sent:
                days_until_due = (b.due_date - now).days
                if 0 <= days_until_due <= b.user.reminder_days:
                    if b.user.email_notifications:
                        send_due_reminder(b.user, b.book, b.due_date)
                        reminders_sent_count += 1
                    b.reminder_sent = True
                    
    db.session.commit()
    print(f"Reminder run complete. Sent {reminders_sent_count} reminders and {overdue_notices_sent_count} overdue notices.")
    
    # Run reservation expiry checks
    check_reservation_expirations()
