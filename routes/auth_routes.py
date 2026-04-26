from functools import wraps
from datetime import date
import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db_connection import get_db_connection
from module_access import has_module, module_required, update_module_flags_in_session

auth = Blueprint('auth', __name__)


def _attendance_has_meal_status(connection):
	cursor = connection.cursor()
	cursor.execute("SHOW COLUMNS FROM attendance LIKE 'meal_status'")
	has_column = cursor.fetchone() is not None
	cursor.close()
	return has_column


def _attendance_has_meal_taken(connection):
	cursor = connection.cursor()
	cursor.execute("SHOW COLUMNS FROM attendance LIKE 'meal_taken'")
	has_column = cursor.fetchone() is not None
	cursor.close()
	return has_column


def _attendance_has_meal_confirmed(connection):
	cursor = connection.cursor()
	cursor.execute("SHOW COLUMNS FROM attendance LIKE 'meal_confirmed'")
	has_column = cursor.fetchone() is not None
	cursor.close()
	return has_column


def _ensure_meal_confirmed_column(connection):
	if _attendance_has_meal_confirmed(connection):
		return
	cursor = connection.cursor()
	cursor.execute("ALTER TABLE attendance ADD COLUMN meal_confirmed ENUM('YES', 'NO') DEFAULT 'NO' AFTER meal_taken")
	cursor.close()
	connection.commit()


def _attendance_has_face_verified(connection):
	cursor = connection.cursor()
	cursor.execute("SHOW COLUMNS FROM attendance LIKE 'face_verified'")
	has_column = cursor.fetchone() is not None
	cursor.close()
	return has_column


def _table_exists(connection, table_name):
	cursor = connection.cursor()
	cursor.execute("SHOW TABLES LIKE %s", (table_name,))
	exists = cursor.fetchone() is not None
	cursor.close()
	return exists


def _ensure_canteen_reports_face_verified_column(connection):
	if not _table_exists(connection, "canteen_reports"):
		return

	cursor = connection.cursor()
	cursor.execute("SHOW COLUMNS FROM canteen_reports LIKE 'face_verified'")
	has_column = cursor.fetchone() is not None
	if not has_column:
		cursor.execute("ALTER TABLE canteen_reports ADD COLUMN face_verified VARCHAR(10) DEFAULT 'NO'")
		connection.commit()
	cursor.close()


