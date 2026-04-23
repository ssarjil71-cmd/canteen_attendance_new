import base64
import io
import os
from datetime import date
import json

import boto3
import qrcode
from botocore.exceptions import BotoCoreError, ClientError
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from database.db_connection import get_db_connection
from module_access import has_module, has_submodule

meal_confirmation = Blueprint("meal_confirmation", __name__)


def _has_column(connection, table_name, column_name):
	cursor = connection.cursor()
	cursor.execute(f"SHOW COLUMNS FROM `{table_name}` LIKE %s", (column_name,))
	has_column = cursor.fetchone() is not None
	cursor.close()
	return has_column


def _table_exists(connection, table_name):
	cursor = connection.cursor()
	cursor.execute("SHOW TABLES LIKE %s", (table_name,))
	exists = cursor.fetchone() is not None
	cursor.close()
	return exists


def _ensure_column(connection, table_name, column_name, alter_sql):
	if _has_column(connection, table_name, column_name):
		return
	cursor = connection.cursor()
	cursor.execute(alter_sql)
	cursor.close()
	connection.commit()


def _ensure_meal_confirmation_schema(connection):
	_ensure_column(connection, "attendance", "meal_status", "ALTER TABLE attendance ADD COLUMN meal_status ENUM('YES', 'NO') DEFAULT 'NO' AFTER check_out_time")
	_ensure_column(connection, "attendance", "meal_taken", "ALTER TABLE attendance ADD COLUMN meal_taken ENUM('YES', 'NO') DEFAULT 'NO' AFTER meal_status")
	_ensure_column(connection, "attendance", "meal_confirmed", "ALTER TABLE attendance ADD COLUMN meal_confirmed ENUM('YES', 'NO') DEFAULT 'NO' AFTER meal_taken")
	_ensure_column(connection, "attendance", "face_verified", "ALTER TABLE attendance ADD COLUMN face_verified TINYINT(1) DEFAULT 0 AFTER meal_confirmed")

	if _table_exists(connection, "canteen_reports"):
		_ensure_column(connection, "canteen_reports", "face_verified", "ALTER TABLE canteen_reports ADD COLUMN face_verified VARCHAR(10) DEFAULT 'NO'")


def _ensure_meal_qr_tokens_schema(connection):
	cursor = connection.cursor()
	cursor.execute(
		"""
		CREATE TABLE IF NOT EXISTS meal_qr_tokens (
			id INT AUTO_INCREMENT PRIMARY KEY,
			attendance_id INT NOT NULL,
			employee_id VARCHAR(100) NOT NULL,
			company_id INT NOT NULL,
			qr_date DATE NOT NULL,
			token VARCHAR(128) NOT NULL,
			payload TEXT NOT NULL,
			issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			expires_at DATETIME NOT NULL,
			consumed_at DATETIME NULL,
			is_active TINYINT(1) DEFAULT 1,
			UNIQUE KEY uk_meal_qr_attendance (attendance_id),
			UNIQUE KEY uk_meal_qr_token (token),
			INDEX idx_meal_qr_company_date (company_id, qr_date),
			INDEX idx_meal_qr_employee_date (employee_id, qr_date),
			CONSTRAINT fk_meal_qr_attendance FOREIGN KEY (attendance_id)
			  REFERENCES attendance(id) ON DELETE CASCADE,
			CONSTRAINT fk_meal_qr_company FOREIGN KEY (company_id)
			  REFERENCES companies(id) ON DELETE CASCADE
		)
		"""
	)
	cursor.close()
	connection.commit()


def _parse_qr_payload(qr_data):
	if not qr_data:
		return None

	qr_data = str(qr_data).strip()
	if not qr_data:
		return None

	try:
		parsed = json.loads(qr_data)
		if isinstance(parsed, dict):
			return parsed
	except Exception:
		pass

	parts = qr_data.split("_")
	if len(parts) >= 4:
		return {
			"employee_id": parts[0],
			"company_id": parts[1],
			"date_time": parts[2],
			"token": parts[3],
		}

	return None


def _get_dashboard_company_id(scan_mode):
	if scan_mode:
		return request.args.get("company_id", type=int)

	company_id = session.get("company_id")
	if company_id:
		return company_id

	return request.args.get("company_id", type=int)


