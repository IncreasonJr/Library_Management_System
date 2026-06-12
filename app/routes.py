from datetime import datetime, timedelta
from functools import wraps
import csv
import io
import json

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort, make_response, jsonify
from flask_login import current_user, login_required

from . import db
from .forms import BookForm, SearchForm, ProfileEditForm, ChangePasswordForm
from .models import Book, Borrowing, User, Category, Reservation, ActivityLog, log_activity


main_bp = Blueprint("main", __name__)


def admin_required(view):
	@wraps(view)
	@login_required
	def wrapped_view(*args, **kwargs):
		if current_user.role != "admin":
			abort(403)
		return view(*args, **kwargs)

	return wrapped_view



@main_bp.route("/")
def index():
	return render_template("index.html")


def get_date_range_bounds(range_type, custom_start=None, custom_end=None):
	now = datetime.utcnow()
	start_date = None
	end_date = now

	if range_type == "this_month":
		start_date = datetime(now.year, now.month, 1)
	elif range_type == "last_month":
		if now.month == 1:
			start_date = datetime(now.year - 1, 12, 1)
		else:
			start_date = datetime(now.year, now.month - 1, 1)
		# End of last month is right before start of this month
		start_of_this_month = datetime(now.year, now.month, 1)
		end_date = start_of_this_month - timedelta(seconds=1)
	elif range_type == "last_3_months":
		m = now.month - 3
		y = now.year
		if m <= 0:
			m += 12
			y -= 1
		start_date = datetime(y, m, 1)
	elif range_type == "this_year":
		start_date = datetime(now.year, 1, 1)
	elif range_type == "custom" and custom_start and custom_end:
		try:
			start_date = datetime.strptime(custom_start, "%Y-%m-%d")
			end_date = datetime.strptime(custom_end, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
		except ValueError:
			pass

	if not start_date:
		start_date = datetime(2000, 1, 1)

	return start_date, end_date


@main_bp.route("/dashboard")
@login_required
def dashboard():
	now = datetime.utcnow()
	this_month_start = datetime(now.year, now.month, 1)

	books_total = Book.query.count()
	available_total = db.session.query(db.func.sum(Book.available)).scalar() or 0
	borrowed_total = Borrowing.query.filter_by(status="borrowed").count()
	members_total = User.query.filter_by(role="member").count()
	recent_transactions = Borrowing.query.order_by(Borrowing.borrow_date.desc()).limit(6).all()

	# Reservation statistics
	active_reservations_total = Reservation.query.filter(
		Reservation.status.in_(["waiting", "notified"])
	).count()

	reservations_fulfilled_this_month = Reservation.query.filter(
		Reservation.status == "fulfilled",
		Reservation.created_at >= this_month_start
	).count()

	# 7-day borrowing data
	borrowed_per_day = []
	labels_days = []
	for i in range(6, -1, -1):
		day = now.date() - timedelta(days=i)
		day_start = datetime(day.year, day.month, day.day)
		day_end = day_start + timedelta(days=1) - timedelta(seconds=1)
		count = Borrowing.query.filter(Borrowing.borrow_date >= day_start, Borrowing.borrow_date <= day_end).count()
		borrowed_per_day.append(count)
		labels_days.append(day.strftime("%b %d"))

	# Top 5 books
	top_books = db.session.query(
		Book.title,
		db.func.count(Borrowing.id).label("count")
	).join(Borrowing).group_by(Book.id).order_by(db.desc("count")).limit(5).all()
	top_books_titles = [b[0] for b in top_books]
	top_books_counts = [b[1] for b in top_books]

	# Category distribution
	categories_data = db.session.query(
		Book.category,
		db.func.sum(Book.quantity).label("total")
	).group_by(Book.category).all()
	categories_labels = [c[0] for c in categories_data]
	categories_counts = [c[1] or 0 for c in categories_data]

	# Borrowing status breakdown
	active_count = Borrowing.query.filter(Borrowing.status == "borrowed", Borrowing.due_date >= now).count()
	returned_count = Borrowing.query.filter(Borrowing.status == "returned").count()
	overdue_count_borrowed = Borrowing.query.filter(Borrowing.status == "borrowed", Borrowing.due_date < now).count()
	status_labels = ["Active", "Returned", "Overdue"]
	status_counts = [active_count, returned_count, overdue_count_borrowed]

	# Admin specific stats
	admin_stats = {}
	if current_user.role == "admin":
		if now.month == 1:
			last_month_start = datetime(now.year - 1, 12, 1)
			last_month_end = datetime(now.year - 1, 12, 31, 23, 59, 59)
		else:
			last_month_start = datetime(now.year, now.month - 1, 1)
			last_month_end = this_month_start - timedelta(seconds=1)

		# 1. Books borrowed this month & last month
		borrowed_this = Borrowing.query.filter(Borrowing.borrow_date >= this_month_start).count()
		borrowed_last = Borrowing.query.filter(Borrowing.borrow_date >= last_month_start, Borrowing.borrow_date <= last_month_end).count()

		# 2. Overdue books count
		overdue_books_total = Borrowing.query.filter(Borrowing.status == "borrowed", Borrowing.due_date < now).count()

		# 3. Most popular book this month
		pop_book = db.session.query(Book.title, db.func.count(Borrowing.id).label("count")).join(Borrowing).filter(
			Borrowing.borrow_date >= this_month_start
		).group_by(Book.id).order_by(db.desc("count")).first()
		most_popular = f"{pop_book[0]} ({pop_book[1]} borrows)" if pop_book else "N/A"

		# 4. Most active member this month
		act_mem = db.session.query(User.name, db.func.count(Borrowing.id).label("count")).join(Borrowing).filter(
			Borrowing.borrow_date >= this_month_start,
			User.role == "member"
		).group_by(User.id).order_by(db.desc("count")).first()
		most_active = f"{act_mem[0]} ({act_mem[1]} borrows)" if act_mem else "N/A"

		# 5. Fine revenue collected this month & last month
		revenue_this = db.session.query(db.func.sum(Borrowing.fine_amount)).filter(
			Borrowing.return_date >= this_month_start,
			Borrowing.status == "returned"
		).scalar() or 0
		revenue_last = db.session.query(db.func.sum(Borrowing.fine_amount)).filter(
			Borrowing.return_date >= last_month_start,
			Borrowing.return_date <= last_month_end,
			Borrowing.status == "returned"
		).scalar() or 0

		# 6. Books added this month & last month
		books_added_this = Book.query.filter(Book.created_at >= this_month_start).count()
		books_added_last = Book.query.filter(Book.created_at >= last_month_start, Book.created_at <= last_month_end).count()

		# 7. New members this month & last month
		members_added_this = User.query.filter(User.created_at >= this_month_start, User.role == "member").count()
		members_added_last = User.query.filter(User.created_at >= last_month_start, User.created_at <= last_month_end, User.role == "member").count()

		def get_trend(current, previous):
			if previous == 0:
				return "↑" if current > 0 else ""
			if current > previous:
				return "↑"
			elif current < previous:
				return "↓"
			return ""

		admin_stats = {
			"borrowed_this": borrowed_this,
			"borrowed_trend": get_trend(borrowed_this, borrowed_last),
			"overdue_count": overdue_books_total,
			"most_popular": most_popular,
			"most_active": most_active,
			"revenue_this": float(revenue_this),
			"revenue_trend": get_trend(revenue_this, revenue_last),
			"books_added_this": books_added_this,
			"books_added_trend": get_trend(books_added_this, books_added_last),
			"members_added_this": members_added_this,
			"members_added_trend": get_trend(members_added_this, members_added_last)
		}

	return render_template(
		"dashboard.html",
		books_total=books_total,
		available_total=available_total,
		borrowed_total=borrowed_total,
		members_total=members_total,
		recent_transactions=recent_transactions,
		active_reservations_total=active_reservations_total,
		reservations_fulfilled_this_month=reservations_fulfilled_this_month,
		borrowed_per_day=borrowed_per_day,
		labels_days=labels_days,
		top_books_titles=top_books_titles,
		top_books_counts=top_books_counts,
		categories_labels=categories_labels,
		categories_counts=categories_counts,
		status_labels=status_labels,
		status_counts=status_counts,
		admin_stats=admin_stats
	)




@main_bp.route("/books", methods=["GET"])
@login_required
def books():
	q = request.args.get("q", "").strip()
	category = request.args.get("category", "").strip()
	availability = request.args.get("availability", "").strip()
	sort = request.args.get("sort", "title_asc").strip()
	page = request.args.get("page", 1, type=int)

	query = Book.query

	if q:
		search_term = f"%{q}%"
		query = query.filter(
			(Book.title.ilike(search_term))
			| (Book.author.ilike(search_term))
			| (Book.isbn.ilike(search_term))
		)

	if category:
		query = query.filter(Book.category == category)

	if availability == "available":
		query = query.filter(Book.available > 0)

	if sort == "title_asc":
		query = query.order_by(Book.title.asc())
	elif sort == "title_desc":
		query = query.order_by(Book.title.desc())
	elif sort == "newest":
		query = query.order_by(Book.created_at.desc())
	elif sort == "oldest":
		query = query.order_by(Book.created_at.asc())

	pagination = query.paginate(page=page, per_page=10, error_out=False)
	books = pagination.items

	categories = Category.query.order_by(Category.name.asc()).all()

	return render_template(
		"books.html",
		books=books,
		pagination=pagination,
		categories=categories,
		current_category=category,
		current_availability=availability,
		current_sort=sort,
		search_value=q,
	)


@main_bp.route("/members")
@login_required
def members():
	members = User.query.order_by(User.name.asc()).all()
	return render_template("members.html", members=members)


@main_bp.route("/transactions", methods=["GET"])
@login_required
def transactions():
	status = request.args.get("status", "").strip()
	date_from = request.args.get("date_from", "").strip()
	date_to = request.args.get("date_to", "").strip()
	q = request.args.get("q", "").strip()
	sort = request.args.get("sort", "date_desc").strip()
	page = request.args.get("page", 1, type=int)

	query = Borrowing.query

	if q:
		search_term = f"%{q}%"
		query = query.join(User).join(Book).filter(
			(User.name.ilike(search_term)) | (Book.title.ilike(search_term))
		)

	if status == "borrowed":
		query = query.filter(Borrowing.status == "borrowed")
	elif status == "returned":
		query = query.filter(Borrowing.status == "returned")
	elif status == "overdue":
		query = query.filter(Borrowing.status == "borrowed", Borrowing.due_date < datetime.utcnow())

	if date_from:
		try:
			from_date = datetime.strptime(date_from, "%Y-%m-%d")
			query = query.filter(Borrowing.borrow_date >= from_date)
		except ValueError:
			pass
	if date_to:
		try:
			to_date = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
			query = query.filter(Borrowing.borrow_date < to_date)
		except ValueError:
			pass

	if sort == "date_asc":
		query = query.order_by(Borrowing.borrow_date.asc())
	else:
		query = query.order_by(Borrowing.borrow_date.desc())

	pagination = query.paginate(page=page, per_page=10, error_out=False)
	transactions = pagination.items

	return render_template(
		"transactions.html",
		transactions=transactions,
		pagination=pagination,
		current_status=status,
		date_from=date_from,
		date_to=date_to,
		search_value=q,
		current_sort=sort,
		now=datetime.utcnow(),
	)


@main_bp.route("/books/add", methods=["GET", "POST"])
@admin_required
def add_book():
	form = BookForm()
	if form.validate_on_submit():
		book = Book(
			title=form.title.data.strip(),
			author=form.author.data.strip(),
			isbn=form.isbn.data.strip(),
			category=form.category.data.strip(),
			quantity=form.quantity.data,
			available=form.quantity.data,
		)
		db.session.add(book)
		db.session.commit()
		log_activity(current_user.id, "added_book", {"book_id": book.id, "title": book.title, "isbn": book.isbn})
		flash("Book added successfully.", "success")
		return redirect(url_for("main.dashboard"))
	return render_template("book_form.html", form=form, title="Add Book")


@main_bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_book(book_id):
	book = Book.query.get_or_404(book_id)
	form = BookForm(obj=book)
	if form.validate_on_submit():
		book.title = form.title.data.strip()
		book.author = form.author.data.strip()
		book.isbn = form.isbn.data.strip()
		book.category = form.category.data.strip()
		qty_diff = form.quantity.data - book.quantity
		book.quantity = form.quantity.data
		book.available = max(0, book.available + qty_diff)
		db.session.commit()
		log_activity(current_user.id, "edited_book", {"book_id": book.id, "title": book.title, "isbn": book.isbn})
		flash("Book updated successfully.", "success")
		return redirect(url_for("main.dashboard"))
	return render_template("book_form.html", form=form, title="Edit Book")


@main_bp.route("/books/<int:book_id>/delete", methods=["POST"])
@admin_required
def delete_book(book_id):
	book = Book.query.get_or_404(book_id)
	db.session.delete(book)
	db.session.commit()
	log_activity(current_user.id, "deleted_book", {"book_id": book.id, "title": book.title, "isbn": book.isbn})
	flash("Book deleted successfully.", "success")
	return redirect(url_for("main.dashboard"))


@main_bp.route("/books/<int:book_id>/borrow", methods=["POST"])
@login_required
def borrow_book(book_id):
	book = Book.query.get_or_404(book_id)

	# Check if user has a notified reservation
	notified_res = Reservation.query.filter_by(
		user_id=current_user.id,
		book_id=book.id,
		status="notified"
	).first()

	if not notified_res:
		# If user does not have a hold, they must respect truly available copies (available - notified count)
		notified_count = Reservation.query.filter_by(book_id=book.id, status="notified").count()
		truly_available = book.available - notified_count
		if truly_available <= 0:
			flash("This book is currently reserved on hold for another member.", "danger")
			return redirect(url_for("main.books"))

	existing_borrowing = Borrowing.query.filter_by(
		user_id=current_user.id,
		book_id=book.id,
		status="borrowed"
	).first()
	if existing_borrowing:
		flash("You have already borrowed this book.", "danger")
		return redirect(url_for("main.books"))

	active_borrowings_count = Borrowing.query.filter_by(
		user_id=current_user.id,
		status="borrowed"
	).count()
	if active_borrowings_count >= 3:
		flash("You cannot borrow more than 3 books at a time.", "danger")
		return redirect(url_for("main.books"))

	overdue_books = [b for b in Borrowing.query.filter_by(user_id=current_user.id, status="borrowed").all() if b.is_overdue()]
	if overdue_books:
		flash("You cannot borrow new books while you have overdue books.", "danger")
		return redirect(url_for("main.books"))

	borrow_date = datetime.utcnow()
	due_date = borrow_date + timedelta(days=14)
	borrowing = Borrowing(
		user_id=current_user.id,
		book_id=book.id,
		borrow_date=borrow_date,
		due_date=due_date,
		status="borrowed"
	)
	book.available -= 1

	if notified_res:
		notified_res.status = "fulfilled"

	db.session.add(borrowing)
	db.session.commit()
	log_activity(current_user.id, "borrowed_book", {"book_id": book.id, "title": book.title, "borrower": current_user.name})

	due_date_str = due_date.strftime("%B %d, %Y")
	flash(f"Book borrowed successfully! It is due on {due_date_str}.", "success")
	return redirect(url_for("main.books"))



@main_bp.route("/books/<int:book_id>/return", methods=["POST"])
@login_required
def return_book(book_id):
	borrowing = Borrowing.query.filter_by(
		user_id=current_user.id,
		book_id=book_id,
		status="borrowed"
	).first_or_404()

	borrowing.return_date = datetime.utcnow()
	borrowing.status = "returned"
	fine = borrowing.calculate_fine()
	borrowing.fine_amount = fine

	book = Book.query.get(book_id)
	notified_user_name = None
	if book:
		book.available += 1

		# Check if any waiting reservations for this book
		waiting_res_list = Reservation.query.filter_by(
			book_id=book.id,
			status="waiting"
		).order_by(Reservation.reservation_date.asc()).all()

		for res in waiting_res_list:
			if res.user:
				res.status = "notified"
				res.notified_date = datetime.utcnow()
				res.expiry_date = datetime.utcnow() + timedelta(hours=48)
				notified_user_name = res.user.name

				# Send email notification
				if res.user.email_notifications:
					from .email import send_reservation_available_email
					send_reservation_available_email(res.user, book, res.expiry_date)
				break
			else:
				res.status = "cancelled"

		db.session.commit()
	log_activity(current_user.id, "returned_book", {"book_id": book.id, "title": book.title, "borrower": current_user.name, "fine_amount": float(fine)})

	if current_user.email_notifications:
		from .email import send_return_confirmation
		send_return_confirmation(current_user, book, fine)

	if fine > 0:
		flash(f"Book returned successfully. An overdue fine of ${fine:.2f} has been charged.", "warning")
	else:
		flash("Book returned successfully.", "success")

	if notified_user_name:
		flash(f"Reservation notified: {notified_user_name} has been notified and given 48 hours to claim the book.", "info")

	return redirect(url_for("main.transactions"))




@main_bp.route("/books/<int:book_id>/renew", methods=["POST"])
@login_required
def renew_book(book_id):
	borrowing = Borrowing.query.filter_by(
		user_id=current_user.id,
		book_id=book_id,
		status="borrowed"
	).first_or_404()

	if borrowing.is_overdue():
		flash("Overdue books cannot be renewed. Please return it.", "danger")
		return redirect(url_for("main.my_books"))

	max_due_date = borrowing.borrow_date + timedelta(days=28)
	if borrowing.due_date + timedelta(days=7) > max_due_date:
		flash("Maximum renewal limit reached (max 2 renewals).", "danger")
		return redirect(url_for("main.my_books"))

	borrowing.due_date += timedelta(days=7)
	db.session.commit()

	new_due_str = borrowing.due_date.strftime("%B %d, %Y")
	flash(f"Book renewed successfully! New due date is {new_due_str}.", "success")
	return redirect(url_for("main.my_books"))


@main_bp.route("/my-books")
@login_required
def my_books():
	active_borrowings = Borrowing.query.filter_by(
		user_id=current_user.id,
		status="borrowed"
	).order_by(Borrowing.due_date.asc()).all()

	borrowing_history = Borrowing.query.filter_by(
		user_id=current_user.id,
		status="returned"
	).order_by(Borrowing.return_date.desc()).all()

	return render_template(
		"my_books.html",
		active_borrowings=active_borrowings,
		borrowing_history=borrowing_history,
		now=datetime.utcnow(),
		timedelta=timedelta
	)


@main_bp.route("/books/<int:book_id>")
@login_required
def book_detail(book_id):
	book = Book.query.get_or_404(book_id)
	user_active_borrowing = Borrowing.query.filter_by(
		user_id=current_user.id,
		book_id=book.id,
		status="borrowed"
	).first()
	borrowing_history = Borrowing.query.filter_by(book_id=book.id).order_by(Borrowing.borrow_date.desc()).all()

	return render_template(
		"book_detail.html",
		book=book,
		user_active_borrowing=user_active_borrowing,
		borrowing_history=borrowing_history,
		now=datetime.utcnow()
	)


@main_bp.route("/profile", methods=["GET"])
@login_required
def profile():
	total_borrowed = Borrowing.query.filter_by(user_id=current_user.id).count()
	currently_borrowed = Borrowing.query.filter_by(user_id=current_user.id, status="borrowed").count()
	overdue_count = len([
		b for b in Borrowing.query.filter_by(user_id=current_user.id, status="borrowed").all()
		if b.is_overdue()
	])
	password_form = ChangePasswordForm()
	return render_template(
		"profile.html",
		user=current_user,
		total_borrowed=total_borrowed,
		currently_borrowed=currently_borrowed,
		overdue_count=overdue_count,
		password_form=password_form
	)


@main_bp.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
	form = ChangePasswordForm()
	if form.validate_on_submit():
		if current_user.check_password(form.current_password.data):
			current_user.set_password(form.new_password.data)
			db.session.commit()
			log_activity(current_user.id, "password_changed", {"email": current_user.email})
			flash("Password changed successfully.", "success")
			return redirect(url_for("main.profile"))
		else:
			flash("Incorrect current password.", "danger")
	else:
		for field, errors in form.errors.items():
			for error in errors:
				flash(f"{form[field].label.text}: {error}", "danger")
	return redirect(url_for("main.profile"))


@main_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
	form = ProfileEditForm(original_email=current_user.email, obj=current_user)
	if form.validate_on_submit():
		current_user.name = form.name.data.strip()
		current_user.email = form.email.data.lower().strip()
		current_user.email_notifications = form.email_notifications.data
		current_user.reminder_days = form.reminder_days.data
		db.session.commit()
		log_activity(current_user.id, "profile_updated", {"name": current_user.name, "email": current_user.email})
		flash("Profile updated successfully.", "success")
		return redirect(url_for("main.profile"))
	return render_template("profile_edit.html", form=form)


# ─── Reservations Endpoints ────────────────────────────────────────

@main_bp.route("/books/<int:book_id>/reserve", methods=["POST"])
@login_required
def reserve_book(book_id):
	book = Book.query.get_or_404(book_id)

	# Book must have available = 0
	if book.available > 0:
		flash("You can only reserve books that are currently checked out.", "danger")
		return redirect(url_for("main.book_detail", book_id=book.id))

	# User cannot already have this book borrowed
	already_borrowed = Borrowing.query.filter_by(
		user_id=current_user.id,
		book_id=book.id,
		status="borrowed"
	).first()
	if already_borrowed:
		flash("You cannot reserve a book you currently have borrowed.", "danger")
		return redirect(url_for("main.book_detail", book_id=book.id))

	# User cannot already have an active reservation for this book
	already_reserved = Reservation.query.filter(
		Reservation.user_id == current_user.id,
		Reservation.book_id == book.id,
		Reservation.status.in_(["waiting", "notified"])
	).first()
	if already_reserved:
		flash("You already have an active reservation for this book.", "danger")
		return redirect(url_for("main.book_detail", book_id=book.id))

	# Max 3 active reservations per user
	active_res_count = Reservation.query.filter(
		Reservation.user_id == current_user.id,
		Reservation.status.in_(["waiting", "notified"])
	).count()
	if active_res_count >= 3:
		flash("You cannot have more than 3 active reservations at a time.", "danger")
		return redirect(url_for("main.book_detail", book_id=book.id))

	# Create reservation
	reservation = Reservation(
		user_id=current_user.id,
		book_id=book.id,
		status="waiting"
	)
	db.session.add(reservation)
	db.session.commit()

	flash("Book reserved! You'll be notified when available.", "success")
	return redirect(url_for("main.book_detail", book_id=book.id))


@main_bp.route("/reservations/<int:reservation_id>/cancel", methods=["POST"])
@login_required
def cancel_reservation(reservation_id):
	reservation = Reservation.query.get_or_404(reservation_id)

	# Only reservation owner can cancel
	if reservation.user_id != current_user.id:
		flash("You do not have permission to cancel this reservation.", "danger")
		return redirect(url_for("main.my_reservations"))

	if reservation.status not in ["waiting", "notified"]:
		flash("This reservation cannot be cancelled in its current state.", "danger")
		return redirect(url_for("main.my_reservations"))

	was_notified = (reservation.status == "notified")
	reservation.status = "cancelled"
	
	if was_notified:
		# Notify next person in queue
		next_res = Reservation.query.filter_by(
			book_id=reservation.book_id,
			status="waiting"
		).order_by(Reservation.reservation_date.asc()).first()
		if next_res:
			next_res.status = "notified"
			next_res.notified_date = datetime.utcnow()
			next_res.expiry_date = datetime.utcnow() + timedelta(hours=48)
			
			if next_res.user.email_notifications:
				from .email import send_reservation_available_email
				send_reservation_available_email(next_res.user, next_res.book, next_res.expiry_date)
				
	db.session.commit()
	flash("Reservation cancelled.", "success")
	return redirect(url_for("main.my_reservations"))


@main_bp.route("/my-reservations", methods=["GET"])
@login_required
def my_reservations():
	active_reservations = Reservation.query.filter(
		Reservation.user_id == current_user.id,
		Reservation.status.in_(["waiting", "notified"])
	).order_by(Reservation.reservation_date.desc()).all()

	reservation_history = Reservation.query.filter(
		Reservation.user_id == current_user.id,
		Reservation.status.notin_(["waiting", "notified"])
	).order_by(Reservation.created_at.desc()).all()

	return render_template(
		"my_reservations.html",
		active_reservations=active_reservations,
		reservation_history=reservation_history,
		now=datetime.utcnow()
	)


@main_bp.route("/admin/reservations", methods=["GET"])
@admin_required
def admin_reservations():
	status = request.args.get("status", "all")
	query = Reservation.query
	
	# Compute counts for active filters
	waiting_count = Reservation.query.filter_by(status="waiting").count()
	notified_count = Reservation.query.filter_by(status="notified").count()
	fulfilled_count = Reservation.query.filter_by(status="fulfilled").count()
	all_count = Reservation.query.count()
	
	if status != "all":
		query = query.filter_by(status=status)
	
	reservations = query.order_by(Reservation.reservation_date.desc()).all()
	return render_template(
		"admin/reservations.html",
		reservations=reservations,
		current_status=status,
		now=datetime.utcnow(),
		waiting_count=waiting_count,
		notified_count=notified_count,
		fulfilled_count=fulfilled_count,
		all_count=all_count
	)


@main_bp.route("/admin/reservations/<int:reservation_id>/cancel", methods=["POST"])
@admin_required
def admin_cancel_reservation(reservation_id):
	reservation = Reservation.query.get_or_404(reservation_id)
	if reservation.status not in ["waiting", "notified"]:
		flash("This reservation cannot be cancelled.", "danger")
		return redirect(url_for("main.admin_reservations"))

	was_notified = (reservation.status == "notified")
	reservation.status = "cancelled"
	
	if was_notified:
		# Notify next person in queue
		next_res = Reservation.query.filter_by(
			book_id=reservation.book_id,
			status="waiting"
		).order_by(Reservation.reservation_date.asc()).first()
		if next_res:
			next_res.status = "notified"
			next_res.notified_date = datetime.utcnow()
			next_res.expiry_date = datetime.utcnow() + timedelta(hours=48)
			
			if next_res.user.email_notifications:
				from .email import send_reservation_available_email
				send_reservation_available_email(next_res.user, next_res.book, next_res.expiry_date)

	db.session.commit()
	flash("Reservation cancelled by Admin.", "success")
	return redirect(url_for("main.admin_reservations"))


@main_bp.route("/admin/reservations/<int:reservation_id>/expire", methods=["POST"])
@admin_required
def admin_expire_reservation(reservation_id):
	reservation = Reservation.query.get_or_404(reservation_id)
	if reservation.status != "notified":
		flash("Only notified reservations can be expired manually.", "danger")
		return redirect(url_for("main.admin_reservations"))

	reservation.status = "expired"
	
	# Notify next person in queue
	next_res = Reservation.query.filter_by(
		book_id=reservation.book_id,
		status="waiting"
	).order_by(Reservation.reservation_date.asc()).first()
	if next_res:
		next_res.status = "notified"
		next_res.notified_date = datetime.utcnow()
		next_res.expiry_date = datetime.utcnow() + timedelta(hours=48)
		
		if next_res.user.email_notifications:
			from .email import send_reservation_available_email
			send_reservation_available_email(next_res.user, next_res.book, next_res.expiry_date)

	db.session.commit()
	flash("Reservation expired manually.", "success")
	return redirect(url_for("main.admin_reservations"))


# ─── Admin Reports & Activity Log & Exports ───────────────────────────

@main_bp.route("/admin/reports")
@admin_required
def admin_reports():
	now = datetime.utcnow()
	date_range = request.args.get("date_range", "this_month")
	custom_start = request.args.get("start_date", "")
	custom_end = request.args.get("end_date", "")

	start_date, end_date = get_date_range_bounds(date_range, custom_start, custom_end)

	# 1. Overdue Books Report
	overdue_books = Borrowing.query.filter(
		Borrowing.status == "borrowed",
		Borrowing.due_date < now
	).all()

	# 2. Popular Books Report
	popular_books = db.session.query(
		Book,
		db.func.count(Borrowing.id).label("borrow_count")
	).join(Borrowing).filter(
		Borrowing.borrow_date >= start_date,
		Borrowing.borrow_date <= end_date
	).group_by(Book.id).order_by(db.desc("borrow_count")).limit(10).all()

	# 3. Member Activity Report
	member_activity = db.session.query(
		User,
		db.func.count(Borrowing.id).label("borrow_count")
	).join(Borrowing).filter(
		Borrowing.borrow_date >= start_date,
		Borrowing.borrow_date <= end_date,
		User.role == "member"
	).group_by(User.id).order_by(db.desc("borrow_count")).all()

	# 4. Revenue Report
	if "postgresql" in db.engine.url.drivername:
		month_expr = db.func.to_char(Borrowing.return_date, "YYYY-MM")
	else:
		month_expr = db.func.strftime("%Y-%m", Borrowing.return_date)

	revenue_data = db.session.query(
		month_expr.label("month"),
		db.func.sum(Borrowing.fine_amount).label("total_revenue")
	).filter(
		Borrowing.return_date >= start_date,
		Borrowing.return_date <= end_date,
		Borrowing.fine_amount > 0
	).group_by("month").order_by("month").all()

	return render_template(
		"admin/reports.html",
		overdue_books=overdue_books,
		popular_books=popular_books,
		member_activity=member_activity,
		revenue_data=revenue_data,
		date_range=date_range,
		start_date=custom_start,
		end_date=custom_end,
		now=now
	)


def generate_csv_response(filename, headers, rows):
	si = io.StringIO()
	cw = csv.writer(si)
	cw.writerow(headers)
	cw.writerows(rows)
	response = make_response(si.getvalue())
	response.headers["Content-Disposition"] = f"attachment; filename={filename}"
	response.headers["Content-Type"] = "text/csv"
	return response


@main_bp.route("/admin/export/books/csv")
@admin_required
def export_books_csv():
	books = Book.query.all()
	headers = ['Book ID', 'Title', 'Author', 'ISBN', 'Category', 'Total Quantity', 'Available Copies', 'Created At']
	rows = [[b.id, b.title, b.author, b.isbn, b.category, b.quantity, b.available, b.created_at.strftime("%Y-%m-%d %H:%M:%S")] for b in books]
	filename = f"books_export_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
	return generate_csv_response(filename, headers, rows)


@main_bp.route("/admin/export/transactions/csv")
@admin_required
def export_transactions_csv():
	date_range = request.args.get("date_range", "all")
	custom_start = request.args.get("start_date")
	custom_end = request.args.get("end_date")
	start, end = get_date_range_bounds(date_range, custom_start, custom_end)

	borrowings = Borrowing.query.filter(Borrowing.borrow_date >= start, Borrowing.borrow_date <= end).all()

	headers = ['Transaction ID', 'Member Name', 'Member Email', 'Book Title', 'ISBN', 'Borrow Date', 'Due Date', 'Return Date', 'Status', 'Fine Charged']
	rows = [[
		b.id,
		b.user.name,
		b.user.email,
		b.book.title,
		b.book.isbn,
		b.borrow_date.strftime("%Y-%m-%d %H:%M:%S"),
		b.due_date.strftime("%Y-%m-%d %H:%M:%S"),
		b.return_date.strftime("%Y-%m-%d %H:%M:%S") if b.return_date else 'N/A',
		b.status,
		f"${b.fine_amount:.2f}"
	] for b in borrowings]
	filename = f"transactions_export_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
	return generate_csv_response(filename, headers, rows)


@main_bp.route("/admin/export/members/csv")
@admin_required
def export_members_csv():
	members = User.query.filter_by(role="member").all()
	headers = ['Member ID', 'Name', 'Email', 'Role', 'Status', 'Joined Date', 'Active Borrowings']
	rows = []
	for m in members:
		active_borrows = Borrowing.query.filter_by(user_id=m.id, status="borrowed").count()
		rows.append([
			m.id,
			m.name,
			m.email,
			m.role,
			'Active' if m.active else 'Inactive',
			m.created_at.strftime("%Y-%m-%d %H:%M:%S"),
			active_borrows
		])
	filename = f"members_export_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
	return generate_csv_response(filename, headers, rows)


@main_bp.route("/admin/export/overdue/csv")
@main_bp.route("/admin/reports/export-overdue")
@admin_required
def export_overdue_csv():
	overdue_borrows = Borrowing.query.filter(Borrowing.status == "borrowed", Borrowing.due_date < datetime.utcnow()).all()
	headers = ['Member Name', 'Member Email', 'Book Title', 'ISBN', 'Borrow Date', 'Due Date', 'Days Overdue', 'Estimated Fine']
	rows = []
	for ob in overdue_borrows:
		days_overdue = (datetime.utcnow() - ob.due_date).days
		est_fine = ob.calculate_fine()
		rows.append([
			ob.user.name,
			ob.user.email,
			ob.book.title,
			ob.book.isbn,
			ob.borrow_date.strftime("%Y-%m-%d %H:%M:%S"),
			ob.due_date.strftime("%Y-%m-%d %H:%M:%S"),
			days_overdue,
			f"${est_fine:.2f}"
		])
	filename = f"overdue_export_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
	return generate_csv_response(filename, headers, rows)


@main_bp.route("/admin/activity")
@admin_required
def admin_activity():
	action_type = request.args.get("action_type", "").strip()
	user_search = request.args.get("user_search", "").strip()
	page = request.args.get("page", 1, type=int)

	query = ActivityLog.query

	if action_type:
		query = query.filter(ActivityLog.action == action_type)

	if user_search:
		query = query.join(User).filter(User.name.ilike(f"%{user_search}%") | User.email.ilike(f"%{user_search}%"))

	pagination = query.order_by(ActivityLog.timestamp.desc()).paginate(page=page, per_page=20, error_out=False)
	activities = []
	for act in pagination.items:
		if act.details:
			try:
				act.details_dict = json.loads(act.details)
			except Exception:
				act.details_dict = {}
		else:
			act.details_dict = {}
		activities.append(act)

	# Get distinct action types for filter dropdown
	action_types = db.session.query(ActivityLog.action).distinct().all()
	action_types = [a[0] for a in action_types]

	return render_template(
		"admin/activity.html",
		activities=activities,
		pagination=pagination,
		action_types=action_types,
		selected_action=action_type,
		user_search=user_search
	)


@main_bp.route("/api/books/suggest")
@login_required
def books_suggest():
	q = request.args.get("q", "").strip()
	if not q or len(q) < 2:
		return jsonify([])
	
	books = Book.query.filter(
		Book.title.ilike(f"%{q}%") | Book.author.ilike(f"%{q}%") | Book.category.ilike(f"%{q}%")
	).limit(8).all()
	
	return jsonify([{
		"id": b.id,
		"title": b.title,
		"author": b.author,
		"category": b.category,
		"available": b.available
	} for b in books])


# ─── Error Handlers ────────────────────────────────────────────────


@main_bp.app_errorhandler(403)
def forbidden_error(error):
	return render_template("errors/403.html"), 403


@main_bp.app_errorhandler(404)
def not_found_error(error):
	return render_template("errors/404.html"), 404


@main_bp.app_errorhandler(500)
def internal_error(error):
	db.session.rollback()
	return render_template("errors/500.html"), 500