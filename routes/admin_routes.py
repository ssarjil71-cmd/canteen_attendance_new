from functools import wraps

import mysql.connector

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database.db_connection import get_db_connection

admin = Blueprint('admin', __name__)


def _ensure_attendance_submodule_columns(connection):
	cursor = connection.cursor()
	cursor.execute("SHOW COLUMNS FROM companies LIKE 'attendance_qr_generation_enabled'")
	has_qr_generation = cursor.fetchone() is not None
	cursor.execute("SHOW COLUMNS FROM companies LIKE 'attendance_qr_scanner_enabled'")
	has_qr_scanner = cursor.fetchone() is not None

	if not has_qr_generation:
		cursor.execute("ALTER TABLE companies ADD COLUMN attendance_qr_generation_enabled TINYINT(1) NOT NULL DEFAULT 1")
	if not has_qr_scanner:
		cursor.execute("ALTER TABLE companies ADD COLUMN attendance_qr_scanner_enabled TINYINT(1) NOT NULL DEFAULT 1")

	cursor.close()
	if not has_qr_generation or not has_qr_scanner:
		connection.commit()


def _ensure_canteen_submodule_columns(connection):
	cursor = connection.cursor()
	cols = {
		"canteen_qr_generate_enabled": "TINYINT(1) NOT NULL DEFAULT 1",
		"canteen_qr_scan_enabled": "TINYINT(1) NOT NULL DEFAULT 1",
		"canteen_face_verify_enabled": "TINYINT(1) NOT NULL DEFAULT 1",
		"canteen_reports_enabled": "TINYINT(1) NOT NULL DEFAULT 1",
	}
	added = False
	for col, definition in cols.items():
		cursor.execute(f"SHOW COLUMNS FROM companies LIKE '{col}'")
		if cursor.fetchone() is None:
			cursor.execute(f"ALTER TABLE companies ADD COLUMN {col} {definition}")
			added = True
	cursor.close()
	if added:
		connection.commit()


def admin_required(function):
	@wraps(function)
	def wrapper(*args, **kwargs):
		if session.get("role") != "admin":
			flash("Admin access required.", "error")
			return redirect(url_for("auth.role_login", role="admin"))
		return function(*args, **kwargs)

	return wrapper


def _get_company_types(active_only=True):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	query = "SELECT id, type_name, is_active, created_at FROM company_types"
	if active_only:
		query += " WHERE is_active = 1"
	query += " ORDER BY type_name"

	cursor.execute(query)
	company_types = cursor.fetchall()

	cursor.close()
	connection.close()
	return company_types


