import os
import sys

# Set up testing config
os.environ["MAIL_SUPPRESS_SEND"] = "True"
sys.path.insert(0, "/home/caleb/Desktop/PROJECTS/LIBRARY")

from app import create_app, db, mail
from app.models import User, Book, Borrowing, Reservation, ActivityLog

def debug_reservation_flow():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["MAIL_SUPPRESS_SEND"] = True
    
    mail.init_app(app)
    client = app.test_client()
    
    with app.app_context():
        # Clean up database to a clean starting state
        db.drop_all()
        db.create_all()
        
        # Create a member and an admin
        member = User(name="Grace Thompson", email="member@library.com")
        member.set_password("password123")
        
        admin = User(name="Admin User", email="admin@library.com", role="admin")
        admin.set_password("password123")
        
        # Create a 1-copy book
        book = Book(title="1-Copy Test Book", author="Tester", isbn="9999999999", category="Fiction", quantity=1, available=1)
        
        db.session.add_all([member, admin, book])
        db.session.commit()
        
        print(f"[DEBUG] Setup: Book ID={book.id}, Available={book.available}")
        
        # 1. Member borrows the book
        client.post('/login', data={'email': 'member@library.com', 'password': 'password123'}, follow_redirects=True)
        client.post(f'/books/{book.id}/borrow', follow_redirects=True)
        
        db.session.refresh(book)
        print(f"[DEBUG] After Borrow: Available={book.available}")
        client.get('/logout', follow_redirects=True)
        
        # 2. Register test2
        test2_email = "test2@library.com"
        reg_resp = client.post('/register', data={
            'name': 'Test User Two',
            'email': test2_email,
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        
        t2_user = User.query.filter_by(email=test2_email).first()
        print(f"[DEBUG] Register Test2: User exists={t2_user is not None}, User ID={t2_user.id if t2_user else None}")
        
        # 3. Log in test2
        login_resp = client.post('/login', data={'email': test2_email, 'password': 'password123'}, follow_redirects=True)
        print(f"[DEBUG] Login Test2: 'Dashboard' in response={b'Dashboard' in login_resp.data}")
        
        # 4. Reserve book
        res_resp = client.post(f'/books/{book.id}/reserve', follow_redirects=True)
        res_record = Reservation.query.filter_by(user_id=t2_user.id, book_id=book.id).first()
        print(f"[DEBUG] Reservation: Record exists={res_record is not None}, Status={res_record.status if res_record else None}")
        
        client.get('/logout', follow_redirects=True)
        
        # 5. Member returns book
        client.post('/login', data={'email': 'member@library.com', 'password': 'password123'}, follow_redirects=True)
        
        with mail.record_messages() as outbox:
            ret_resp = client.post(f'/books/{book.id}/return', follow_redirects=True)
            print(f"[DEBUG] Return: Redirected status={ret_resp.status_code}")
            
            db.session.refresh(res_record)
            print(f"[DEBUG] After Return: Reservation status={res_record.status}")
            print(f"[DEBUG] Emails sent: {len(outbox)}")
            for msg in outbox:
                print(f"  - Subject: {msg.subject}, To: {msg.recipients}")
                
            # Print flashes or response content highlights
            print(f"[DEBUG] Flashed messages in response data:")
            # Simple check for alert classes or messages
            for line in ret_resp.data.split(b'\n'):
                if b'alert' in line or b'Reservation' in line or b'returned' in line or b'notified' in line:
                    print(f"    {line.decode('utf-8').strip()}")

if __name__ == "__main__":
    debug_reservation_flow()