def _build_qr_base64(scan_url):
	buffer = io.BytesIO()
	qr = qrcode.QRCode(version=1, box_size=10, border=4)
	qr.add_data(scan_url)
	qr.make(fit=True)
	img = qr.make_image(fill_color="black", back_color="white")
	img.save(buffer, format="PNG")
	return base64.b64encode(buffer.getvalue()).decode("ascii")


def _decode_data_url(image_data):
	if not image_data:
		return None
	if "," in image_data:
		image_data = image_data.split(",", 1)[1]
	try:
		return base64.b64decode(image_data)
	except Exception:
		return None


def _verify_with_rekognition(stored_image_path, captured_image_bytes, similarity_threshold=0.0):
	try:
		with open(stored_image_path, "rb") as source_file:
			source_bytes = source_file.read()

		client = boto3.client("rekognition", region_name=os.getenv("AWS_REGION", "us-east-1"))
		response = client.compare_faces(
			SourceImage={"Bytes": source_bytes},
			TargetImage={"Bytes": captured_image_bytes},
			SimilarityThreshold=float(similarity_threshold),
		)
		matches = response.get("FaceMatches", [])
		if not matches:
			return False, 0.0, None

		best_match = max(matches, key=lambda item: item.get("Similarity", 0.0))
		similarity = float(best_match.get("Similarity", 0.0))
		return True, round(similarity, 2), None
	except (BotoCoreError, ClientError, OSError) as exc:
		current_app.logger.warning("Rekognition verification failed: %s", exc)
		return None, 0.0, str(exc)