def _get_company_types_with_assignment(active_only=True):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	query = (
		"""
		SELECT company_types.id,
		       company_types.type_name,
		       company_types.is_active,
		       company_types.created_at,
		       COUNT(companies.id) AS assigned_count,
		       GROUP_CONCAT(companies.company_name ORDER BY companies.company_name SEPARATOR '||') AS assigned_company_names
		FROM company_types
		LEFT JOIN companies ON companies.company_type_id = company_types.id
		"""
	)
	if active_only:
		query += " WHERE company_types.is_active = 1"
	query += " GROUP BY company_types.id, company_types.type_name, company_types.is_active, company_types.created_at"
	query += " ORDER BY company_types.type_name"

	cursor.execute(query)
	company_types = cursor.fetchall()

	for company_type in company_types:
		company_names_raw = company_type.get("assigned_company_names") or ""
		company_names = [name for name in company_names_raw.split("||") if name]
		preview_names = ", ".join(company_names[:3])
		remaining_count = len(company_names) - 3
		if remaining_count > 0:
			preview_names = f"{preview_names} and {remaining_count} more"
		company_type["assigned_preview"] = preview_names

	cursor.close()
	connection.close()
	return company_types


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
	company_types = _get_company_types(active_only=True)

	if request.method == "POST":
		company_name = request.form.get("company_name", "").strip()
		company_code = request.form.get("company_code", "").strip()
		company_type_id = request.form.get("company_type_id", "").strip()
		address = request.form.get("address", "").strip()
		email = request.form.get("email", "").strip()
		phone = request.form.get("phone", "").strip()
		city = request.form.get("city", "").strip()
		state = request.form.get("state", "").strip()
		pincode = request.form.get("pincode", "").strip()
		gst_number = request.form.get("gst_number", "").strip()
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()
		latitude = request.form.get("latitude", "").strip()
		longitude = request.form.get("longitude", "").strip()
		radius = request.form.get("radius", "").strip()
		attendance_module_enabled = 1 if request.form.get("attendance_module_enabled") else 0
		attendance_qr_generation_enabled = 1 if request.form.get("attendance_qr_generation_enabled") else 0
		attendance_qr_scanner_enabled = 1 if request.form.get("attendance_qr_scanner_enabled") else 0
		canteen_module_enabled = 1 if request.form.get("canteen_module_enabled") else 0
		canteen_qr_generate_enabled = 1 if request.form.get("canteen_qr_generate_enabled") else 0
		canteen_qr_scan_enabled = 1 if request.form.get("canteen_qr_scan_enabled") else 0
		canteen_face_verify_enabled = 1 if request.form.get("canteen_face_verify_enabled") else 0
		canteen_reports_enabled = 1 if request.form.get("canteen_reports_enabled") else 0
		salary_slip_module_enabled = 1 if request.form.get("salary_slip_module_enabled") else 0
		logo_file = request.files.get('logo')

		if not attendance_module_enabled:
			attendance_qr_generation_enabled = 0
			attendance_qr_scanner_enabled = 0

		if not canteen_module_enabled:
			canteen_qr_generate_enabled = 0
			canteen_qr_scan_enabled = 0
			canteen_face_verify_enabled = 0
			canteen_reports_enabled = 0

		if not (attendance_module_enabled or canteen_module_enabled or salary_slip_module_enabled):
			flash("Please select at least one module.", "error")
			return render_template("admin/add_company.html", company_types=company_types)

		if not all([company_name, company_type_id, email, phone, address, password, confirm_password, latitude, longitude, radius]):
			flash("All fields are mandatory except Company ID and Company Logo.", "error")
			return render_template("admin/add_company.html", company_types=company_types)

		if logo_file and logo_file.filename:
			logo_file.stream.seek(0, 2)
			logo_size = logo_file.stream.tell()
			logo_file.stream.seek(0)
			if logo_size > 10 * 1024 * 1024:
				flash("Company logo must be 10 MB or less.", "error")
				return render_template("admin/add_company.html", company_types=company_types)

		if len(phone) != 10 or not phone.isdigit():
			flash("Contact number must be exactly 10 digits.", "error")
			return render_template("admin/add_company.html", company_types=company_types)

		if password != confirm_password:
			flash("Password and confirm password must match.", "error")
			return render_template("admin/add_company.html", company_types=company_types)

		connection = get_db_connection()
		cursor = connection.cursor(dictionary=True)
		_ensure_attendance_submodule_columns(connection)
		
		# Check if email already exists
		cursor.execute("SELECT id FROM companies WHERE email = %s", (email,))
		existing_company = cursor.fetchone()
		if existing_company:
			cursor.close()
			connection.close()
			flash("Email already exists.", "error")
			return render_template("admin/add_company.html", company_types=company_types)

		if company_code:
			cursor.execute("SELECT id FROM companies WHERE company_code = %s", (company_code,))
			existing_company_code = cursor.fetchone()
			if existing_company_code:
				cursor.close()
				connection.close()
				flash("Company ID already exists.", "error")
				return render_template("admin/add_company.html", company_types=company_types)

		cursor.execute("SELECT id FROM company_types WHERE id = %s AND is_active = 1", (company_type_id,))
		selected_company_type = cursor.fetchone()
		if not selected_company_type:
			cursor.close()
			connection.close()
			flash("Please select a valid company type.", "error")
			return render_template("admin/add_company.html", company_types=company_types)

		# Handle logo upload
		logo_filename = None
		if logo_file and logo_file.filename:
			import os
			from werkzeug.utils import secure_filename
			from flask import current_app
			
			# Create uploads directory if it doesn't exist
			upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
			os.makedirs(upload_dir, exist_ok=True)
			
			# Generate secure filename
			import time
			filename = secure_filename(logo_file.filename)
			timestamp = str(int(time.time()))
			logo_filename = f"company_new_{timestamp}_{filename}"
			logo_path = os.path.join(upload_dir, logo_filename)
			
			# Save the file
			logo_file.save(logo_path)

		cursor.execute(
			"""
			INSERT INTO companies
			(company_name, company_code, company_type_id, address, email, phone, city, state, pincode,
			 gst_number, logo, latitude, longitude, radius, password,
			 attendance_module_enabled, attendance_qr_generation_enabled, attendance_qr_scanner_enabled,
			 canteen_module_enabled, canteen_qr_generate_enabled, canteen_qr_scan_enabled,
			 canteen_face_verify_enabled, canteen_reports_enabled,
			 salary_slip_module_enabled, status)
			VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
			""",
			(
				company_name,
				company_code or None,
				int(company_type_id),
				address or None,
				email,
				phone,
				city or None,
				state or None,
				pincode or None,
				gst_number or None,
				logo_filename,
				float(latitude) if latitude else None,
				float(longitude) if longitude else None,
				int(radius) if radius else 100,
				password,
				attendance_module_enabled,
				attendance_qr_generation_enabled,
				attendance_qr_scanner_enabled,
				canteen_module_enabled,
				canteen_qr_generate_enabled,
				canteen_qr_scan_enabled,
				canteen_face_verify_enabled,
				canteen_reports_enabled,
				salary_slip_module_enabled,
				'active'
			),
		)
		connection.commit()
		cursor.close()
		connection.close()

		flash("Company created successfully.", "success")
		return redirect(url_for("admin.admin_dashboard"))

	return render_template("admin/add_company.html", company_types=company_types)


