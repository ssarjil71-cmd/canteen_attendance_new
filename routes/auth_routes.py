from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database.db_connection import get_db_connection

auth = Blueprint('auth', __name__)


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
	allowed_roles = ["admin", "manager", "canteen", "company"]
	if role not in allowed_roles:
		flash("Invalid role.", "error")
		return redirect(url_for("auth.landing_page"))

	if request.method == "POST":
		username = request.form.get("username", "").strip()
		password = request.form.get("password", "").strip()

		if not username or not password:
			flash("Username and password are required.", "error")
			return render_template("auth/login.html", role=role)

		connection = get_db_connection()
		cursor = connection.cursor(dictionary=True)

		# Query the appropriate table based on role
		user = None
		if role == "admin":
			cursor.execute(
				"SELECT id, username, 'admin' as role, NULL as company_id FROM admins WHERE username = %s AND password = %s",
				(username, password)
			)
			user = cursor.fetchone()
		elif role == "manager":
			cursor.execute(
				"SELECT id, username, 'manager' as role, company_id FROM managers WHERE username = %s AND password = %s",
				(username, password)
			)
			user = cursor.fetchone()
		elif role == "canteen":
			cursor.execute(
				"SELECT id, username, 'canteen' as role, NULL as company_id FROM canteen WHERE username = %s AND password = %s",
				(username, password)
			)
			user = cursor.fetchone()
		elif role == "company":
			# For company login, we'll use company_code as username and a password field
			cursor.execute(
				"SELECT id, company_code as username, 'company' as role, id as company_id, company_name FROM companies WHERE company_code = %s AND company_password = %s",
				(username, password)
			)
			user = cursor.fetchone()

		cursor.close()
		connection.close()

		if not user:
			flash("Invalid credentials.", "error")
			return render_template("auth/login.html", role=role)

		session["user_id"] = user["id"]
		session["username"] = user["username"]
		session["role"] = user["role"]
		session["company_id"] = user.get("company_id")
		if role == "company":
			session["company_name"] = user.get("company_name")

		flash(f"Welcome back, {user['username']}!", "success")
		return redirect(url_for("auth.redirect_dashboard"))

	return render_template("auth/login.html", role=role)


@auth.route("/dashboard")
@login_required()
def redirect_dashboard():
	role = session.get("role")

	if role == "admin":
		return redirect(url_for("admin.admin_dashboard"))
	if role == "manager":
		return redirect(url_for("manager.dashboard"))
	if role == "company":
		return redirect(url_for("auth.company_dashboard"))
	return redirect(url_for("auth.canteen_dashboard"))


@auth.route("/manager/dashboard")
@login_required(["manager"])
def manager_dashboard():
	return render_template("manager/manager_dashboard.html")


@auth.route("/company/dashboard")
@login_required(["company"])
def company_dashboard():
	return render_template("company/company_dashboard.html")


@auth.route("/canteen/dashboard")
@login_required(["canteen"])
def canteen_dashboard():
	return render_template("canteen/canteen_dashboard.html")


@auth.route("/logout")
def logout():
	session.clear()
	flash("You have been logged out.", "success")
	return redirect(url_for("auth.landing_page"))