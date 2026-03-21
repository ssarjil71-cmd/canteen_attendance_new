from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database.db_connection import get_db_connection

admin = Blueprint('admin', __name__)


def admin_required(function):
	@wraps(function)
	def wrapper(*args, **kwargs):
		if session.get("role") != "admin":
			flash("Admin access required.", "error")
			return redirect(url_for("auth.role_login", role="admin"))
		return function(*args, **kwargs)

	return wrapper


@admin.route("/admin/dashboard")
@admin_required
def admin_dashboard():
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT id, company_name
		FROM companies
		ORDER BY company_name
		"""
	)
	companies = cursor.fetchall()
	total_companies = len(companies)

	cursor.close()
	connection.close()

	return render_template(
		"admin/admin_dashboard.html",
		companies=companies,
		total_companies=total_companies,
	)


@admin.route("/admin/add_company", methods=["GET", "POST"])
@admin_required
def add_company():
	if request.method == "POST":
		company_name = request.form.get("company_name", "").strip()
		company_code = request.form.get("company_code", "").strip()
		address = request.form.get("address", "").strip()
		email = request.form.get("email", "").strip()
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()
		attendance_module_enabled = 1 if request.form.get("attendance_module_enabled") else 0
		canteen_module_enabled = 1 if request.form.get("canteen_module_enabled") else 0

		if not company_name or not company_code or not email or not password or not confirm_password:
			flash("Company name, ID, email, password and confirm password are required.", "error")
			return render_template("admin/add_company.html")

		if password != confirm_password:
			flash("Password and confirm password must match.", "error")
			return render_template("admin/add_company.html")

		connection = get_db_connection()
		cursor = connection.cursor(dictionary=True)
		cursor.execute(
			"SELECT id FROM companies WHERE company_code = %s OR email = %s",
			(company_code, email),
		)
		existing_company = cursor.fetchone()
		if existing_company:
			cursor.close()
			connection.close()
			flash("Company ID or email already exists.", "error")
			return render_template("admin/add_company.html")

		cursor.execute(
			"""
			INSERT INTO companies
			(company_name, company_code, address, email, password, attendance_module_enabled, canteen_module_enabled)
			VALUES (%s, %s, %s, %s, %s, %s, %s)
			""",
			(
				company_name,
				company_code,
				address or None,
				email,
				password,
				attendance_module_enabled,
				canteen_module_enabled,
			),
		)
		connection.commit()
		cursor.close()
		connection.close()

		flash("Company created successfully.", "success")
		return redirect(url_for("admin.admin_dashboard"))

	return render_template("admin/add_company.html")


@admin.route("/admin/companies")
@admin_required
def view_companies():
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT id, company_name, company_code, email, attendance_module_enabled,
		       canteen_module_enabled, created_at
		FROM companies
		ORDER BY id DESC
		"""
	)
	companies = cursor.fetchall()

	cursor.close()
	connection.close()

	return render_template("admin/view_companies.html", companies=companies)