@admin.route("/admin/add_company_type", methods=["GET", "POST"])
@admin_required
def add_company_type():
	if request.method == "POST":
		type_name = request.form.get("type_name", "").strip()

		if not type_name:
			flash("Company type name is required.", "error")
			return render_template("admin/add_company_type.html", company_types=_get_company_types_with_assignment(active_only=True))

		connection = get_db_connection()
		cursor = connection.cursor(dictionary=True)
		cursor.execute("SELECT id, is_active FROM company_types WHERE LOWER(type_name) = LOWER(%s)", (type_name,))
		existing_type = cursor.fetchone()

		if existing_type:
			if existing_type["is_active"] == 0:
				cursor.execute("UPDATE company_types SET is_active = 1 WHERE id = %s", (existing_type["id"],))
				connection.commit()
				cursor.close()
				connection.close()
				flash("Company type re-activated successfully.", "success")
				return redirect(url_for("admin.add_company_type"))

			cursor.close()
			connection.close()
			flash("This company type already exists.", "error")
			return render_template("admin/add_company_type.html", company_types=_get_company_types_with_assignment(active_only=True))

		cursor.execute("INSERT INTO company_types (type_name, is_active) VALUES (%s, 1)", (type_name,))
		connection.commit()
		cursor.close()
		connection.close()

		flash("Company type added successfully.", "success")
		return redirect(url_for("admin.add_company_type"))

	return render_template("admin/add_company_type.html", company_types=_get_company_types_with_assignment(active_only=True))


@admin.route("/admin/company_type/<int:type_id>/delete", methods=["POST"])
@admin_required
def delete_company_type(type_id):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute("SELECT id, type_name, is_active FROM company_types WHERE id = %s", (type_id,))
	company_type = cursor.fetchone()
	if not company_type:
		cursor.close()
		connection.close()
		flash("Company type not found.", "error")
		return redirect(url_for("admin.add_company_type"))

	cursor.execute(
		"SELECT company_name FROM companies WHERE company_type_id = %s ORDER BY company_name",
		(type_id,),
	)
	assigned_companies = cursor.fetchall()

	if assigned_companies:
		if company_type["is_active"] == 1:
			cursor.execute("UPDATE company_types SET is_active = 0 WHERE id = %s", (type_id,))
			connection.commit()

		assigned_company_names = [row["company_name"] for row in assigned_companies]
		preview_names = ", ".join(assigned_company_names[:3])
		remaining_count = len(assigned_company_names) - 3
		if remaining_count > 0:
			preview_names = f"{preview_names} and {remaining_count} more"

		cursor.close()
		connection.close()
		flash(
			f'Warning: "{company_type["type_name"]}" is assigned to {len(assigned_company_names)} compan'
			f'{"y" if len(assigned_company_names) == 1 else "ies"} ({preview_names}). '
			"It was deactivated instead of permanently deleted, and it will stay visible for those companies.",
			"error",
		)
		return redirect(url_for("admin.add_company_type"))

	try:
		cursor.execute("DELETE FROM company_types WHERE id = %s", (type_id,))
		connection.commit()
	except mysql.connector.Error:
		connection.rollback()
		cursor.close()
		connection.close()
		flash("Unable to delete company type right now. Please try again.", "error")
		return redirect(url_for("admin.add_company_type"))

	cursor.close()
	connection.close()
	flash("Company type deleted successfully.", "success")
	return redirect(url_for("admin.add_company_type"))


