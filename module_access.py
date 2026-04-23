from functools import wraps

from flask import flash, jsonify, redirect, request, session, url_for

from database.db_connection import get_db_connection


MODULE_COLUMN_MAP = {
	"attendance": "attendance_module_enabled",
	"attendance_management": "attendance_module_enabled",
	"canteen": "canteen_module_enabled",
	"canteen_management": "canteen_module_enabled",
	"salary_slip": "salary_slip_module_enabled",
	"salary_slip_management": "salary_slip_module_enabled",
}

SUBMODULE_COLUMN_MAP = {
	"attendance": {
		"qr_generation": "attendance_qr_generation_enabled",
		"qr_scanner": "attendance_qr_scanner_enabled",
	},
	"canteen_management": {
		"qr_generate": "canteen_qr_generate_enabled",
		"qr_scan": "canteen_qr_scan_enabled",
		"face_verify": "canteen_face_verify_enabled",
		"reports": "canteen_reports_enabled",
	},
}


def _default_module_flags():
	return {
		"attendance": False,
		"canteen_management": False,
		"salary_slip_management": False,
	}


def _default_submodule_flags():
	return {
		"attendance": {
			"qr_generation": False,
			"qr_scanner": False,
		},
		"canteen_management": {
			"qr_generate": False,
			"qr_scan": False,
			"face_verify": False,
			"reports": False,
		},
	}


def _normalize_module_name(module_name):
	key = str(module_name or "").strip().lower().replace(" ", "_")
	if key == "canteen":
		return "canteen_management"
	if key == "salary_slip":
		return "salary_slip_management"
	if key == "attendance_management":
		return "attendance"
	return key


def _normalize_submodule_name(submodule_name):
	key = str(submodule_name or "").strip().lower().replace(" ", "_")
	# attendance submodule aliases
	if key in {"qr_code_generation", "qrcode_generation", "attendance_qr_generation"}:
		return "qr_generation"
	if key in {"attendance_qr_scanner", "attendance_scanner"}:
		return "qr_scanner"
	# canteen submodule aliases
	if key in {"meal_qr_generation", "canteen_qr_generate"}:
		return "qr_generate"
	if key in {"meal_qr_scanner", "canteen_qr_scan", "meal_qr_scan", "qr_scan"}:
		return "qr_scan"
	if key in {"face_verification", "canteen_face_verify", "face_verify"}:
		return "face_verify"
	if key in {"meal_reports", "canteen_reports"}:
		return "reports"
	return key


def get_company_module_flags(company_id, connection=None):
	flags = _default_module_flags()
	if not company_id:
		return flags

	own_connection = connection is None
	if own_connection:
		connection = get_db_connection()

	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""
		SELECT *
		FROM companies
		WHERE id = %s
		""",
		(company_id,),
	)
	company = cursor.fetchone() or {}
	cursor.close()

	if own_connection:
		connection.close()

	flags["attendance"] = bool(company.get("attendance_module_enabled"))
	flags["canteen_management"] = bool(company.get("canteen_module_enabled"))
	flags["salary_slip_management"] = bool(company.get("salary_slip_module_enabled"))
	return flags


def get_company_submodule_flags(company_id, connection=None):
	flags = _default_submodule_flags()
	if not company_id:
		return flags

	own_connection = connection is None
	if own_connection:
		connection = get_db_connection()

	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""
		SELECT *
		FROM companies
		WHERE id = %s
		""",
		(company_id,),
	)
	company = cursor.fetchone() or {}
	cursor.close()

	if own_connection:
		connection.close()

	attendance_enabled = bool(company.get("attendance_module_enabled"))
	flags["attendance"]["qr_generation"] = attendance_enabled and bool(company.get("attendance_qr_generation_enabled", 1))
	flags["attendance"]["qr_scanner"] = attendance_enabled and bool(company.get("attendance_qr_scanner_enabled", 1))

	canteen_enabled = bool(company.get("canteen_module_enabled"))
	flags["canteen_management"]["qr_generate"] = canteen_enabled and bool(company.get("canteen_qr_generate_enabled") if company.get("canteen_qr_generate_enabled") is not None else 1)
	flags["canteen_management"]["qr_scan"] = canteen_enabled and bool(company.get("canteen_qr_scan_enabled") if company.get("canteen_qr_scan_enabled") is not None else 1)
	flags["canteen_management"]["face_verify"] = canteen_enabled and bool(company.get("canteen_face_verify_enabled") if company.get("canteen_face_verify_enabled") is not None else 1)
	flags["canteen_management"]["reports"] = canteen_enabled and bool(company.get("canteen_reports_enabled") if company.get("canteen_reports_enabled") is not None else 1)
	return flags


