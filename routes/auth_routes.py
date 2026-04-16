from functools import wraps
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db_connection import get_db_connection

auth = Blueprint('auth', __name__)


ROLE_LOGIN_SELECT_MAP = {
	"admin": "SELECT id, username, NULL AS company_id FROM admins WHERE username = %s AND password = %s",
	"company": "SELECT id, email AS username, id AS company_id FROM companies WHERE email = %s AND password = %s",
	"canteen": "SELECT id, username, email, company_id, password FROM canteen WHERE email = %s",
}


def _password_matches(stored_password, provided_password):
	if not stored_password:
		return False

	if stored_password == provided_password:
		return True

	try:
		return check_password_hash(stored_password, provided_password)
	except ValueError:
		return False


def login_required(roles=None):
	roles = roles or []

	def decorator(function):
		@wraps(function)
		def wrapper(*args, **kwargs):
			current_role = session.get("role")
			if not current_role:
				flash("Please login first.", "error")
				return redirect(url_for("auth.role_login", role="admin"))

			if roles and current_role not in roles:
				flash("You are not authorized to access this page.", "error")
				return redirect(url_for("auth.redirect_dashboard"))

			return function(*args, **kwargs)

		return wrapper

	return decorator


@auth.route("/")
def landing_page():
	return render_template("landing.html")


@auth.route("/<role>/login", methods=["GET", "POST"])
def role_login(role):
	allowed_roles = ["admin", "canteen", "company"]
	if role not in allowed_roles:
		flash("Invalid role.", "error")
		return redirect(url_for("auth.landing_page"))

	if request.method == "POST":
		if role == "admin":
			username = request.form.get("admin_username", "").strip()
		elif role == "canteen":
			username = request.form.get("email", "").strip()
		else:
			username = request.form.get("username", "").strip()
		password = request.form.get("password", "").strip()

		if not username or not password:
			login_error = "Email and password are required." if role == "canteen" else "Username and password are required."
			flash(login_error, "error")
			return render_template("auth/login.html", role=role, login_error=login_error)

		connection = get_db_connection()
		cursor = connection.cursor(dictionary=True)

		login_select = ROLE_LOGIN_SELECT_MAP[role]
		if role == "company":
			cursor.execute(login_select, (username, password))
		elif role == "admin":
			cursor.execute(login_select, (username, password))
		else:
			cursor.execute(login_select, (username,))
		user = cursor.fetchone()
		if role == "canteen" and user and not _password_matches(user.get("password"), password):
			user = None

		cursor.close()
		connection.close()

		if not user:
			login_error = "Invalid email or password"
			flash(login_error, "error")
			return render_template("auth/login.html", role=role, login_error=login_error)

		session["user_id"] = user["id"]
		session["username"] = user["username"]
		session["role"] = role
		session["company_id"] = user.get("company_id")

		flash(f"Welcome back, {user['username']}!", "success")
		return redirect(url_for("auth.redirect_dashboard"))

	return render_template("auth/login.html", role=role)


@auth.route("/dashboard")
@login_required()
def redirect_dashboard():
	role = session.get("role")

	if role == "admin":
		return redirect(url_for("admin.admin_dashboard"))
	if role == "company":
		return redirect(url_for("company.company_dashboard"))
	return redirect(url_for("auth.canteen_dashboard"))


@auth.route("/canteen/dashboard")
@login_required(["canteen"])
def canteen_dashboard():
	canteen_id = session.get("user_id")
	today = date.today()

	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT
			SUM(CASE WHEN status = 'Coming' THEN 1 ELSE 0 END) AS coming_count,
			SUM(CASE WHEN status = 'Not Coming' THEN 1 ELSE 0 END) AS not_coming_count
		FROM meal_responses
		WHERE canteen_id = %s AND response_date = %s
		""",
		(canteen_id, today),
	)
	meal_counts = cursor.fetchone() or {}

	coming_count = int(meal_counts.get("coming_count") or 0)
	not_coming_count = int(meal_counts.get("not_coming_count") or 0)

	cursor.execute(
		"""
		SELECT morning_item, afternoon_item, evening_item
		FROM canteen_menus
		WHERE canteen_id = %s AND menu_date = %s
		""",
		(canteen_id, today),
	)
	today_menu = cursor.fetchone()

	cursor.close()
	connection.close()

	meal_summary_count = coming_count if today_menu else 0

	stats = {
		"coming": coming_count,
		"not_coming": not_coming_count,
		"breakfast": meal_summary_count,
		"lunch": meal_summary_count,
		"dinner": meal_summary_count,
	}

	return render_template("canteen/canteen_dashboard.html", stats=stats, today_menu=today_menu, today=today)


@auth.route("/canteen/menu/add", methods=["GET", "POST"])
@login_required(["canteen"])
def add_menu():
	canteen_id = session.get("user_id")

	if request.method == "POST":
		menu_date = request.form.get("menu_date", "").strip()
		morning_item = request.form.get("morning_item", "").strip()
		afternoon_item = request.form.get("afternoon_item", "").strip()
		evening_item = request.form.get("evening_item", "").strip()

		if not menu_date or not morning_item or not afternoon_item or not evening_item:
			flash("All menu fields are required.", "error")
			return render_template("canteen/add_menu.html", today=date.today().isoformat())

		connection = get_db_connection()
		cursor = connection.cursor()
		cursor.execute(
			"""
			INSERT INTO canteen_menus (canteen_id, menu_date, morning_item, afternoon_item, evening_item)
			VALUES (%s, %s, %s, %s, %s)
			ON DUPLICATE KEY UPDATE
				morning_item = VALUES(morning_item),
				afternoon_item = VALUES(afternoon_item),
				evening_item = VALUES(evening_item),
				updated_at = CURRENT_TIMESTAMP
			""",
			(canteen_id, menu_date, morning_item, afternoon_item, evening_item),
		)
		connection.commit()
		cursor.close()
		connection.close()

		flash("Menu saved successfully.", "success")
		return redirect(url_for("auth.view_menu"))

	return render_template("canteen/add_menu.html", today=date.today().isoformat())


@auth.route("/canteen/menu/view")
@login_required(["canteen"])
def view_menu():
	canteen_id = session.get("user_id")
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""
		SELECT id, menu_date, morning_item, afternoon_item, evening_item, created_at, updated_at
		FROM canteen_menus
		WHERE canteen_id = %s
		ORDER BY menu_date DESC
		""",
		(canteen_id,),
	)
	menus = cursor.fetchall()
	cursor.close()
	connection.close()

	return render_template("canteen/view_menu.html", menus=menus)


@auth.route("/logout")
def logout():
	previous_role = session.get("role")
	session.clear()

	if previous_role == "admin":
		flash("You have been logged out.", "logout")
		return redirect(url_for("auth.role_login", role="admin"))

	flash("You have been logged out.", "success")
	return redirect(url_for("auth.landing_page"))