@admin.route("/admin/companies")
@admin_required
def view_companies():
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT companies.id, companies.company_name, companies.company_code, companies.email,
		       companies.attendance_module_enabled, companies.canteen_module_enabled,
		       companies.salary_slip_module_enabled, companies.created_at,
		       company_types.type_name AS company_type_name
		FROM companies
		LEFT JOIN company_types ON company_types.id = companies.company_type_id
		ORDER BY companies.id DESC
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
	_ensure_attendance_submodule_columns(connection)

	cursor.execute(
		"""
		SELECT companies.*, company_types.type_name AS company_type_name
		FROM companies
		LEFT JOIN company_types ON company_types.id = companies.company_type_id
		WHERE companies.id = %s
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
	_ensure_attendance_submodule_columns(connection)

	cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
	company = cursor.fetchone()
	if not company:
		cursor.close()
		connection.close()
		flash("Company not found.", "error")
		return redirect(url_for("admin.admin_dashboard"))

	company_types = _get_company_types(active_only=True)
	if company.get("company_type_id"):
		type_ids = {company_type["id"] for company_type in company_types}
		if company["company_type_id"] not in type_ids:
			cursor.execute(
				"SELECT id, type_name, is_active, created_at FROM company_types WHERE id = %s",
				(company["company_type_id"],),
			)
			assigned_inactive_type = cursor.fetchone()
			if assigned_inactive_type:
				company_types.append(assigned_inactive_type)

	if request.method == "POST":
		company_name = request.form.get("company_name", "").strip()
		company_code = request.form.get("company_code", "").strip()
		company_type_id = request.form.get("company_type_id", "").strip()
		address = request.form.get("address", "").strip()
		email = request.form.get("email", "").strip()
		phone = request.form.get("phone", "").strip()
		city = request.form.get("city", company.get("city") or "").strip()
		state = request.form.get("state", company.get("state") or "").strip()
		pincode = request.form.get("pincode", company.get("pincode") or "").strip()
		gst_number = request.form.get("gst_number", company.get("gst_number") or "").strip()
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()
		latitude = request.form.get("latitude", "").strip()
		longitude = request.form.get("longitude", "").strip()
		radius = request.form.get("radius", "").strip()
		attendance_module_enabled = 1 if request.form.get("attendance_module_enabled") else 0
		attendance_qr_generation_enabled = 1 if request.form.get("attendance_qr_generation_enabled") else 0
		attendance_qr_scanner_enabled = 1 if request.form.get("attendance_qr_scanner_enabled") else 0
		canteen_module_enabled = 1 if request.form.get("canteen_module_enabled") else 0
		canteen_qr_generate_enabled = 1 if request.form.get("canteen_qr_generate_enabled") else 0
		canteen_qr_scan_enabled = 1 if request.form.get("canteen_qr_scan_enabled") else 0
		canteen_face_verify_enabled = 1 if request.form.get("canteen_face_verify_enabled") else 0
		canteen_reports_enabled = 1 if request.form.get("canteen_reports_enabled") else 0
		salary_slip_module_enabled = 1 if request.form.get("salary_slip_module_enabled") else 0
		logo_file = request.files.get('logo')

		if not attendance_module_enabled:
			attendance_qr_generation_enabled = 0
			attendance_qr_scanner_enabled = 0

		if not canteen_module_enabled:
			canteen_qr_generate_enabled = 0
			canteen_qr_scan_enabled = 0
			canteen_face_verify_enabled = 0
			canteen_reports_enabled = 0

		_ensure_attendance_submodule_columns(connection)
		_ensure_canteen_submodule_columns(connection)

		if not (attendance_module_enabled or canteen_module_enabled or salary_slip_module_enabled):
			flash("Please select at least one module.", "error")
			company.update(
				{
					"company_name": company_name,
					"company_code": company_code,
					"company_type_id": int(company_type_id) if company_type_id.isdigit() else company.get("company_type_id"),
					"address": address,
					"email": email,
					"phone": phone,
					"latitude": latitude,
					"longitude": longitude,
					"radius": radius,
					"attendance_module_enabled": attendance_module_enabled,
					"canteen_module_enabled": canteen_module_enabled,
					"salary_slip_module_enabled": salary_slip_module_enabled,
				}
			)
			cursor.close()
			connection.close()
			return render_template("admin/edit_company.html", company=company, company_types=company_types)

		if not all([company_name, company_type_id, email, phone, address, latitude, longitude, radius]):
			flash("All fields are mandatory except Company ID, Company Logo and Password.", "error")
			company.update(
				{
					"company_name": company_name,
					"company_code": company_code,
					"company_type_id": int(company_type_id) if company_type_id.isdigit() else company.get("company_type_id"),
					"address": address,
					"email": email,
					"phone": phone,
					"latitude": latitude,
					"longitude": longitude,
					"radius": radius,
					"attendance_module_enabled": attendance_module_enabled,
					"canteen_module_enabled": canteen_module_enabled,
					"salary_slip_module_enabled": salary_slip_module_enabled,
				}
			)
			cursor.close()
			connection.close()
			return render_template("admin/edit_company.html", company=company, company_types=company_types)

		if len(phone) != 10 or not phone.isdigit():
			flash("Contact number must be exactly 10 digits.", "error")
			company.update(
				{
					"company_name": company_name,
					"company_code": company_code,
					"company_type_id": int(company_type_id) if company_type_id.isdigit() else company.get("company_type_id"),
					"address": address,
					"email": email,
					"phone": phone,
					"latitude": latitude,
					"longitude": longitude,
					"radius": radius,
					"attendance_module_enabled": attendance_module_enabled,
					"canteen_module_enabled": canteen_module_enabled,
					"salary_slip_module_enabled": salary_slip_module_enabled,
				}
			)
			cursor.close()
			connection.close()
			return render_template("admin/edit_company.html", company=company, company_types=company_types)

		if (password or confirm_password) and password != confirm_password:
			flash("Password and confirm password must match.", "error")
			company.update(
				{
					"company_name": company_name,
					"company_code": company_code,
					"company_type_id": int(company_type_id) if company_type_id.isdigit() else company.get("company_type_id"),
					"address": address,
					"email": email,
					"phone": phone,
					"latitude": latitude,
					"longitude": longitude,
					"radius": radius,
					"attendance_module_enabled": attendance_module_enabled,
					"canteen_module_enabled": canteen_module_enabled,
					"salary_slip_module_enabled": salary_slip_module_enabled,
				}
			)
			cursor.close()
			connection.close()
			return render_template("admin/edit_company.html", company=company, company_types=company_types)

		if logo_file and logo_file.filename:
			logo_file.stream.seek(0, 2)
			logo_size = logo_file.stream.tell()
			logo_file.stream.seek(0)
			if logo_size > 10 * 1024 * 1024:
				flash("Company logo must be 10 MB or less.", "error")
				company.update(
					{
						"company_name": company_name,
						"company_code": company_code,
						"company_type_id": int(company_type_id) if company_type_id.isdigit() else company.get("company_type_id"),
						"address": address,
						"email": email,
						"phone": phone,
						"latitude": latitude,
						"longitude": longitude,
						"radius": radius,
						"attendance_module_enabled": attendance_module_enabled,
						"canteen_module_enabled": canteen_module_enabled,
						"salary_slip_module_enabled": salary_slip_module_enabled,
					}
				)
				cursor.close()
				connection.close()
				return render_template("admin/edit_company.html", company=company, company_types=company_types)

		cursor.execute("SELECT id FROM company_types WHERE id = %s", (company_type_id,))
		selected_company_type = cursor.fetchone()
		if not selected_company_type:
			flash("Please select a valid company type.", "error")
			company.update(
				{
					"company_name": company_name,
					"company_code": company_code,
					"company_type_id": company.get("company_type_id"),
					"address": address,
					"email": email,
					"phone": phone,
					"latitude": latitude,
					"longitude": longitude,
					"radius": radius,
					"attendance_module_enabled": attendance_module_enabled,
					"canteen_module_enabled": canteen_module_enabled,
					"salary_slip_module_enabled": salary_slip_module_enabled,
				}
			)
			cursor.close()
			connection.close()
			return render_template("admin/edit_company.html", company=company, company_types=company_types)

		# Check if email already exists for other companies
		cursor.execute(
			"SELECT id FROM companies WHERE email = %s AND id != %s",
			(email, company_id),
		)
		duplicate_company = cursor.fetchone()
		if duplicate_company:
			flash("Email already exists.", "error")
			company.update(
				{
					"company_name": company_name,
					"company_code": company_code,
					"company_type_id": int(company_type_id),
					"address": address,
					"email": email,
					"phone": phone,
					"latitude": latitude,
					"longitude": longitude,
					"radius": radius,
					"attendance_module_enabled": attendance_module_enabled,
					"canteen_module_enabled": canteen_module_enabled,
					"salary_slip_module_enabled": salary_slip_module_enabled,
				}
			)
			cursor.close()
			connection.close()
			return render_template("admin/edit_company.html", company=company, company_types=company_types)

		if company_code:
			cursor.execute(
				"SELECT id FROM companies WHERE company_code = %s AND id != %s",
				(company_code, company_id),
			)
			duplicate_company_code = cursor.fetchone()
			if duplicate_company_code:
				flash("Company ID already exists.", "error")
				company.update(
					{
						"company_name": company_name,
						"company_code": company_code,
						"company_type_id": int(company_type_id),
						"address": address,
						"email": email,
						"phone": phone,
						"latitude": latitude,
						"longitude": longitude,
						"radius": radius,
						"attendance_module_enabled": attendance_module_enabled,
						"canteen_module_enabled": canteen_module_enabled,
						"salary_slip_module_enabled": salary_slip_module_enabled,
					}
				)
				cursor.close()
				connection.close()
				return render_template("admin/edit_company.html", company=company, company_types=company_types)

		# Handle logo upload
		logo_filename = company.get('logo')
		import os
		from flask import current_app
		upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
		os.makedirs(upload_dir, exist_ok=True)

		from werkzeug.utils import secure_filename

		if logo_file and logo_file.filename:
			if company.get('logo'):
				old_logo_path = os.path.join(upload_dir, company['logo'])
				if os.path.exists(old_logo_path):
					os.remove(old_logo_path)

			import time
			filename = secure_filename(logo_file.filename)
			timestamp = str(int(time.time()))
			logo_filename = f"company_edit_{company_id}_{timestamp}_{filename}"
			logo_path = os.path.join(upload_dir, logo_filename)
			logo_file.save(logo_path)

		password_to_save = password if password else company.get("password")

		cursor.execute(
			"""
			UPDATE companies
			SET company_name = %s,
				company_code = %s,
				company_type_id = %s,
				address = %s,
				email = %s,
				phone = %s,
				city = %s,
				state = %s,
				pincode = %s,
				gst_number = %s,
				logo = %s,
				password = %s,
				latitude = %s,
				longitude = %s,
				radius = %s,
				attendance_module_enabled = %s,
				attendance_qr_generation_enabled = %s,
				attendance_qr_scanner_enabled = %s,
				canteen_module_enabled = %s,
				canteen_qr_generate_enabled = %s,
				canteen_qr_scan_enabled = %s,
				canteen_face_verify_enabled = %s,
				canteen_reports_enabled = %s,
				salary_slip_module_enabled = %s
			WHERE id = %s
			""",
			(
				company_name,
				company_code or None,
				int(company_type_id),
				address or None,
				email,
				phone or None,
				city or None,
				state or None,
				pincode or None,
				gst_number or None,
				logo_filename,
				password_to_save,
				latitude or None,
				longitude or None,
				int(radius) if radius else 100,
				attendance_module_enabled,
				attendance_qr_generation_enabled,
				attendance_qr_scanner_enabled,
				canteen_module_enabled,
				canteen_qr_generate_enabled,
				canteen_qr_scan_enabled,
				canteen_face_verify_enabled,
				canteen_reports_enabled,
				salary_slip_module_enabled,
				company_id,
			),
		)
		connection.commit()
		cursor.close()
		connection.close()

		flash("Company updated successfully.", "success")
		return redirect(url_for("admin.company_details", company_id=company_id))

	cursor.close()
	connection.close()
	return render_template("admin/edit_company.html", company=company, company_types=company_types)


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
	return redirect(url_for("admin.view_companies"))


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