ROLE_LOGIN_SELECT_MAP = {
	"admin": "SELECT id, username, NULL AS company_id FROM admins WHERE username = %s AND password = %s",
	"company": "SELECT id, email AS username, id AS company_id, subscription_end, subscription_status FROM companies WHERE email = %s AND password = %s",
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

		# Subscription check for company login — allow login but flag as expired
		if role == "company":
			from datetime import date as _date
			sub_end = user.get("subscription_end")
			if sub_end and _date.today() > sub_end:
				conn2 = get_db_connection()
				cur2 = conn2.cursor()
				cur2.execute(
					"UPDATE companies SET subscription_status = 'expired' WHERE id = %s",
					(user["id"],)
				)
				conn2.commit()
				cur2.close()
				conn2.close()

		session["user_id"] = user["id"]
		session["username"] = user["username"]
		session["role"] = role
		session["company_id"] = user.get("company_id")
		session.permanent = True  # persist session across navigation

		# Flag expired subscription in session so routes can redirect without a DB hit
		if role == "company":
			from datetime import date as _date
			sub_end = user.get("subscription_end")
			if sub_end and _date.today() > sub_end:
				session["subscription_status"] = "expired"
			else:
				session.pop("subscription_status", None)  # persist session across navigation

		if role == "canteen" and not has_module(user.get("company_id"), "canteen_management"):
			session.clear()
			login_error = "Canteen Management module is disabled for your company."
			flash(login_error, "error")
			return render_template("auth/login.html", role=role, login_error=login_error)

		if role in {"company", "canteen"} and session.get("company_id"):
			update_module_flags_in_session(session.get("company_id"))
		else:
			session.pop("company_modules", None)
			session.pop("company_submodules", None)
			session.pop("attendance_module_enabled", None)
			session.pop("attendance_qr_generation_enabled", None)
			session.pop("attendance_qr_scanner_enabled", None)
			session.pop("canteen_module_enabled", None)
			session.pop("salary_slip_module_enabled", None)

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
@module_required("canteen_management")
def canteen_dashboard():
	company_id = session.get("company_id")
	canteen_id = session.get("user_id")
	today = date.today()

	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	# Total employees for this company
	cursor.execute(
		"SELECT COUNT(*) AS count FROM employees WHERE company_id = %s",
		(company_id,),
	)
	total_employees = int((cursor.fetchone() or {}).get("count") or 0)

	if _attendance_has_meal_status(connection):
		cursor.execute(
			"""
			SELECT COUNT(DISTINCT a.employee_id) AS coming_count
			FROM attendance a
			JOIN employees e
			  ON e.company_id = a.company_id
			 AND a.employee_id = e.emp_id
			WHERE a.company_id = %s
			  AND a.date = %s
			  AND a.check_in_time IS NOT NULL
			  AND a.meal_status = 'YES'
			""",
			(company_id, today),
		)
		row = cursor.fetchone() or {}
		coming_count = int(row.get("coming_count") or 0)
		not_coming_count = max(total_employees - coming_count, 0)
	else:
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
		WHERE canteen_id = %s AND day_of_week = %s
		""",
		(canteen_id, today.strftime("%A")),
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


@auth.route("/canteen/meal-scan")
def canteen_meal_scan():
	logged_in_canteen = session.get("role") == "canteen"
	company_id = request.args.get("company_id", type=int)

	if not company_id and logged_in_canteen:
		company_id = session.get("company_id")

	if not company_id:
		return render_template("attendance/error.html", message="Invalid meal scan link. Missing company information."), 400

	if not has_module(company_id, "canteen_management"):
		return render_template("attendance/error.html", message="Canteen Management module is disabled for this company."), 403

	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, company_name FROM companies WHERE id = %s", (company_id,))
	company = cursor.fetchone()
	cursor.close()
	connection.close()

	if not company:
		return render_template("attendance/error.html", message="Company not found for meal scan."), 404

	scan_url = url_for("auth.canteen_meal_scan", _external=True, company_id=company_id)
	qr_image_path = None
	if logged_in_canteen and session.get("company_id") == company_id:
		try:
			import qrcode
			static_dir = os.path.join(current_app.root_path, "static")
			qr_dir = os.path.join(static_dir, "qr")
			os.makedirs(qr_dir, exist_ok=True)
			qr_filename = f"canteen_meal_scan_company_{company_id}.png"
			qr_file_path = os.path.join(qr_dir, qr_filename)

			qr = qrcode.QRCode(
				version=1,
				error_correction=qrcode.constants.ERROR_CORRECT_H,
				box_size=10,
				border=4,
			)
			qr.add_data(scan_url)
			qr.make(fit=True)
			qr_img = qr.make_image(fill_color="black", back_color="white")
			qr_img.save(qr_file_path)
			qr_image_path = f"qr/{qr_filename}"
		except Exception as exc:
			current_app.logger.error("Failed to generate meal scan QR: %s", exc)

	return render_template(
		"canteen/meal_scan.html",
		company=company,
		company_id=company_id,
		scan_url=scan_url,
		qr_image_path=qr_image_path,
		show_qr_tools=bool(logged_in_canteen and session.get("company_id") == company_id),
	)


@auth.route("/canteen/menu/add", methods=["GET", "POST"])
@login_required(["canteen"])
@module_required("canteen_management")
def add_menu():
	canteen_id = session.get("user_id")
	DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

	if request.method == "POST":
		day_of_week = request.form.get("day_of_week", "").strip()
		morning_item = request.form.get("morning_item", "").strip()
		afternoon_item = request.form.get("afternoon_item", "").strip()
		evening_item = request.form.get("evening_item", "").strip()

		if day_of_week not in DAYS or not morning_item or not afternoon_item or not evening_item:
			flash("All menu fields are required.", "error")
			return render_template("canteen/add_menu.html", days=DAYS)

		connection = get_db_connection()
		cursor = connection.cursor()
		cursor.execute(
			"""
			INSERT INTO canteen_menus (canteen_id, day_of_week, morning_item, afternoon_item, evening_item)
			VALUES (%s, %s, %s, %s, %s)
			ON DUPLICATE KEY UPDATE
				morning_item = VALUES(morning_item),
				afternoon_item = VALUES(afternoon_item),
				evening_item = VALUES(evening_item),
				updated_at = CURRENT_TIMESTAMP
			""",
			(canteen_id, day_of_week, morning_item, afternoon_item, evening_item),
		)
		connection.commit()
		cursor.close()
		connection.close()

		flash("Menu saved successfully.", "success")
		return redirect(url_for("auth.view_menu"))

	# GET: pre-fill existing menu if day is provided
	preselect_day = request.args.get("day", "")
	existing_menu = None
	if preselect_day in DAYS:
		connection = get_db_connection()
		cursor = connection.cursor(dictionary=True)
		cursor.execute(
			"SELECT * FROM canteen_menus WHERE canteen_id = %s AND day_of_week = %s",
			(canteen_id, preselect_day),
		)
		existing_menu = cursor.fetchone()
		cursor.close()
		connection.close()

	return render_template("canteen/add_menu.html", days=DAYS, preselect_day=preselect_day, existing_menu=existing_menu)

	return render_template("canteen/add_menu.html", days=DAYS, preselect_day=request.args.get("day", ""))

	# GET: pre-fill existing menu if day is provided
	preselect_day = request.args.get("day", "")
	existing_menu = None
	if preselect_day in DAYS:
		connection = get_db_connection()
		cursor = connection.cursor(dictionary=True)
		cursor.execute(
			"SELECT * FROM canteen_menus WHERE canteen_id = %s AND day_of_week = %s",
			(canteen_id, preselect_day),
		)
		existing_menu = cursor.fetchone()
		cursor.close()
		connection.close()

	return render_template("canteen/add_menu.html", days=DAYS, preselect_day=preselect_day, existing_menu=existing_menu)


@auth.route("/canteen/menu/edit/<day>", methods=["GET", "POST"])
@login_required(["canteen"])
@module_required("canteen_management")
def edit_menu(day):
	DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	if day not in DAYS:
		flash("Invalid day.", "error")
		return redirect(url_for("auth.view_menu"))

	canteen_id = session.get("user_id")
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)

	if request.method == "POST":
		morning_item = request.form.get("morning_item", "").strip()
		afternoon_item = request.form.get("afternoon_item", "").strip()
		evening_item = request.form.get("evening_item", "").strip()

		if not morning_item or not afternoon_item or not evening_item:
			flash("All fields are required.", "error")
		else:
			cursor.execute(
				"""
				INSERT INTO canteen_menus (canteen_id, day_of_week, morning_item, afternoon_item, evening_item)
				VALUES (%s, %s, %s, %s, %s)
				ON DUPLICATE KEY UPDATE
					morning_item = VALUES(morning_item),
					afternoon_item = VALUES(afternoon_item),
					evening_item = VALUES(evening_item),
					updated_at = CURRENT_TIMESTAMP
				""",
				(canteen_id, day, morning_item, afternoon_item, evening_item),
			)
			connection.commit()
			flash("Menu updated.", "success")
			cursor.close()
			connection.close()
			return redirect(url_for("auth.view_menu"))

	cursor.execute(
		"SELECT * FROM canteen_menus WHERE canteen_id = %s AND day_of_week = %s",
		(canteen_id, day),
	)
	existing = cursor.fetchone()
	cursor.close()
	connection.close()
	return render_template("canteen/edit_menu.html", day=day, menu=existing, days=DAYS)


@auth.route("/canteen/menu/view")
@login_required(["canteen"])
@module_required("canteen_management")
def view_menu():
	canteen_id = session.get("user_id")
	DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	today_day = date.today().strftime("%A")

	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""
		SELECT id, day_of_week, morning_item, afternoon_item, evening_item, updated_at
		FROM canteen_menus
		WHERE canteen_id = %s AND day_of_week IS NOT NULL
		ORDER BY FIELD(day_of_week, 'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
		""",
		(canteen_id,),
	)
	menus_raw = cursor.fetchall()
	cursor.close()
	connection.close()

	# Build a dict keyed by day for easy lookup
	menus_by_day = {m["day_of_week"]: m for m in menus_raw}

	return render_template(
		"canteen/view_menu.html",
		menus_by_day=menus_by_day,
		days=DAYS,
		today_day=today_day,
	)