def has_module(company_id, module_name, connection=None):
	normalized_module = _normalize_module_name(module_name)
	flags = get_company_module_flags(company_id, connection=connection)
	if normalized_module in flags:
		return bool(flags[normalized_module])

	column_name = MODULE_COLUMN_MAP.get(normalized_module)
	if not column_name:
		return False

	if column_name == "attendance_module_enabled":
		return bool(flags["attendance"])
	if column_name == "canteen_module_enabled":
		return bool(flags["canteen_management"])
	if column_name == "salary_slip_module_enabled":
		return bool(flags["salary_slip_management"])
	return False


def has_submodule(company_id, module_name, submodule_name, connection=None):
	normalized_module = _normalize_module_name(module_name)
	normalized_submodule = _normalize_submodule_name(submodule_name)

	module_flags = get_company_module_flags(company_id, connection=connection)
	if not module_flags.get(normalized_module, False):
		return False

	module_submodules = SUBMODULE_COLUMN_MAP.get(normalized_module, {})
	if normalized_submodule not in module_submodules:
		return False

	submodule_flags = get_company_submodule_flags(company_id, connection=connection)
	return bool(submodule_flags.get(normalized_module, {}).get(normalized_submodule, False))


def update_module_flags_in_session(company_id):
	flags = get_company_module_flags(company_id)
	submodule_flags = get_company_submodule_flags(company_id)
	session["company_modules"] = flags
	session["company_submodules"] = submodule_flags
	session["attendance_module_enabled"] = flags["attendance"]
	session["attendance_qr_generation_enabled"] = submodule_flags["attendance"]["qr_generation"]
	session["attendance_qr_scanner_enabled"] = submodule_flags["attendance"]["qr_scanner"]
	session["canteen_module_enabled"] = flags["canteen_management"]
	session["canteen_qr_generate_enabled"] = submodule_flags["canteen_management"]["qr_generate"]
	session["canteen_qr_scan_enabled"] = submodule_flags["canteen_management"]["qr_scan"]
	session["canteen_face_verify_enabled"] = submodule_flags["canteen_management"]["face_verify"]
	session["canteen_reports_enabled"] = submodule_flags["canteen_management"]["reports"]
	session["salary_slip_module_enabled"] = flags["salary_slip_management"]
	return flags


def module_required(module_name, json_response=False):
	def decorator(function):
		@wraps(function)
		def wrapper(*args, **kwargs):
			company_id = session.get("company_id")

			if not company_id:
				company_id = kwargs.get("company_id")

			if not company_id:
				company_id = request.args.get("company_id", type=int)

			if not company_id:
				payload = request.get_json(silent=True) or {}
				company_id = payload.get("company_id")

			if not company_id:
				company_id = request.form.get("company_id")

			if not company_id:
				if json_response:
					return jsonify({"success": False, "message": "Company context is missing"}), 400
				flash("Company context is missing.", "error")
				return redirect(url_for("auth.redirect_dashboard"))

			if has_module(company_id, module_name):
				return function(*args, **kwargs)

			message = f"{str(module_name).replace('_', ' ').title()} module is disabled for this company."
			if json_response:
				return jsonify({"success": False, "message": message}), 403

			flash(message, "error")
			current_role = session.get("role")
			if current_role == "company":
				return redirect(url_for("company.company_dashboard"))
			if current_role == "canteen":
				return redirect(url_for("auth.canteen_dashboard"))
			return redirect(url_for("auth.landing_page"))

		return wrapper

	return decorator
