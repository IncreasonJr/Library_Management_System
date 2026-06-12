from functools import wraps
from urllib.parse import urlparse, urljoin

from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from itsdangerous import URLSafeTimedSerializer

from . import db
from .forms import LoginForm, RegistrationForm, RequestResetForm, ResetPasswordForm
from .models import User, log_activity
from .email import send_welcome_email, send_password_reset

auth_bp = Blueprint("auth", __name__)


def is_safe_url(target):
	ref_url = urlparse(request.host_url)
	test_url = urlparse(urljoin(request.host_url, target))
	return test_url.scheme in {"http", "https"} and ref_url.netloc == test_url.netloc


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
	if current_user.is_authenticated:
		return redirect(url_for("main.dashboard"))

	form = LoginForm()
	next_page = request.args.get("next") or request.form.get("next")
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data.lower().strip()).first()
		if user and user.check_password(form.password.data):
			login_user(user)
			log_activity(user.id, "user_logged_in", {"email": user.email})
			flash("Logged in successfully.", "success")
			if next_page and is_safe_url(next_page):
				return redirect(next_page)
			return redirect(url_for("main.dashboard"))
		flash("Invalid email or password.", "danger")

	return render_template("login.html", form=form, next_page=next_page)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
	if current_user.is_authenticated:
		return redirect(url_for("main.dashboard"))

	form = RegistrationForm()
	if form.validate_on_submit():
		user = User(
			name=form.name.data.strip(),
			email=form.email.data.lower().strip(),
			role="member",
		)
		user.set_password(form.password.data)
		db.session.add(user)
		try:
			db.session.commit()
		except IntegrityError:
			db.session.rollback()
			flash("An account with that email already exists.", "danger")
			return render_template("register.html", form=form)
		
		# Send welcome email and flash message
		send_welcome_email(user)
		log_activity(user.id, "user_registered", {"email": user.email, "name": user.name})
		flash("Registration successful. Please log in.", "success")
		flash("Registration email sent", "info")
		return redirect(url_for("auth.login"))

	return render_template("register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
	logout_user()
	flash("You have been logged out.", "info")
	return redirect(url_for("auth.login"))


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
	if current_user.is_authenticated:
		return redirect(url_for("main.dashboard"))
	
	form = RequestResetForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data.lower().strip()).first()
		if user:
			serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
			token = serializer.dumps(user.email, salt="password-reset-salt")
			send_password_reset(user, token)
			flash("Password reset email sent", "success")
			flash("Check your email for instructions", "info")
			return redirect(url_for("auth.login"))
	
	return render_template("reset_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password_token(token):
	if current_user.is_authenticated:
		return redirect(url_for("main.dashboard"))
	
	serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
	try:
		email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
	except Exception:
		flash("The password reset link is invalid or has expired.", "danger")
		return redirect(url_for("auth.reset_password"))
	
	user = User.query.filter_by(email=email).first_or_404()
	form = ResetPasswordForm()
	if form.validate_on_submit():
		user.set_password(form.password.data)
		db.session.commit()
		flash("Your password has been reset successfully.", "success")
		return redirect(url_for("auth.login"))
	
	return render_template("reset_password_token.html", form=form)