@admin.route("/admin/company/<int:company_id>")
@admin_required
def company_details(company_id):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT id, company_name, company_code, address, email, attendance_module_enabled,
		       canteen_module_enabled, created_at
		FROM companies
		WHERE id = %s
		""",
		(company_id,),
	)
	company = cursor.fetchone()

	cursor.close()
	connection.close()

	if not company:
		flash("Company not found.", "error")
		return redirect(url_for("admin.view_companies"))

	return render_template("admin/company_details.html", company=company)


@admin.route("/admin/company/<int:company_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_company(company_id):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
	company = cursor.fetchone()
	if not company:
		cursor.close()
		connection.close()
		flash("Company not found.", "error")
		return redirect(url_for("admin.admin_dashboard"))

	if request.method == "POST":
		company_name = request.form.get("company_name", "").strip()
		company_code = request.form.get("company_code", "").strip()
		address = request.form.get("address", "").strip()
		email = request.form.get("email", "").strip()
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()
		attendance_module_enabled = 1 if request.form.get("attendance_module_enabled") else 0
		canteen_module_enabled = 1 if request.form.get("canteen_module_enabled") else 0

		if not company_name or not company_code or not email:
			flash("Company name, ID and email are required.", "error")
			cursor.close()
			connection.close()
			return render_template("admin/edit_company.html", company=company)

		if password or confirm_password:
			if password != confirm_password:
				flash("Password and confirm password must match.", "error")
				cursor.close()
				connection.close()
				return render_template("admin/edit_company.html", company=company)

		cursor.execute(
			"""
			SELECT id FROM companies
			WHERE (company_code = %s OR email = %s) AND id != %s
			""",
			(company_code, email, company_id),
		)
		duplicate_company = cursor.fetchone()
		if duplicate_company:
			flash("Company ID or email already exists.", "error")
			cursor.close()
			connection.close()
			company.update(
				{
					"company_name": company_name,
					"company_code": company_code,
					"address": address,
					"email": email,
					"password": password,
					"attendance_module_enabled": attendance_module_enabled,
					"canteen_module_enabled": canteen_module_enabled,
				}
			)
			return render_template("admin/edit_company.html", company=company)

		if password:
			cursor.execute(
				"""
				UPDATE companies
				SET company_name = %s,
					company_code = %s,
					address = %s,
					email = %s,
					password = %s,
					attendance_module_enabled = %s,
					canteen_module_enabled = %s
				WHERE id = %s
				""",
				(
					company_name,
					company_code,
					address or None,
					email,
					password,
					attendance_module_enabled,
					canteen_module_enabled,
					company_id,
				),
			)
		else:
			cursor.execute(
				"""
				UPDATE companies
				SET company_name = %s,
					company_code = %s,
					address = %s,
					email = %s,
					attendance_module_enabled = %s,
					canteen_module_enabled = %s
				WHERE id = %s
				""",
				(
					company_name,
					company_code,
					address or None,
					email,
					attendance_module_enabled,
					canteen_module_enabled,
					company_id,
				),
			)
		connection.commit()
		cursor.close()
		connection.close()

		flash("Company updated successfully.", "success")
		return redirect(url_for("admin.admin_dashboard"))

	cursor.close()
	connection.close()
	return render_template("admin/edit_company.html", company=company)


@admin.route("/admin/company/<int:company_id>/delete", methods=["POST"])
@admin_required
def delete_company(company_id):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute("SELECT id FROM companies WHERE id = %s", (company_id,))
	company = cursor.fetchone()
	if not company:
		cursor.close()
		connection.close()
		flash("Company not found.", "error")
		return redirect(url_for("admin.admin_dashboard"))

	cursor.execute("DELETE FROM companies WHERE id = %s", (company_id,))
	connection.commit()
	cursor.close()
	connection.close()

	flash("Company deleted successfully.", "success")
	return redirect(url_for("admin.admin_dashboard"))


@admin.route("/admin/create_manager", methods=["GET", "POST"])
@admin_required
def create_manager():
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, company_name FROM companies ORDER BY company_name")
	companies = cursor.fetchall()

	if request.method == "POST":
		full_name = request.form.get("full_name", "").strip()
		email = request.form.get("email", "").strip()
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()
		company_id = request.form.get("company_id", "").strip()

		if not full_name or not email or not password or not confirm_password or not company_id:
			flash("All fields are required.", "error")
			cursor.close()
			connection.close()
			return render_template("admin/create_manager.html", companies=companies)

		if password != confirm_password:
			flash("Password and confirm password must match.", "error")
			cursor.close()
			connection.close()
			return render_template("admin/create_manager.html", companies=companies)

		username = email

		cursor.execute("SELECT id FROM managers WHERE username = %s OR email = %s", (username, email))
		existing_user = cursor.fetchone()
		if existing_user:
			flash("A user with this email already exists.", "error")
			cursor.close()
			connection.close()
			return render_template("admin/create_manager.html", companies=companies)

		cursor.execute(
			"""
			INSERT INTO managers (username, full_name, email, password, company_id)
			VALUES (%s, %s, %s, %s, %s)
			""",
			(username, full_name, email, password, company_id),
		)
		connection.commit()

		cursor.close()
		connection.close()
		flash("Manager account created successfully.", "success")
		return redirect(url_for("admin.admin_dashboard"))

	cursor.close()
	connection.close()
	return render_template("admin/create_manager.html", companies=companies)


@admin.route("/admin/managers")
@admin_required
def view_managers():
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT managers.id, managers.username, managers.full_name, managers.email, managers.company_id,
		       companies.company_name
		FROM managers
		LEFT JOIN companies ON managers.company_id = companies.id
		ORDER BY companies.company_name ASC, managers.full_name ASC, managers.id ASC
		"""
	)
	managers = cursor.fetchall()

	cursor.close()
	connection.close()

	return render_template("admin/view_managers.html", managers=managers)


