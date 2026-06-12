from app import create_app, db
from app.models import Book, Category, User


def seed_database():
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        categories = {
            "Fiction": "Narrative works of imagination and character-driven stories.",
            "Science": "Books that explore scientific ideas, discoveries, and research.",
            "History": "Works covering events, people, and developments from the past.",
            "Technology": "Titles focused on software, engineering, and digital systems.",
        }

        for name, description in categories.items():
            existing_category = Category.query.filter_by(name=name).first()
            if not existing_category:
                db.session.add(Category(name=name, description=description))

        users = [
            {
                "name": "Amina Yusuf",
                "email": "admin@library.com",
                "role": "admin",
                "password": "password123",
            },
            {
                "name": "Daniel Mensah",
                "email": "librarian@library.com",
                "role": "librarian",
                "password": "password123",
            },
            {
                "name": "Grace Thompson",
                "email": "member@library.com",
                "role": "member",
                "password": "password123",
            },
        ]

        for user_data in users:
            existing_user = User.query.filter_by(email=user_data["email"]).first()
            if not existing_user:
                password = user_data.pop("password")
                user = User(name=user_data["name"], email=user_data["email"], role=user_data["role"])
                user.set_password(password)
                db.session.add(user)

        books = [
            {
                "title": "The Midnight Library",
                "author": "Matt Haig",
                "isbn": "9780525559474",
                "category": "Fiction",
                "quantity": 4,
                "available": True,
            },
            {
                "title": "The Book Thief",
                "author": "Markus Zusak",
                "isbn": "9780375842207",
                "category": "Fiction",
                "quantity": 3,
                "available": True,
            },
            {
                "title": "Where the Crawdads Sing",
                "author": "Delia Owens",
                "isbn": "9780735219090",
                "category": "Fiction",
                "quantity": 5,
                "available": True,
            },
            {
                "title": "A Brief History of Time",
                "author": "Stephen Hawking",
                "isbn": "9780553380163",
                "category": "Science",
                "quantity": 2,
                "available": True,
            },
            {
                "title": "The Selfish Gene",
                "author": "Richard Dawkins",
                "isbn": "9780198788607",
                "category": "Science",
                "quantity": 2,
                "available": True,
            },
            {
                "title": "Guns, Germs, and Steel",
                "author": "Jared Diamond",
                "isbn": "9780393354324",
                "category": "History",
                "quantity": 3,
                "available": True,
            },
            {
                "title": "The Silk Roads",
                "author": "Peter Frankopan",
                "isbn": "9781101912379",
                "category": "History",
                "quantity": 2,
                "available": True,
            },
            {
                "title": "Clean Code",
                "author": "Robert C. Martin",
                "isbn": "9780132350884",
                "category": "Technology",
                "quantity": 4,
                "available": True,
            },
            {
                "title": "The Pragmatic Programmer",
                "author": "Andrew Hunt and David Thomas",
                "isbn": "9780201616224",
                "category": "Technology",
                "quantity": 3,
                "available": True,
            },
            {
                "title": "Designing Data-Intensive Applications",
                "author": "Martin Kleppmann",
                "isbn": "9781449373320",
                "category": "Technology",
                "quantity": 2,
                "available": True,
            },
        ]

        for book_data in books:
            existing_book = Book.query.filter_by(isbn=book_data["isbn"]).first()
            if not existing_book:
                if "available" in book_data and book_data["available"] is True:
                    book_data["available"] = book_data["quantity"]
                db.session.add(Book(**book_data))

        db.session.commit()


if __name__ == "__main__":
    seed_database()