@auth.route("/canteen/reports")
@login_required(["canteen"])
@module_required("canteen_management")
def canteen_reports():
	company_id = session.get("company_id")
	if not company_id:
		flash("Company session is missing. Please login again.", "error")
		return redirect(url_for("auth.role_login", role="canteen"))
	selected_date = request.args.get("date") or date.today().isoformat()
	meal_filter = (request.args.get("meal_filter") or "all").strip().lower()
	search_query = (request.args.get("q") or "").strip()

	if meal_filter not in {"all", "yes", "no"}:
		meal_filter = "all"

	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)
	if not _attendance_has_meal_status(connection):
		cursor.execute("ALTER TABLE attendance ADD COLUMN meal_status ENUM('YES', 'NO') DEFAULT 'NO' AFTER check_out_time")
	if not _attendance_has_meal_taken(connection):
		cursor.execute("ALTER TABLE attendance ADD COLUMN meal_taken ENUM('YES', 'NO') DEFAULT 'NO' AFTER meal_status")
	if not _attendance_has_meal_confirmed(connection):
		_ensure_meal_confirmed_column(connection)
		connection.commit()
	if not _attendance_has_face_verified(connection):
		cursor.execute("ALTER TABLE attendance ADD COLUMN face_verified TINYINT(1) DEFAULT 0 AFTER meal_confirmed")
		connection.commit()
	_ensure_canteen_reports_face_verified_column(connection)

	count_query = (
		"""
		SELECT COUNT(DISTINCT a.employee_id) AS total_count
		FROM attendance a
		JOIN employees e
		  ON e.company_id = a.company_id
		 AND a.employee_id = e.emp_id
		"""
		+ """
		WHERE a.company_id = %s
		  AND a.date = %s
		  AND a.check_in_time IS NOT NULL
		"""
	)
	count_params = [company_id, selected_date]
	if meal_filter == "yes":
		count_query += " AND a.meal_status = 'YES'"
	elif meal_filter == "no":
		count_query += " AND COALESCE(a.meal_status, 'NO') = 'NO'"
	if search_query:
		count_query += " AND (e.name LIKE %s OR e.emp_id LIKE %s)"
		count_params.extend([f"%{search_query}%", f"%{search_query}%"])

	cursor.execute(count_query, count_params)
	total_count = int((cursor.fetchone() or {}).get("total_count") or 0)
	current_app.logger.info(
		"Canteen reports count query returned %s rows for company_id=%s date=%s meal_filter=%s search=%s",
		total_count,
		company_id,
		selected_date,
		meal_filter,
		search_query,
	)

	query = (
		"""
		SELECT
			e.name,
			e.emp_id,
			e.department,
			COALESCE(a.meal_status, 'NO') AS meal_status,
			COALESCE(a.meal_confirmed, 'NO') AS meal_confirmed,
			CASE WHEN COALESCE(a.face_verified, 0) = 1 THEN 'YES' ELSE 'NO' END AS face_verified,
			a.check_in_time
		FROM attendance a
		JOIN employees e
		  ON e.company_id = a.company_id
		 AND a.employee_id = e.emp_id
		WHERE a.company_id = %s
		  AND a.date = %s
		  AND a.check_in_time IS NOT NULL
		  AND a.id = (
		      SELECT id FROM attendance a2
		      WHERE a2.employee_id = a.employee_id
		        AND a2.company_id = a.company_id
		        AND a2.date = a.date
		      ORDER BY a2.check_in_time DESC
		      LIMIT 1
		  )
		"""
	)
	params = [company_id, selected_date]
	if meal_filter == "yes":
		query += " AND a.meal_status = 'YES'"
	elif meal_filter == "no":
		query += " AND COALESCE(a.meal_status, 'NO') = 'NO'"
	if search_query:
		query += " AND (e.name LIKE %s OR e.emp_id LIKE %s)"
		params.extend([f"%{search_query}%", f"%{search_query}%"])
	query += " ORDER BY a.check_in_time DESC, e.name ASC"

	cursor.execute(query, params)
	reports = cursor.fetchall()
	current_app.logger.info(
		"Canteen reports query returned rows: %s",
		len(reports),
	)
	for row in reports[:10]:
		current_app.logger.info("Canteen report row: %s", row)
	cursor.close()
	connection.close()

	for row in reports:
		row["meal_status_label"] = "YES" if (row.get("meal_status") or "").strip().upper() == "YES" else "NO"
		row["meal_taken_label"] = "YES" if (row.get("meal_taken") or "").strip().upper() == "YES" else "NO"
		row["meal_confirmed_label"] = "YES" if (row.get("meal_confirmed") or "").strip().upper() == "YES" else "NO"
		row["face_verified_label"] = "YES" if (row.get("face_verified") or "").strip().upper() == "YES" else "NO"

	return render_template(
		"canteen/canteen_reports.html",
		reports=reports,
		total_count=total_count,
		selected_date=selected_date,
		meal_filter=meal_filter,
		search_query=search_query,
	)


@auth.route("/logout")
def logout():
	previous_role = session.get("role")
	session.clear()

	if previous_role == "admin":
		flash("You have been logged out.", "logout")
		return redirect(url_for("auth.role_login", role="admin"))

	flash("You have been logged out.", "success")
	return redirect(url_for("auth.landing_page"))