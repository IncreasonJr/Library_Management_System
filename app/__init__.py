from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import get_config


from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()



login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."


def init_db(app):
	with app.app_context():
		try:
			db.create_all()
			app.logger.info("Database tables initialized successfully.")
		except Exception as e:
			app.logger.error(f"Database initialization failed (DB may be offline or unreachable): {e}")


@login_manager.user_loader
def load_user(user_id):
	from .models import User

	return User.query.get(int(user_id))


def create_app():
	app = Flask(__name__, static_folder="../static")
	app.config.from_object(get_config())

	db.init_app(app)
	bcrypt.init_app(app)
	login_manager.init_app(app)
	mail.init_app(app)
	csrf.init_app(app)


	from . import models  # noqa: F401
	from .auth import auth_bp
	from .routes import main_bp

	app.register_blueprint(auth_bp)
	app.register_blueprint(main_bp)

	@app.template_filter("timeago")
	def timeago_filter(dt):
		if not dt:
			return ""
		from datetime import datetime
		diff = datetime.utcnow() - dt
		if diff.days > 365:
			y = diff.days // 365
			return f"{y} year{'s' if y > 1 else ''} ago"
		if diff.days > 30:
			m = diff.days // 30
			return f"{m} month{'s' if m > 1 else ''} ago"
		if diff.days > 0:
			return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
		if diff.seconds > 3600:
			h = diff.seconds // 3600
			return f"{h} hour{'s' if h > 1 else ''} ago"
		if diff.seconds > 60:
			m = diff.seconds // 60
			return f"{m} minute{'s' if m > 1 else ''} ago"
		return "just now"

	init_db(app)

	return app