def _identify_employee_by_face(company_id, captured_image_bytes):
	connection = get_db_connection()
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""
		SELECT DISTINCT e.emp_id, e.name, e.image_path
		FROM employees e
		JOIN attendance a
		  ON a.company_id = e.company_id
		 AND a.employee_id = e.emp_id
		WHERE e.company_id = %s
		  AND e.image_path IS NOT NULL
		  AND TRIM(e.image_path) <> ''
		  AND DATE(COALESCE(a.check_in_time, a.date)) = CURDATE()
		  AND COALESCE(a.meal_status, 'NO') = 'YES'
		""",
		(company_id,),
	)
	employees = cursor.fetchall()
	cursor.close()
	connection.close()

	if not employees:
		return None, 0.0, "No eligible employees found for meal confirmation today"

	best_employee = None
	best_similarity = 0.0
	last_error = None

	for employee in employees:
		stored_relative_path = (employee.get("image_path") or "").strip().replace("\\", "/")
		if not stored_relative_path:
			continue

		stored_image_path = os.path.join(current_app.root_path, "static", stored_relative_path)
		if not os.path.exists(stored_image_path):
			continue

		matched, similarity, error_message = _verify_with_rekognition(
			stored_image_path,
			captured_image_bytes,
			similarity_threshold=0.0,
		)
		if matched is None:
			last_error = error_message
			continue

		if similarity > best_similarity:
			best_similarity = similarity
			best_employee = {
				"emp_id": employee.get("emp_id"),
				"name": employee.get("name"),
			}

	if best_employee is None and last_error:
		return None, 0.0, last_error

	return best_employee, round(best_similarity, 2), None


def _update_optional_canteen_reports(connection, company_id, employee_id, matched):
	if not _table_exists(connection, "canteen_reports"):
		return

	if not _has_column(connection, "canteen_reports", "face_verified"):
		return

	has_company_id = _has_column(connection, "canteen_reports", "company_id")
	has_employee_id = _has_column(connection, "canteen_reports", "employee_id")
	has_report_date = _has_column(connection, "canteen_reports", "report_date")
	has_date = _has_column(connection, "canteen_reports", "date")
	has_meal_confirmed = _has_column(connection, "canteen_reports", "meal_confirmed")

	if not (has_company_id and has_employee_id):
		return

	set_parts = ["face_verified = %s"]
	params = ["YES" if matched else "NO"]
	if matched and has_meal_confirmed:
		set_parts.append("meal_confirmed = 'YES'")

	query = "UPDATE canteen_reports SET " + ", ".join(set_parts) + " WHERE company_id = %s AND employee_id = %s"
	params.extend([company_id, employee_id])
	if has_report_date:
		query += " AND DATE(report_date) = CURDATE()"
	elif has_date:
		query += " AND DATE(date) = CURDATE()"

	cursor = connection.cursor()
	cursor.execute(query, params)
	cursor.close()


@meal_confirmation.route("/meal-confirmation/dashboard")
def dashboard():
	scan_mode = (request.args.get("scan") or "").lower()
	is_scan_mode = scan_mode == "true"
	role = session.get("role")

	if not is_scan_mode and role not in {"company", "canteen"}:
		flash("Please login to access confirmation dashboard.", "error")
		return redirect(url_for("auth.landing_page"))

	company_id = _get_dashboard_company_id(is_scan_mode)
	if not company_id:
		flash("Company id is required for scan.", "error")
		return redirect(url_for("auth.landing_page"))

	if not has_module(company_id, "canteen_management"):
		if is_scan_mode:
			return render_template("attendance/error.html", message="Canteen Management module is disabled for this company."), 403
		flash("Canteen Management module is disabled for this company.", "error")
		if role == "company":
			return redirect(url_for("company.company_dashboard"))
		if role == "canteen":
			return redirect(url_for("auth.canteen_dashboard"))
		return redirect(url_for("auth.landing_page"))

	qr_scanner_enabled = has_submodule(company_id, "canteen_management", "qr_scan")
	qr_generate_enabled = has_submodule(company_id, "canteen_management", "qr_generate")
	face_verify_enabled = has_submodule(company_id, "canteen_management", "face_verify")
	reports_enabled = has_submodule(company_id, "canteen_management", "reports")

	if is_scan_mode and not qr_scanner_enabled:
		return render_template("attendance/error.html", message="Meal QR Scanner is disabled for this company."), 403

	today = date.today()
	connection = get_db_connection()
	_ensure_meal_confirmation_schema(connection)

	stats = {}
	records = []

	if not is_scan_mode:
		cursor = connection.cursor(dictionary=True)
		cursor.execute(
			"""
			SELECT
				COUNT(*) AS total_records,
				SUM(CASE WHEN COALESCE(meal_status, 'NO') = 'YES' THEN 1 ELSE 0 END) AS meal_requested,
				SUM(CASE WHEN COALESCE(meal_taken, 'NO') = 'YES' THEN 1 ELSE 0 END) AS meal_taken_count,
				SUM(CASE WHEN COALESCE(meal_confirmed, 'NO') = 'YES' THEN 1 ELSE 0 END) AS meal_confirmed_count,
				SUM(CASE WHEN COALESCE(face_verified, 0) = 1 THEN 1 ELSE 0 END) AS face_verified_count
			FROM attendance
			WHERE company_id = %s
			  AND DATE(COALESCE(check_in_time, date)) = %s
			""",
			(company_id, today),
		)
		stats = cursor.fetchone() or {}

		cursor.execute(
			"""
			SELECT
				a.employee_id,
				e.name,
				e.department,
				COALESCE(a.meal_status, 'NO') AS meal_status,
				COALESCE(a.meal_taken, 'NO') AS meal_taken,
				COALESCE(a.meal_confirmed, 'NO') AS meal_confirmed,
				CASE WHEN COALESCE(a.face_verified, 0) = 1 THEN 'YES' ELSE 'NO' END AS face_verified,
				a.check_in_time
			FROM attendance a
			JOIN employees e
			  ON e.company_id = a.company_id
			 AND e.emp_id = a.employee_id
			WHERE a.company_id = %s
			  AND DATE(COALESCE(a.check_in_time, a.date)) = %s
			ORDER BY a.check_in_time DESC
			LIMIT 50
			""",
			(company_id, today),
		)
		records = cursor.fetchall()
		cursor.close()
	connection.close()

	for record in records:
		record["meal_status_label"] = "YES" if (record.get("meal_status") or "").strip().upper() == "YES" else "NO"
		record["meal_taken_label"] = "YES" if (record.get("meal_taken") or "").strip().upper() == "YES" else "NO"
		record["meal_confirmed_label"] = "YES" if (record.get("meal_confirmed") or "").strip().upper() == "YES" else "NO"
		record["face_verified_label"] = "YES" if (record.get("face_verified") or "").strip().upper() == "YES" else "NO"

	scan_url = url_for("meal_confirmation.dashboard", scan="true", company_id=company_id, _external=True)
	qr_image_b64 = _build_qr_base64(scan_url) if not is_scan_mode else None

	return render_template(
		"meal_confirmation/dashboard.html",
		layout_template="base_minimal.html" if is_scan_mode else "base.html",
		today=today,
		stats=stats,
		records=records,
		scan_mode=scan_mode,
		is_scan_mode=is_scan_mode,
		company_id=company_id,
		scan_url=scan_url,
		qr_image_b64=qr_image_b64,
		qr_scanner_enabled=qr_scanner_enabled,
		qr_generate_enabled=qr_generate_enabled,
		face_verify_enabled=face_verify_enabled,
		reports_enabled=reports_enabled,
	)


@meal_confirmation.route("/verify-face", methods=["POST"])
def verify_face():
	data = request.get_json(silent=True) or {}
	company_id = data.get("company_id")
	captured_image_data = data.get("captured_image")

	if not company_id or not captured_image_data:
		return jsonify({"success": False, "message": "company_id and captured_image are required"}), 400

	if not has_module(company_id, "canteen_management"):
		return jsonify({"success": False, "message": "Canteen Management module is disabled for this company."}), 403

	if not has_submodule(company_id, "canteen_management", "face_verify"):
		return jsonify({"success": False, "message": "Face Verification is disabled for this company."}), 403

	captured_image_bytes = _decode_data_url(captured_image_data)
	if not captured_image_bytes:
		return jsonify({"success": False, "message": "Invalid captured image payload"}), 400

	connection = get_db_connection()
	_ensure_meal_confirmation_schema(connection)

	employee, similarity, error_message = _identify_employee_by_face(company_id, captured_image_bytes)
	if error_message:
		connection.close()
		return jsonify({"success": False, "message": f"Face verification unavailable: {error_message}"}), 500

	if not employee:
		connection.close()
		return jsonify({"success": False, "message": "No matching employee found"}), 404

	employee_id = employee.get("emp_id")
	confidence = float(similarity)
	matched = confidence >= 90.0

	cursor = connection.cursor()
	if matched:
		cursor.execute(
			"""
			UPDATE attendance
			SET meal_confirmed = 'YES',
				face_verified = 1,
				updated_at = CURRENT_TIMESTAMP
			WHERE company_id = %s
			  AND employee_id = %s
			  AND DATE(COALESCE(check_in_time, date)) = CURDATE()
			""",
			(company_id, employee_id),
		)
	else:
		cursor.execute(
			"""
			UPDATE attendance
			SET face_verified = 0,
				updated_at = CURRENT_TIMESTAMP
			WHERE company_id = %s
			  AND employee_id = %s
			  AND DATE(COALESCE(check_in_time, date)) = CURDATE()
			""",
			(company_id, employee_id),
		)

	_update_optional_canteen_reports(connection, company_id, employee_id, matched)
	connection.commit()

	cursor.close()
	connection.close()

	return jsonify(
		{
			"success": True,
			"matched": bool(matched),
			"employee_id": employee_id,
			"employee_name": employee.get("name"),
			"meal_confirmed": "YES" if matched else "NO",
			"face_verified": "YES" if matched else "NO",
			"confidence": confidence,
			"message": "Meal confirmed successfully" if matched else "Face identified but similarity is below threshold",
		}
	)


@meal_confirmation.route("/scan-meal", methods=["POST"])
def scan_meal():
	data = request.get_json(silent=True) or {}
	qr_data = data.get("qr_data")
	request_company_id = data.get("company_id")

	if request_company_id and not has_module(request_company_id, "canteen_management"):
		return jsonify({"success": False, "status": "error", "message": "Canteen Management module is disabled for this company."}), 403

	if request_company_id and not has_submodule(request_company_id, "canteen_management", "qr_scan"):
		return jsonify({"success": False, "status": "error", "message": "Meal QR Scanner is disabled for this company."}), 403

	payload = _parse_qr_payload(qr_data)
	if not payload:
		return jsonify({"success": False, "status": "error", "message": "Invalid QR payload"}), 400

	token = (payload.get("token") or "").strip()
	if not token:
		return jsonify({"success": False, "status": "error", "message": "Invalid QR token"}), 400

	today = date.today()
	connection = get_db_connection()
	_ensure_meal_confirmation_schema(connection)
	_ensure_meal_qr_tokens_schema(connection)
	cursor = connection.cursor(dictionary=True)

	cursor.execute(
		"""
		SELECT
			t.id,
			t.attendance_id,
			t.employee_id,
			t.company_id,
			t.qr_date,
			t.expires_at,
			t.consumed_at,
			t.is_active,
			COALESCE(a.meal_status, 'NO') AS meal_status,
			COALESCE(a.meal_taken, 'NO') AS meal_taken,
			COALESCE(a.meal_confirmed, 'NO') AS meal_confirmed
		FROM meal_qr_tokens t
		JOIN attendance a ON a.id = t.attendance_id
		WHERE t.token = %s
		LIMIT 1
		""",
		(token,),
	)
	record = cursor.fetchone()

	if not record:
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Invalid QR"}), 404

	payload_employee_id = (payload.get("employee_id") or "").strip()
	payload_company_id = payload.get("company_id")
	if payload_employee_id and payload_employee_id != str(record["employee_id"]):
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Invalid QR"}), 400

	if payload_company_id is not None and str(payload_company_id) != str(record["company_id"]):
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Invalid QR"}), 400

	if request_company_id is not None and str(request_company_id) != str(record["company_id"]):
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "QR does not belong to this company"}), 403

	if not has_module(record["company_id"], "canteen_management"):
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Canteen Management module is disabled for this company."}), 403

	if not has_submodule(record["company_id"], "canteen_management", "qr_scan"):
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Meal QR Scanner is disabled for this company."}), 403

	if record.get("consumed_at") is not None or int(record.get("is_active") or 0) == 0:
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Already Used"}), 409

	if (record.get("meal_taken") or "NO").strip().upper() == "YES" or (record.get("meal_confirmed") or "NO").strip().upper() == "YES":
		cursor.execute(
			"""
			UPDATE meal_qr_tokens
			SET consumed_at = COALESCE(consumed_at, CURRENT_TIMESTAMP),
				is_active = 0
			WHERE id = %s
			""",
			(record["id"],),
		)
		connection.commit()
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Already Used"}), 409

	if record.get("qr_date") != today:
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "QR expired for today"}), 400

	expires_at = record.get("expires_at")
	if expires_at is not None and expires_at.date() < today:
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "QR expired for today"}), 400

	if (record.get("meal_status") or "NO").strip().upper() != "YES":
		cursor.close()
		connection.close()
		return jsonify({"success": False, "status": "error", "message": "Meal not selected for this employee"}), 400

	cursor.execute(
		"""
		UPDATE attendance
		SET meal_taken = 'YES',
			meal_confirmed = 'YES',
			updated_at = CURRENT_TIMESTAMP
		WHERE id = %s
		""",
		(record["attendance_id"],),
	)

	cursor.execute(
		"""
		UPDATE meal_qr_tokens
		SET consumed_at = CURRENT_TIMESTAMP,
			is_active = 0
		WHERE id = %s
		""",
		(record["id"],),
	)

	connection.commit()
	cursor.close()
	connection.close()

	return jsonify(
		{
			"success": True,
			"status": "success",
			"employee_id": record.get("employee_id"),
			"company_id": record.get("company_id"),
			"meal_taken": "YES",
			"meal_confirmed": "YES",
			"message": "Meal Confirmed",
		}
	)


@meal_confirmation.route("/meal-scanner")
def meal_scanner():
	role = session.get("role")
	if role not in {"company", "canteen"}:
		flash("Please login to access meal scanner.", "error")
		return redirect(url_for("auth.landing_page"))

	company_id = session.get("company_id") or request.args.get("company_id", type=int)
	if not company_id:
		flash("Company id is required for meal scanner.", "error")
		return redirect(url_for("meal_confirmation.dashboard"))

	if not has_module(company_id, "canteen_management"):
		flash("Canteen Management module is disabled for this company.", "error")
		if role == "company":
			return redirect(url_for("company.company_dashboard"))
		return redirect(url_for("auth.canteen_dashboard"))

	if not has_submodule(company_id, "canteen_management", "qr_scan"):
		flash("Meal QR Scanner is disabled for this company.", "error")
		if role == "company":
			return redirect(url_for("meal_confirmation.dashboard", company_id=company_id))
		return redirect(url_for("auth.canteen_dashboard"))

	return render_template(
		"meal_confirmation/meal_scanner.html",
		company_id=company_id,
		dashboard_url=url_for("meal_confirmation.dashboard", company_id=company_id),
	)