@admin.route("/admin/manager/<int:manager_id>")
@admin_required
def manager_details(manager_id):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT managers.id, managers.username, managers.full_name, managers.email, managers.company_id,
		       companies.company_name
		FROM managers
		LEFT JOIN companies ON managers.company_id = companies.id
		WHERE managers.id = %s
		""",
		(manager_id,),
	)
	manager = cursor.fetchone()

	cursor.close()
	connection.close()

	if not manager:
		flash("Manager not found.", "error")
		return redirect(url_for("admin.view_managers"))

	return render_template("admin/manager_details.html", manager=manager)


@admin.route("/admin/manager/<int:manager_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_manager(manager_id):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, company_name FROM companies ORDER BY company_name")
	companies = cursor.fetchall()

	cursor.execute(
		"""
		SELECT id, username, full_name, email, company_id
		FROM managers
		WHERE id = %s
		""",
		(manager_id,),
	)
	manager = cursor.fetchone()
	if not manager:
		cursor.close()
		connection.close()
		flash("Manager not found.", "error")
		return redirect(url_for("admin.admin_dashboard"))

	if request.method == "POST":
		full_name = request.form.get("full_name", "").strip()
		email = request.form.get("email", "").strip()
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()
		company_id = request.form.get("company_id", "").strip()

		if not full_name or not email or not company_id:
			flash("Name, email and assigned company are required.", "error")
			cursor.close()
			connection.close()
			return render_template("admin/edit_manager.html", companies=companies, manager=manager)

		if password or confirm_password:
			if password != confirm_password:
				flash("Password and confirm password must match.", "error")
				cursor.close()
				connection.close()
				return render_template("admin/edit_manager.html", companies=companies, manager=manager)

		username = email
		cursor.execute(
			"SELECT id FROM managers WHERE (username = %s OR email = %s) AND id != %s",
			(username, email, manager_id),
		)
		existing_user = cursor.fetchone()
		if existing_user:
			flash("A user with this email already exists.", "error")
			cursor.close()
			connection.close()
			return render_template("admin/edit_manager.html", companies=companies, manager=manager)

		if password:
			cursor.execute(
				"""
				UPDATE managers
				SET username = %s, full_name = %s, email = %s, password = %s, company_id = %s
				WHERE id = %s
				""",
				(username, full_name, email, password, company_id, manager_id),
			)
		else:
			cursor.execute(
				"""
				UPDATE managers
				SET username = %s, full_name = %s, email = %s, company_id = %s
				WHERE id = %s
				""",
				(username, full_name, email, company_id, manager_id),
			)

		connection.commit()
		cursor.close()
		connection.close()
		flash("Manager updated successfully.", "success")
		return redirect(url_for("admin.admin_dashboard"))

	cursor.close()
	connection.close()
	return render_template("admin/edit_manager.html", companies=companies, manager=manager)


@admin.route("/admin/manager/<int:manager_id>/delete", methods=["POST"])
@admin_required
def delete_manager(manager_id):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute("SELECT id FROM managers WHERE id = %s", (manager_id,))
	manager = cursor.fetchone()
	if not manager:
		cursor.close()
		connection.close()
		flash("Manager not found.", "error")
		return redirect(url_for("admin.admin_dashboard"))

	cursor.execute("DELETE FROM managers WHERE id = %s", (manager_id,))
	connection.commit()
	cursor.close()
	connection.close()

	flash("Manager deleted successfully.", "success")
	return redirect(url_for("admin.admin_dashboard"))