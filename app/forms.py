from flask_wtf import FlaskForm
from wtforms import IntegerField, PasswordField, StringField, SubmitField, BooleanField
from wtforms.fields import EmailField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, ValidationError

from .models import User


class LoginForm(FlaskForm):
	email = EmailField("Email", validators=[DataRequired(), Email()])
	password = PasswordField("Password", validators=[DataRequired()])
	submit = SubmitField("Login")


class RegistrationForm(FlaskForm):
	name = StringField("Name", validators=[DataRequired(), Length(min=2, max=120)])
	email = EmailField("Email", validators=[DataRequired(), Email()])
	password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
	confirm_password = PasswordField(
		"Confirm Password",
		validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
	)
	submit = SubmitField("Register")

	def validate_email(self, email):
		if User.query.filter_by(email=email.data.lower().strip()).first():
			raise ValidationError("An account with that email already exists.")


class BookForm(FlaskForm):
	title = StringField("Title", validators=[DataRequired(), Length(min=2, max=255)])
	author = StringField("Author", validators=[DataRequired(), Length(min=2, max=255)])
	isbn = StringField("ISBN", validators=[DataRequired(), Length(min=10, max=20)])
	category = StringField("Category", validators=[DataRequired(), Length(min=2, max=100)])
	quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
	submit = SubmitField("Save Book")


class SearchForm(FlaskForm):
	search_query = StringField("Search", validators=[DataRequired(), Length(min=1, max=255)])
	submit = SubmitField("Search")


class ProfileEditForm(FlaskForm):
	name = StringField("Name", validators=[DataRequired(), Length(min=2, max=120)])
	email = EmailField("Email", validators=[DataRequired(), Email()])
	email_notifications = BooleanField("Receive Email Notifications")
	reminder_days = IntegerField("Reminder Days before Due", validators=[DataRequired(), NumberRange(min=1, max=30)])
	submit = SubmitField("Update Profile")


	def __init__(self, original_email, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.original_email = original_email

	def validate_email(self, email):
		if email.data.lower().strip() != self.original_email.lower().strip():
			user = User.query.filter_by(email=email.data.lower().strip()).first()
			if user:
				raise ValidationError("That email is already in use by another account.")


class ChangePasswordForm(FlaskForm):
	current_password = PasswordField("Current Password", validators=[DataRequired()])
	new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
	confirm_password = PasswordField(
		"Confirm New Password",
		validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")]
	)
	submit = SubmitField("Change Password")


class RequestResetForm(FlaskForm):
	email = EmailField("Email Address", validators=[DataRequired(), Email()])
	submit = SubmitField("Request Password Reset")

	def validate_email(self, email):
		user = User.query.filter_by(email=email.data.lower().strip()).first()
		if user is None:
			raise ValidationError("There is no account with that email. Please register first.")


class ResetPasswordForm(FlaskForm):
	password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
	confirm_password = PasswordField(
		"Confirm New Password",
		validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
	)
	submit = SubmitField("Reset Password")