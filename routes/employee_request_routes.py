from datetime import date
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from database.db_connection import get_db_connection

employee_request_bp = Blueprint("employee_request", __name__)


def _company_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "company":
            flash("Company access required.", "error")
            return redirect(url_for("auth.role_login", role="company"))
        return f(*args, **kwargs)
    return wrapper


def _ensure_employee_requests_table(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employee_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            company_id INT NOT NULL,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(150) NULL,
            phone VARCHAR(20) NULL,
            emp_id VARCHAR(100) NOT NULL,
            gender ENUM('Male', 'Female', 'Other') NULL,
            dob DATE NULL,
            address TEXT NULL,
            status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP NULL,
            CONSTRAINT fk_emp_req_company FOREIGN KEY (company_id)
              REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )
    for col, defn in [
        ("submitted_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("reviewed_at", "TIMESTAMP NULL"),
        ("email", "VARCHAR(150) NULL"),
        ("phone", "VARCHAR(20) NULL"),
        ("gender", "ENUM('Male','Female','Other') NULL"),
        ("dob", "DATE NULL"),
        ("address", "TEXT NULL"),
    ]:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'employee_requests' AND COLUMN_NAME = %s",
            (col,),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(f"ALTER TABLE employee_requests ADD COLUMN {col} {defn}")
    connection.commit()
    cursor.close()


@employee_request_bp.route("/company/employee-requests", methods=["GET"])
@_company_required
def view_requests():
    company_id = session.get("company_id")
    connection = get_db_connection()
    _ensure_employee_requests_table(connection)
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM employee_requests WHERE company_id = %s ORDER BY submitted_at DESC, id DESC",
        (company_id,),
    )
    requests_list = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template("company/employee_requests.html", requests=requests_list)


@employee_request_bp.route("/company/employee-requests/approve/<int:req_id>", methods=["POST"])
@_company_required
def approve_request(req_id):
    company_id = session.get("company_id")
    connection = get_db_connection()
    _ensure_employee_requests_table(connection)
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM employee_requests WHERE id = %s AND company_id = %s AND status = 'pending'",
        (req_id, company_id),
    )
    req = cursor.fetchone()
    if not req:
        flash("Request not found or already processed.", "error")
        cursor.close()
        connection.close()
        return redirect(url_for("employee_request.view_requests"))

    cursor.execute(
        """
        INSERT INTO employees
            (name, emp_id, email, phone, gender, dob, address, company_id,
             company, role, department, shift, joining_date, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '', 'General', 'General', 'General', %s, 'active')
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), email=VALUES(email), phone=VALUES(phone),
            gender=VALUES(gender), dob=VALUES(dob), address=VALUES(address),
            company_id=VALUES(company_id), status='active'
        """,
        (req["name"], req["emp_id"], req["email"], req["phone"],
         req["gender"], req["dob"], req["address"], company_id, date.today()),
    )
    cursor.execute(
        "UPDATE employee_requests SET status='approved', reviewed_at=NOW() WHERE id = %s",
        (req_id,),
    )
    connection.commit()
    cursor.close()
    connection.close()

    flash(f"Employee '{req['name']}' approved and added to the system.", "success")
    return redirect(url_for("employee_request.view_requests"))


@employee_request_bp.route("/company/employee-requests/reject/<int:req_id>", methods=["POST"])
@_company_required
def reject_request(req_id):
    company_id = session.get("company_id")
    connection = get_db_connection()
    _ensure_employee_requests_table(connection)
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT id, name FROM employee_requests WHERE id = %s AND company_id = %s AND status = 'pending'",
        (req_id, company_id),
    )
    req = cursor.fetchone()
    if not req:
        flash("Request not found or already processed.", "error")
        cursor.close()
        connection.close()
        return redirect(url_for("employee_request.view_requests"))

    cursor.execute(
        "UPDATE employee_requests SET status='rejected', reviewed_at=NOW() WHERE id = %s",
        (req_id,),
    )
    connection.commit()
    cursor.close()
    connection.close()

    flash(f"Request from '{req['name']}' has been rejected.", "info")
    return redirect(url_for("employee_request.view_requests"))
