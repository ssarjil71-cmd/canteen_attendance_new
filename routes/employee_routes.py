from flask import Blueprint, flash, redirect, url_for, render_template, request
from database.db_connection import get_db_connection

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")

@employee_bp.route("/self-register", methods=["GET", "POST"])
def employee_register():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM companies ORDER BY name")
    companies = cursor.fetchall()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        emp_id = request.form.get("emp_id", "").strip()
        email = request.form.get("email", "").strip()
        gender = request.form.get("gender", "").strip()
        dob = request.form.get("dob", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        role = request.form.get("role", "").strip()
        employee_role = request.form.get("employee_role", "").strip()
        department_id = request.form.get("department_id", "").strip()
        shift_id = request.form.get("shift_id", "").strip()
        joining_date = request.form.get("joining_date", "").strip()

        errors = []
        if not name:
            errors.append("Full Name is required.")
        if not emp_id:
            errors.append("Employee ID is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not employee_role:
            errors.append("Employee Role is required.")
        if not joining_date:
            errors.append("Joining date is required.")

        # Check for duplicate Employee ID
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id FROM employees WHERE emp_id = %s", (emp_id,))
        if cursor.fetchone():
            errors.append("An employee with this Employee ID already exists.")

        # Check for duplicate phone/email
        if phone:
            cursor.execute("SELECT id FROM employees WHERE phone = %s", (phone,))
            if cursor.fetchone():
                errors.append("An employee with this phone number already exists.")
        if email:
            cursor.execute("SELECT id FROM employees WHERE email = %s", (email,))
            if cursor.fetchone():
                errors.append("An employee with this email already exists.")

        if errors:
            for error in errors:
                flash(error, "error")
            cursor.close()
            connection.close()
            return render_template("employee/self_registration.html", companies=companies)

        # Insert new employee
        try:
            from datetime import datetime
            dob_obj = datetime.strptime(dob, '%Y-%m-%d').date() if dob else None
            joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date() if joining_date else None
        except ValueError:
            flash("Invalid date format.", "error")
            cursor.close()
            connection.close()
            return render_template("employee/self_registration.html", companies=companies)

        cursor.execute(
            """
            INSERT INTO employees (
                name, emp_id, email, gender, dob, phone, address, role, employee_role,
                department, shift, joining_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name, emp_id, email or None, gender, dob_obj, phone or None,
                address or None, role or 'General', employee_role,
                department_id or None, shift_id or None, joining_date_obj
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("Registration Successful!", "success")
        return redirect(url_for("employee.employee_register"))

    # GET request: render registration form
    cursor.close()
    connection.close()
    return render_template("employee/self_registration.html", companies=companies)
