import os

from dotenv import load_dotenv


load_dotenv()


class BaseConfig:
	SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
	SQLALCHEMY_TRACK_MODIFICATIONS = False
	BCRYPT_LOG_ROUNDS = 12

	# Flask-Mail configuration
	MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
	MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
	MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
	MAIL_USERNAME = os.getenv("MAIL_USERNAME")
	MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
	MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
	MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False").lower() == "true"



class DevelopmentConfig(BaseConfig):
	_db_url = os.getenv("DATABASE_URL", "sqlite:///library.db")
	if _db_url:
		_db_url = _db_url.strip()
		if _db_url.startswith("postgres://"):
			_db_url = _db_url.replace("postgres://", "postgresql://", 1)
	SQLALCHEMY_DATABASE_URI = _db_url


class ProductionConfig(BaseConfig):
	_db_url = os.getenv("POSTGRESQL_URL") or os.getenv("DATABASE_URL")
	if _db_url:
		_db_url = _db_url.strip()
		if _db_url.startswith("postgres://"):
			_db_url = _db_url.replace("postgres://", "postgresql://", 1)
	SQLALCHEMY_DATABASE_URI = _db_url or "postgresql://postgres:postgres@localhost:5432/library_db"


def get_config():
	environment = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
	if environment == "production":
		return ProductionConfig
	return DevelopmentConfig

