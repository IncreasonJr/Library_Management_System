from datetime import datetime, timedelta

from flask_login import UserMixin

from . import bcrypt, db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="member")
    active = db.Column("is_active", db.Boolean, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    email_notifications = db.Column(db.Boolean, nullable=False, default=True)
    reminder_days = db.Column(db.Integer, nullable=False, default=3)


    borrowings = db.relationship(
        "Borrowing",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reservations = db.relationship(
        "Reservation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    activities = db.relationship(
        "ActivityLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )




    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self): 
        return True

    @property
    def is_active(self):
        return self.active

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    available = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    borrowings = db.relationship(
        "Borrowing",
        back_populates="book",
        cascade="all, delete-orphan",
    )
    reservations = db.relationship(
        "Reservation",
        back_populates="book",
        cascade="all, delete-orphan",
    )



class Borrowing(db.Model):
    __tablename__ = "borrowings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    borrow_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_date = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(days=14),
    )
    return_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default="borrowed")
    fine_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    reminder_sent = db.Column(db.Boolean, nullable=False, default=False)
    overdue_notice_sent = db.Column(db.Boolean, nullable=False, default=False)


    user = db.relationship("User", back_populates="borrowings")
    book = db.relationship("Book", back_populates="borrowings")


    def is_overdue(self):
        """Check if borrowing is past due date and not returned"""
        return self.status == "borrowed" and datetime.utcnow() > self.due_date

    def calculate_fine(self):
        """Calculate fine: $0.50 per day overdue"""
        if self.return_date and self.return_date > self.due_date:
            days_overdue = (self.return_date - self.due_date).days
            return round(days_overdue * 0.50, 2)
        elif not self.return_date and datetime.utcnow() > self.due_date:
            days_overdue = (datetime.utcnow() - self.due_date).days
            return round(days_overdue * 0.50, 2)
        return 0.00


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)


class Reservation(db.Model):
    __tablename__ = "reservations"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    reservation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="waiting")  # waiting, notified, fulfilled, cancelled, expired
    notified_date = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)  # 48 hours after notification
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    user = db.relationship("User", back_populates="reservations")
    book = db.relationship("Book", back_populates="reservations")


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    user = db.relationship("User", back_populates="activities")


def log_activity(user_id, action, details=None):
    import json
    try:
        details_str = json.dumps(details) if details else None
        log = ActivityLog(user_id=user_id, action=action, details=details_str)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
        db.session.rollback()



