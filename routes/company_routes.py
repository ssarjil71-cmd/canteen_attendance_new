from functools import wraps
from datetime import datetime, time

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from database.db_connection import get_db_connection

company = Blueprint("company", __name__, url_prefix="/company")


def company_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if session.get("role") != "company":
            flash("Company access required.", "error")
            return redirect(url_for("auth.role_login", role="company"))
        return function(*args, **kwargs)

    return wrapper


@company.route("/dashboard")
@company_required
def company_dashboard():
    return render_template("company/dashboard.html")


# Department Management Routes
@company.route("/add_department", methods=["GET", "POST"])
@company_required
def add_department():
    company_id = session.get("company_id")

    if request.method == "POST":
        department_name = request.form.get("department_name", "").strip()

        if not department_name:
            flash("Department name is required.", "error")
            return render_template("company/add_department.html")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check if department name already exists for this company
        cursor.execute(
            "SELECT id FROM departments WHERE name = %s AND company_id = %s", 
            (department_name, company_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            flash("A department with this name already exists.", "error")
            return render_template("company/add_department.html")

        # Insert new department
        cursor.execute(
            "INSERT INTO departments (name, company_id) VALUES (%s, %s)",
            (department_name, company_id)
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash("Department added successfully!", "success")
        return redirect(url_for("company.view_departments"))

    return render_template("company/add_department.html")


@company.route("/departments")
@company_required
def view_departments():
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, name, created_at
        FROM departments
        WHERE company_id = %s
        ORDER BY name ASC
        """,
        (company_id,),
    )
    departments = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template("company/view_departments.html", departments=departments)


@company.route("/delete_department/<int:department_id>", methods=["POST"])
@company_required
def delete_department(department_id):
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Verify department belongs to this company before deleting
    cursor.execute(
        "DELETE FROM departments WHERE id = %s AND company_id = %s",
        (department_id, company_id)
    )
    
    if cursor.rowcount > 0:
        flash("Department deleted successfully!", "success")
    else:
        flash("Department not found or access denied.", "error")
    
    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("company.view_departments"))


# Shift Management Routes
@company.route("/add_shift", methods=["GET", "POST"])
@company_required
def add_shift():
    company_id = session.get("company_id")

    if request.method == "POST":
        shift_name = request.form.get("shift_name", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()

        errors = []
        if not shift_name:
            errors.append("Shift name is required.")
        if not start_time:
            errors.append("Start time is required.")
        if not end_time:
            errors.append("End time is required.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("company/add_shift.html")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check if shift name already exists for this company
        cursor.execute(
            "SELECT id FROM shifts WHERE name = %s AND company_id = %s", 
            (shift_name, company_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            flash("A shift with this name already exists.", "error")
            return render_template("company/add_shift.html")

        # Insert new shift
        cursor.execute(
            "INSERT INTO shifts (name, start_time, end_time, company_id) VALUES (%s, %s, %s, %s)",
            (shift_name, start_time, end_time, company_id)
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash("Shift added successfully!", "success")
        return redirect(url_for("company.view_shifts"))

    return render_template("company/add_shift.html")


@company.route("/shifts")
@company_required
def view_shifts():
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, name, start_time, end_time, created_at
        FROM shifts
        WHERE company_id = %s
        ORDER BY start_time ASC
        """,
        (company_id,),
    )
    shifts = cursor.fetchall()
    
    # Convert timedelta objects to time objects if needed
    for shift in shifts:
        if hasattr(shift['start_time'], 'total_seconds'):
            # It's a timedelta object, convert to time
            total_seconds = int(shift['start_time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            # Ensure hours and minutes are within valid ranges
            hours = max(0, min(23, hours))
            minutes = max(0, min(59, minutes))
            shift['start_time'] = time(hours, minutes)
            
        if hasattr(shift['end_time'], 'total_seconds'):
            # It's a timedelta object, convert to time
            total_seconds = int(shift['end_time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            # Ensure hours and minutes are within valid ranges
            hours = max(0, min(23, hours))
            minutes = max(0, min(59, minutes))
            shift['end_time'] = time(hours, minutes)
    
    cursor.close()
    connection.close()

    return render_template("company/view_shifts.html", shifts=shifts)


@company.route("/delete_shift/<int:shift_id>", methods=["POST"])
@company_required
def delete_shift(shift_id):
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Verify shift belongs to this company before deleting
    cursor.execute(
        "DELETE FROM shifts WHERE id = %s AND company_id = %s",
        (shift_id, company_id)
    )
    
    if cursor.rowcount > 0:
        flash("Shift deleted successfully!", "success")
    else:
        flash("Shift not found or access denied.", "error")
    
    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("company.view_shifts"))


@company.route("/edit_department/<int:department_id>", methods=["POST"])
@company_required
def edit_department(department_id):
    company_id = session.get("company_id")
    department_name = request.form.get("department_name", "").strip()

    if not department_name:
        flash("Department name is required.", "error")
        return redirect(url_for("company.view_departments"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Check if department name already exists for this company (excluding current department)
    cursor.execute(
        "SELECT id FROM departments WHERE name = %s AND company_id = %s AND id != %s", 
        (department_name, company_id, department_id)
    )
    if cursor.fetchone():
        cursor.close()
        connection.close()
        flash("A department with this name already exists.", "error")
        return redirect(url_for("company.view_departments"))

    # Update department
    cursor.execute(
        "UPDATE departments SET name = %s WHERE id = %s AND company_id = %s",
        (department_name, department_id, company_id)
    )
    
    if cursor.rowcount > 0:
        flash("Department updated successfully!", "success")
    else:
        flash("Department not found or access denied.", "error")
    
    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("company.view_departments"))


@company.route("/edit_shift/<int:shift_id>", methods=["POST"])
@company_required
def edit_shift(shift_id):
    company_id = session.get("company_id")
    shift_name = request.form.get("shift_name", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()

    errors = []
    if not shift_name:
        errors.append("Shift name is required.")
    if not start_time:
        errors.append("Start time is required.")
    if not end_time:
        errors.append("End time is required.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("company.view_shifts"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Check if shift name already exists for this company (excluding current shift)
    cursor.execute(
        "SELECT id FROM shifts WHERE name = %s AND company_id = %s AND id != %s", 
        (shift_name, company_id, shift_id)
    )
    if cursor.fetchone():
        cursor.close()
        connection.close()
        flash("A shift with this name already exists.", "error")
        return redirect(url_for("company.view_shifts"))

    # Update shift
    cursor.execute(
        "UPDATE shifts SET name = %s, start_time = %s, end_time = %s WHERE id = %s AND company_id = %s",
        (shift_name, start_time, end_time, shift_id, company_id)
    )
    
    if cursor.rowcount > 0:
        flash("Shift updated successfully!", "success")
    else:
        flash("Shift not found or access denied.", "error")
    
    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("company.view_shifts"))


@company.route("/add_employee", methods=["GET", "POST"])
@company_required
def add_employee():
    company_id = session.get("company_id")

    # Fetch departments, shifts, and roles for dropdowns
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("SELECT id, name FROM departments WHERE company_id = %s ORDER BY name", (company_id,))
    departments = cursor.fetchall()
    
    cursor.execute("SELECT id, name, start_time, end_time FROM shifts WHERE company_id = %s ORDER BY name", (company_id,))
    shifts = cursor.fetchall()
    
    # Convert timedelta objects to time objects if needed for shifts
    for shift in shifts:
        if hasattr(shift['start_time'], 'total_seconds'):
            total_seconds = int(shift['start_time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            hours = max(0, min(23, hours))
            minutes = max(0, min(59, minutes))
            shift['start_time'] = time(hours, minutes)
            
        if hasattr(shift['end_time'], 'total_seconds'):
            total_seconds = int(shift['end_time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            hours = max(0, min(23, hours))
            minutes = max(0, min(59, minutes))
            shift['end_time'] = time(hours, minutes)
    
    cursor.execute("SELECT id, name FROM roles WHERE company_id = %s ORDER BY name", (company_id,))
    roles = cursor.fetchall()
    
    cursor.close()
    connection.close()

    if request.method == "POST":
        # Basic Information
        name = request.form.get("name", "").strip()
        emp_id = request.form.get("emp_id", "").strip()
        email = request.form.get("email", "").strip()
        
        # Personal Details
        gender = request.form.get("gender", "").strip()
        dob = request.form.get("dob", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        
        # Work Details
        role = request.form.get("role", "").strip()
        employee_role = request.form.get("employee_role", "").strip()
        department_id = request.form.get("department_id", "").strip()
        shift_id = request.form.get("shift_id", "").strip()
        joining_date = request.form.get("joining_date", "").strip()

        # Validation
        errors = []
        
        if not name:
            errors.append("Employee name is required.")
        if not emp_id:
            errors.append("Employee ID is required.")
        if not gender:
            errors.append("Gender is required.")
        if not dob:
            errors.append("Date of birth is required.")
        if not employee_role:
            errors.append("Employee Role is required.")
        if not joining_date:
            errors.append("Joining date is required.")
            
        # Database validation
        if not errors:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            # Check employee ID uniqueness
            cursor.execute("SELECT id FROM employees WHERE emp_id = %s", (emp_id,))
            if cursor.fetchone():
                errors.append("An employee with this Employee ID already exists.")
                
            # Check email uniqueness if provided
            if email:
                cursor.execute("SELECT id FROM employees WHERE email = %s", (email,))
                if cursor.fetchone():
                    errors.append("An employee with this email already exists.")
                
            cursor.close()
            connection.close()

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("company/add_employee.html", departments=departments, shifts=shifts, roles=roles)

        # Get company name, department and shift names
        company_name = None
        department_name = None
        shift_name = None
        
        # Get company name from company_id
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT company_name FROM companies WHERE id = %s", (company_id,))
        company_result = cursor.fetchone()
        if company_result:
            company_name = company_result['company_name']
        cursor.close()
        connection.close()
        
        # Validate that we have a company name
        if not company_name:
            flash("Company information not found. Please contact administrator.", "error")
            return render_template("company/add_employee.html", departments=departments, shifts=shifts, roles=roles)
        
        if department_id:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT name FROM departments WHERE id = %s AND company_id = %s", (department_id, company_id))
            dept_result = cursor.fetchone()
            if dept_result:
                department_name = dept_result['name']
            cursor.close()
            connection.close()
            
        if shift_id:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT name FROM shifts WHERE id = %s AND company_id = %s", (shift_id, company_id))
            shift_result = cursor.fetchone()
            if shift_result:
                shift_name = shift_result['name']
            cursor.close()
            connection.close()

        # Convert dates to proper format
        try:
            dob_obj = datetime.strptime(dob, '%Y-%m-%d').date()
            joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "error")
            return render_template("company/add_employee.html", departments=departments, shifts=shifts, roles=roles)

        # Handle face image data
        face_image_filename = None
        face_image_data = request.form.get("face_image_data", "").strip()
        
        # Add face validation to errors list
        if not face_image_data:
            errors.append("Face capture is required for employee registration.")
        
        if face_image_data:
            try:
                import base64
                import os
                from flask import current_app
                
                # Create face images directory
                face_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'faces')
                os.makedirs(face_dir, exist_ok=True)
                
                # Remove data URL prefix
                if face_image_data.startswith('data:image'):
                    face_image_data = face_image_data.split(',')[1]
                
                # Decode base64 image
                image_data = base64.b64decode(face_image_data)
                
                # Generate filename
                import time
                timestamp = str(int(time.time()))
                face_image_filename = f"face_{emp_id}_{timestamp}.jpg"
                face_image_path = os.path.join(face_dir, face_image_filename)
                
                # Save image
                with open(face_image_path, 'wb') as f:
                    f.write(image_data)
                    
            except Exception as e:
                flash(f"Error processing face image: {str(e)}", "error")
                return render_template("company/add_employee.html", departments=departments, shifts=shifts, roles=roles)

        # Insert into database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            """
            INSERT INTO employees (
                name, emp_id, email, gender, dob, phone, address, role, employee_role,
                department, shift, joining_date, company, company_id, face_image
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name, emp_id, email or None, gender, dob_obj, phone or None, 
                address or None, role or 'General', employee_role, department_name or 'General', 
                shift_name or 'General', joining_date_obj, company_name, company_id, face_image_filename
            ),
        )
        
        connection.commit()
        cursor.close()
        connection.close()

        flash("Employee added successfully!", "success")
        return redirect(url_for("company.view_employees"))

    return render_template("company/add_employee.html", departments=departments, shifts=shifts, roles=roles)


@company.route("/employees")
@company_required
def view_employees():
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT e.id, e.name, e.emp_id, e.email, e.gender, e.role, e.employee_role, e.department, 
               e.shift, e.joining_date, e.phone, e.status, e.created_at
        FROM employees e
        WHERE e.company_id = %s
        ORDER BY e.name ASC, e.id ASC
        """,
        (company_id,),
    )
    employees = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template("company/view_employees.html", employees=employees)


@company.route("/delete_employee/<int:employee_id>", methods=["POST"])
@company_required
def delete_employee(employee_id):
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Verify employee belongs to this company before deleting
    cursor.execute(
        "DELETE FROM employees WHERE id = %s AND company_id = %s",
        (employee_id, company_id)
    )
    
    if cursor.rowcount > 0:
        flash("Employee deleted successfully!", "success")
    else:
        flash("Employee not found or access denied.", "error")
    
    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("company.view_employees"))


@company.route("/view_employee/<int:employee_id>")
@company_required
def view_employee(employee_id):
    """View individual employee details"""
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Get employee details
    cursor.execute(
        """
        SELECT e.id, e.name, e.emp_id, e.email, e.gender, e.dob, e.phone, e.address,
               e.role, e.employee_role, e.department, e.shift, e.joining_date, 
               e.status, e.created_at, e.company
        FROM employees e
        WHERE e.id = %s AND e.company_id = %s
        """,
        (employee_id, company_id)
    )
    employee = cursor.fetchone()
    cursor.close()
    connection.close()

    if not employee:
        flash("Employee not found.", "error")
        return redirect(url_for("company.view_employees"))

    return render_template("company/view_employee.html", employee=employee)


@company.route("/edit_employee/<int:employee_id>", methods=["GET", "POST"])
@company_required
def edit_employee(employee_id):
    """Edit individual employee details"""
    company_id = session.get("company_id")

    # Fetch departments, shifts, and roles for dropdowns
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("SELECT id, name FROM departments WHERE company_id = %s ORDER BY name", (company_id,))
    departments = cursor.fetchall()
    
    cursor.execute("SELECT id, name, start_time, end_time FROM shifts WHERE company_id = %s ORDER BY name", (company_id,))
    shifts = cursor.fetchall()
    
    # Convert timedelta objects to time objects if needed for shifts
    for shift in shifts:
        if hasattr(shift['start_time'], 'total_seconds'):
            total_seconds = int(shift['start_time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            hours = max(0, min(23, hours))
            minutes = max(0, min(59, minutes))
            shift['start_time'] = time(hours, minutes)
            
        if hasattr(shift['end_time'], 'total_seconds'):
            total_seconds = int(shift['end_time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            hours = max(0, min(23, hours))
            minutes = max(0, min(59, minutes))
            shift['end_time'] = time(hours, minutes)
    
    cursor.execute("SELECT id, name FROM roles WHERE company_id = %s ORDER BY name", (company_id,))
    roles = cursor.fetchall()
    
    # Get employee details
    cursor.execute(
        """
        SELECT e.id, e.name, e.emp_id, e.email, e.gender, e.dob, e.phone, e.address,
               e.role, e.employee_role, e.department, e.shift, e.joining_date, 
               e.status, e.created_at, e.company_id,
               d.id as department_id, s.id as shift_id
        FROM employees e
        LEFT JOIN departments d ON e.department = d.name AND d.company_id = %s
        LEFT JOIN shifts s ON e.shift = s.name AND s.company_id = %s
        WHERE e.id = %s AND e.company_id = %s
        """,
        (company_id, company_id, employee_id, company_id)
    )
    employee = cursor.fetchone()
    
    if not employee:
        flash("Employee not found.", "error")
        cursor.close()
        connection.close()
        return redirect(url_for("company.view_employees"))

    if request.method == "POST":
        # Basic Information
        name = request.form.get("name", "").strip()
        emp_id = request.form.get("emp_id", "").strip()
        email = request.form.get("email", "").strip()
        
        # Personal Details
        gender = request.form.get("gender", "").strip()
        dob = request.form.get("dob", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        
        # Work Details
        role = request.form.get("role", "").strip()
        employee_role = request.form.get("employee_role", "").strip()
        department_id = request.form.get("department_id", "").strip()
        shift_id = request.form.get("shift_id", "").strip()
        joining_date = request.form.get("joining_date", "").strip()

        # Validation
        errors = []
        
        if not name:
            errors.append("Employee name is required.")
        if not emp_id:
            errors.append("Employee ID is required.")
        if not gender:
            errors.append("Gender is required.")
        if not dob:
            errors.append("Date of birth is required.")
        if not employee_role:
            errors.append("Employee Role is required.")
        if not joining_date:
            errors.append("Joining date is required.")
            
        # Database validation
        if not errors:
            # Check employee ID uniqueness (excluding current employee)
            cursor.execute("SELECT id FROM employees WHERE emp_id = %s AND id != %s", (emp_id, employee_id))
            if cursor.fetchone():
                errors.append("An employee with this Employee ID already exists.")
                
            # Check email uniqueness if provided (excluding current employee)
            if email:
                cursor.execute("SELECT id FROM employees WHERE email = %s AND id != %s", (email, employee_id))
                if cursor.fetchone():
                    errors.append("An employee with this email already exists.")

        if errors:
            for error in errors:
                flash(error, "error")
            cursor.close()
            connection.close()
            return render_template("company/edit_employee.html", employee=employee, departments=departments, shifts=shifts, roles=roles)

        # Get company name, department and shift names
        company_name = None
        department_name = None
        shift_name = None
        
        # Get company name from company_id
        cursor.execute("SELECT company_name FROM companies WHERE id = %s", (company_id,))
        company_result = cursor.fetchone()
        if company_result:
            company_name = company_result['company_name']
        
        # Validate that we have a company name
        if not company_name:
            flash("Company information not found. Please contact administrator.", "error")
            cursor.close()
            connection.close()
            return render_template("company/edit_employee.html", employee=employee, departments=departments, shifts=shifts, roles=roles)
        
        if department_id:
            cursor.execute("SELECT name FROM departments WHERE id = %s AND company_id = %s", (department_id, company_id))
            dept_result = cursor.fetchone()
            if dept_result:
                department_name = dept_result['name']
            
        if shift_id:
            cursor.execute("SELECT name FROM shifts WHERE id = %s AND company_id = %s", (shift_id, company_id))
            shift_result = cursor.fetchone()
            if shift_result:
                shift_name = shift_result['name']

        # Convert dates to proper format
        try:
            dob_obj = datetime.strptime(dob, '%Y-%m-%d').date()
            joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "error")
            cursor.close()
            connection.close()
            return render_template("company/edit_employee.html", employee=employee, departments=departments, shifts=shifts, roles=roles)

        # Update employee in database
        cursor.execute(
            """
            UPDATE employees SET
                name = %s, emp_id = %s, email = %s, gender = %s, dob = %s, phone = %s, 
                address = %s, role = %s, employee_role = %s, department = %s, 
                shift = %s, joining_date = %s, company = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND company_id = %s
            """,
            (
                name, emp_id, email or None, gender, dob_obj, phone or None, 
                address or None, role or 'General', employee_role, department_name or 'General', 
                shift_name or 'General', joining_date_obj, company_name, employee_id, company_id
            ),
        )
        
        connection.commit()
        cursor.close()
        connection.close()

        flash("Employee updated successfully!", "success")
        return redirect(url_for("company.view_employees"))

    cursor.close()
    connection.close()
    return render_template("company/edit_employee.html", employee=employee, departments=departments, shifts=shifts, roles=roles)


# Employee Registration Routes (QR-based)
@company.route("/employee/qr")
@company_required
def generate_common_qr():
    """Generate common QR code for employee registration and save as image"""
    import qrcode
    import os
    from flask import jsonify, current_app
    
    try:
        # Generate common registration URL
        registration_url = url_for('employee_registration.common_employee_registration', _external=True)
        
        # Create QR code with optimal settings
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(registration_url)
        qr.make(fit=True)
        
        # Create QR code image with high quality
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Ensure static/qr directory exists
        static_dir = os.path.join(current_app.root_path, 'static')
        qr_dir = os.path.join(static_dir, 'qr')
        
        if not os.path.exists(qr_dir):
            os.makedirs(qr_dir)
        
        # Save QR code image
        qr_filename = 'common_qr.png'
        qr_path = os.path.join(qr_dir, qr_filename)
        qr_img.save(qr_path)
        
        # Verify file was created
        if not os.path.exists(qr_path):
            raise Exception("QR code file was not created successfully")
        
        # Return JSON response
        return jsonify({
            "success": True,
            "registration_url": registration_url,
            "qr_image_path": f"/static/qr/{qr_filename}",
            "message": "QR code generated successfully"
        })
        
    except ImportError as e:
        return jsonify({
            "success": False,
            "error": "QR code library not available",
            "message": "Please install qrcode library: pip install qrcode[pil]"
        }), 500
        
    except Exception as e:
        current_app.logger.error(f"QR generation error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to generate QR code"
        }), 500


# Employee Registration Routes (Public - no authentication required)
from flask import Blueprint

# Create a separate blueprint for public employee registration
employee_registration_bp = Blueprint("employee_registration", __name__)

@employee_registration_bp.route("/employee/register", methods=["GET", "POST"])
def common_employee_registration():
    """Public common employee registration form accessible via QR code"""
    
    if request.method == "GET":
        # Get all companies with their departments and shifts for the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get company info for new registration
        cursor.execute(
            """
            SELECT c.id as company_id, c.company_name as company_name,
                   d.id as dept_id, d.name as dept_name,
                   s.id as shift_id, s.name as shift_name,
                   r.id as role_id, r.name as role_name
            FROM companies c
            LEFT JOIN departments d ON c.id = d.company_id
            LEFT JOIN shifts s ON c.id = s.company_id
            LEFT JOIN roles r ON c.id = r.company_id
            ORDER BY c.company_name, d.name, s.name, r.name
            """
        )
        company_data = cursor.fetchall()
        
        # Group data by company
        companies = {}
        for row in company_data:
            company_id = row['company_id']
            if company_id not in companies:
                companies[company_id] = {
                    'id': company_id,
                    'name': row['company_name'],
                    'departments': [],
                    'shifts': [],
                    'roles': []
                }
            
            if row['dept_id'] and row['dept_name']:
                dept = {'id': row['dept_id'], 'name': row['dept_name']}
                if dept not in companies[company_id]['departments']:
                    companies[company_id]['departments'].append(dept)
            
            if row['shift_id'] and row['shift_name']:
                shift = {'id': row['shift_id'], 'name': row['shift_name']}
                if shift not in companies[company_id]['shifts']:
                    companies[company_id]['shifts'].append(shift)
            
            if row['role_id'] and row['role_name']:
                role = {'id': row['role_id'], 'name': row['role_name']}
                if role not in companies[company_id]['roles']:
                    companies[company_id]['roles'].append(role)
        
        cursor.close()
        connection.close()
        
        # Fetch company info for the current session/company
        company_id = None
        if len(companies) == 1:
            company_id = companies[0]['id']
        # Fetch departments, shifts, and roles for the company
        departments, shifts, roles = [], [], []
        if company_id:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM departments WHERE company_id = %s ORDER BY name", (company_id,))
            departments = cursor.fetchall()
            cursor.execute("SELECT id, name, start_time, end_time FROM shifts WHERE company_id = %s ORDER BY name", (company_id,))
            shifts = cursor.fetchall()
            cursor.execute("SELECT id, name FROM roles WHERE company_id = %s ORDER BY name", (company_id,))
            roles = cursor.fetchall()
            cursor.close()
            connection.close()
        return render_template(
            "company/add_employee.html",
            departments=departments,
            shifts=shifts,
            roles=roles,
            minimal=True,
            company_name=companies[0]['name'] if len(companies) == 1 else None
        )
    
    elif request.method == "POST":
        # Use the same logic as add_employee for processing
        from flask import session, redirect, url_for, flash
        # Map form fields to match add_employee
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
            errors.append("Employee name is required.")
        if not emp_id:
            errors.append("Employee ID is required.")
        if not gender:
            errors.append("Gender is required.")
        if not dob:
            errors.append("Date of birth is required.")
        if not employee_role:
            errors.append("Employee Role is required.")
        if not joining_date:
            errors.append("Joining date is required.")

        # Database validation
        if not errors:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id FROM employees WHERE emp_id = %s", (emp_id,))
            if cursor.fetchone():
                errors.append("An employee with this Employee ID already exists.")
            if email:
                cursor.execute("SELECT id FROM employees WHERE email = %s", (email,))
                if cursor.fetchone():
                    errors.append("An employee with this email already exists.")
            cursor.close()
            connection.close()

        if errors:
            for error in errors:
                flash(error, "error")
            # Re-render the form with the same UI
            # (rebuild companies, departments, shifts, roles as in GET)
            # ...existing code for GET...
            # For brevity, redirect to GET
            return redirect(url_for("employee_registration.common_employee_registration"))

        # Get company, department, shift names
        company_name = None
        department_name = None
        shift_name = None
        company_id = request.form.get("company_id", "").strip()
        if company_id:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT company_name FROM companies WHERE id = %s", (company_id,))
            company_result = cursor.fetchone()
            if company_result:
                company_name = company_result['company_name']
            cursor.close()
            connection.close()
        if department_id:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT name FROM departments WHERE id = %s AND company_id = %s", (department_id, company_id))
            dept_result = cursor.fetchone()
            if dept_result:
                department_name = dept_result['name']
            cursor.close()
            connection.close()
        if shift_id:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT name FROM shifts WHERE id = %s AND company_id = %s", (shift_id, company_id))
            shift_result = cursor.fetchone()
            if shift_result:
                shift_name = shift_result['name']
            cursor.close()
            connection.close()

        # Convert dates
        from datetime import datetime
        try:
            dob_obj = datetime.strptime(dob, '%Y-%m-%d').date()
            joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("employee_registration.common_employee_registration"))

        # Insert into database
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO employees (
                name, emp_id, email, gender, dob, phone, address, role, employee_role,
                department, shift, joining_date, company, company_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name, emp_id, email or None, gender, dob_obj, phone or None,
                address or None, role or 'General', employee_role, department_name or 'General',
                shift_name or 'General', joining_date_obj, company_name, company_id
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash("Employee added successfully!", "success")
        return redirect(url_for("company.view_employees"))
        joining_date = request.form.get("joining_date", "").strip()
        
        # Validation
        errors = []
        if not name:
            errors.append("Name is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not company_id:
            errors.append("Company selection is required.")
        if not employee_role:
            errors.append("Employee Role is required.")
        
        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for('employee_registration.common_employee_registration'))
        
        # Auto-generate Employee ID
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Generate unique employee ID
        cursor.execute("SELECT COUNT(*) as count FROM employees WHERE company_id = %s", (company_id,))
        count_result = cursor.fetchone()
        employee_count = count_result['count'] + 1
        
        # Get company code for employee ID
        cursor.execute("SELECT company_code FROM companies WHERE id = %s", (company_id,))
        company_result = cursor.fetchone()
        company_code = company_result['company_code'] if company_result else 'EMP'
        
        # Generate employee ID: COMPANY_CODE + sequential number
        emp_id = f"{company_code}{employee_count:03d}"
        
        # Check if employee ID already exists, if so increment
        while True:
            cursor.execute("SELECT id FROM employees WHERE emp_id = %s", (emp_id,))
            if not cursor.fetchone():
                break
            employee_count += 1
            emp_id = f"{company_code}{employee_count:03d}"
        
        # Check for duplicate phone/email
        if phone:
            cursor.execute("SELECT id FROM employees WHERE phone = %s", (phone,))
            if cursor.fetchone():
                flash("An employee with this phone number already exists.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('employee_registration.common_employee_registration'))
        
        if email:
            cursor.execute("SELECT id FROM employees WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("An employee with this email already exists.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('employee_registration.common_employee_registration'))
        
        # Get department and shift names
        department_name = None
        shift_name = None
        company_name = None
        
        # Get company name
        cursor.execute("SELECT company_name FROM companies WHERE id = %s", (company_id,))
        company_result = cursor.fetchone()
        if company_result:
            company_name = company_result['company_name']
        
        if department_id:
            cursor.execute("SELECT name FROM departments WHERE id = %s", (department_id,))
            dept_result = cursor.fetchone()
            if dept_result:
                department_name = dept_result['name']
        
        if shift_id:
            cursor.execute("SELECT name FROM shifts WHERE id = %s", (shift_id,))
            shift_result = cursor.fetchone()
            if shift_result:
                shift_name = shift_result['name']
        
        # Convert dates
        dob_obj = None
        joining_date_obj = None
        
        if dob:
            try:
                dob_obj = datetime.strptime(dob, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date of birth format.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('employee_registration.common_employee_registration'))
        
        if joining_date:
            try:
                joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid joining date format.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('employee_registration.common_employee_registration'))
        else:
            # Default to today if not provided
            joining_date_obj = datetime.now().date()
        
        # Insert new employee
        cursor.execute(
            """
            INSERT INTO employees (
                name, emp_id, email, phone, gender, dob, address, role, employee_role,
                company, department, shift, joining_date, status, company_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (name, emp_id, email or None, phone, gender or None, dob_obj, 
             address or None, role or None, employee_role, company_name or 'Unknown Company',
             department_name or 'General', shift_name or 'General', 
             joining_date_obj, 'active', company_id)
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return render_template("employee/registration_success.html", 
                             employee_id=emp_id, name=name)


# Role Management Routes
@company.route("/add_role", methods=["GET", "POST"])
@company_required
def add_role():
    company_id = session.get("company_id")

    if request.method == "POST":
        role_name = request.form.get("role_name", "").strip()
        description = request.form.get("description", "").strip()
        
        # Validation
        errors = []
        if not role_name:
            errors.append("Role name is required.")
        
        # Check for duplicate role name
        if not errors:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            cursor.execute("SELECT id FROM roles WHERE name = %s AND company_id = %s", (role_name, company_id))
            if cursor.fetchone():
                errors.append("A role with this name already exists.")
            
            cursor.close()
            connection.close()

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("company/add_role.html")

        # Insert into database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            """
            INSERT INTO roles (name, description, company_id, created_at)
            VALUES (%s, %s, %s, NOW())
            """,
            (role_name, description or None, company_id)
        )
        
        connection.commit()
        cursor.close()
        connection.close()

        flash("Role added successfully!", "success")
        return redirect(url_for("company.view_roles"))

    return render_template("company/add_role.html")


@company.route("/roles")
@company_required
def view_roles():
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT r.id, r.name, r.description, r.created_at,
               COUNT(e.id) as employee_count
        FROM roles r
        LEFT JOIN employees e ON r.name = e.employee_role AND e.company_id = %s
        WHERE r.company_id = %s
        GROUP BY r.id, r.name, r.description, r.created_at
        ORDER BY r.name ASC
        """,
        (company_id, company_id)
    )
    roles = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template("company/view_roles.html", roles=roles)


@company.route("/delete_role/<int:role_id>", methods=["POST"])
@company_required
def delete_role(role_id):
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Check if role exists and belongs to company
    cursor.execute("SELECT name FROM roles WHERE id = %s AND company_id = %s", (role_id, company_id))
    role = cursor.fetchone()
    
    if not role:
        flash("Role not found.", "error")
        cursor.close()
        connection.close()
        return redirect(url_for("company.view_roles"))
    
    # Check if any employees are assigned to this role
    cursor.execute("SELECT COUNT(*) as count FROM employees WHERE employee_role = %s AND company_id = %s", (role['name'], company_id))
    employee_count = cursor.fetchone()['count']
    
    if employee_count > 0:
        flash(f"Cannot delete role '{role['name']}' because {employee_count} employee(s) are assigned to it.", "error")
        cursor.close()
        connection.close()
        return redirect(url_for("company.view_roles"))
    
    # Delete the role
    cursor.execute("DELETE FROM roles WHERE id = %s AND company_id = %s", (role_id, company_id))
    connection.commit()
    cursor.close()
    connection.close()

    flash(f"Role '{role['name']}' deleted successfully!", "success")
    return redirect(url_for("company.view_roles"))


@company.route("/edit_role/<int:role_id>", methods=["GET", "POST"])
@company_required
def edit_role(role_id):
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Get role details
    cursor.execute("SELECT * FROM roles WHERE id = %s AND company_id = %s", (role_id, company_id))
    role = cursor.fetchone()
    
    if not role:
        flash("Role not found.", "error")
        cursor.close()
        connection.close()
        return redirect(url_for("company.view_roles"))

    if request.method == "POST":
        role_name = request.form.get("role_name", "").strip()
        description = request.form.get("description", "").strip()
        
        # Validation
        errors = []
        if not role_name:
            errors.append("Role name is required.")
        
        # Check for duplicate role name (excluding current role)
        if not errors:
            cursor.execute("SELECT id FROM roles WHERE name = %s AND company_id = %s AND id != %s", (role_name, company_id, role_id))
            if cursor.fetchone():
                errors.append("A role with this name already exists.")

        if errors:
            for error in errors:
                flash(error, "error")
            cursor.close()
            connection.close()
            return render_template("company/edit_role.html", role=role)

        # Update role
        cursor.execute(
            """
            UPDATE roles 
            SET name = %s, description = %s, updated_at = NOW()
            WHERE id = %s AND company_id = %s
            """,
            (role_name, description or None, role_id, company_id)
        )
        
        # Update employee roles if role name changed
        if role['name'] != role_name:
            cursor.execute(
                "UPDATE employees SET employee_role = %s WHERE employee_role = %s AND company_id = %s",
                (role_name, role['name'], company_id)
            )
        
        connection.commit()
        cursor.close()
        connection.close()

        flash("Role updated successfully!", "success")
        return redirect(url_for("company.view_roles"))

    cursor.close()
    connection.close()
    return render_template("company/edit_role.html", role=role)

# Public Employee Registration Route (accessed via QR code)
@company.route("/employee/register", methods=["GET", "POST"])
def employee_self_register():
    """Public employee self-registration page accessible via QR code"""
    
    if request.method == "GET":
        # Get all companies with their departments, shifts, and roles for the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get company info for new registration
        cursor.execute(
            """
            SELECT c.id as company_id, c.company_name as company_name,
                   d.id as dept_id, d.name as dept_name,
                   s.id as shift_id, s.name as shift_name,
                   r.id as role_id, r.name as role_name
            FROM companies c
            LEFT JOIN departments d ON c.id = d.company_id
            LEFT JOIN shifts s ON c.id = s.company_id
            LEFT JOIN roles r ON c.id = r.company_id
            ORDER BY c.company_name, d.name, s.name, r.name
            """
        )
        company_data = cursor.fetchall()
        
        # Group data by company
        companies = {}
        for row in company_data:
            company_id = row['company_id']
            if company_id not in companies:
                companies[company_id] = {
                    'id': company_id,
                    'name': row['company_name'],
                    'departments': [],
                    'shifts': [],
                    'roles': []
                }
            
            if row['dept_id'] and row['dept_name']:
                dept = {'id': row['dept_id'], 'name': row['dept_name']}
                if dept not in companies[company_id]['departments']:
                    companies[company_id]['departments'].append(dept)
            
            if row['shift_id'] and row['shift_name']:
                shift = {'id': row['shift_id'], 'name': row['shift_name']}
                if shift not in companies[company_id]['shifts']:
                    companies[company_id]['shifts'].append(shift)
            
            if row['role_id'] and row['role_name']:
                role = {'id': row['role_id'], 'name': row['role_name']}
                if role not in companies[company_id]['roles']:
                    companies[company_id]['roles'].append(role)
        
        cursor.close()
        connection.close()
        
        return render_template("employee/self_registration.html", 
                             companies=list(companies.values()))
    
    elif request.method == "POST":
        # Process registration form submission
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        gender = request.form.get("gender", "").strip()
        dob = request.form.get("dob", "").strip()
        address = request.form.get("address", "").strip()
        role = request.form.get("role", "").strip()
        employee_role = request.form.get("employee_role", "").strip()
        company_id = request.form.get("company_id", "").strip()
        department_id = request.form.get("department_id", "").strip()
        shift_id = request.form.get("shift_id", "").strip()
        joining_date = request.form.get("joining_date", "").strip()
        
        # Validation
        errors = []
        if not name:
            errors.append("Name is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not company_id:
            errors.append("Company selection is required.")
        if not employee_role:
            errors.append("Employee Role is required.")
        
        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for('company.employee_self_register'))
        
        # Auto-generate Employee ID
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Generate unique employee ID
        cursor.execute("SELECT COUNT(*) as count FROM employees WHERE company_id = %s", (company_id,))
        count_result = cursor.fetchone()
        employee_count = count_result['count'] + 1
        
        # Get company code for employee ID
        cursor.execute("SELECT company_code FROM companies WHERE id = %s", (company_id,))
        company_result = cursor.fetchone()
        company_code = company_result['company_code'] if company_result else 'EMP'
        
        # Generate employee ID: COMPANY_CODE + sequential number
        emp_id = f"{company_code}{employee_count:03d}"
        
        # Check if employee ID already exists, if so increment
        while True:
            cursor.execute("SELECT id FROM employees WHERE emp_id = %s", (emp_id,))
            if not cursor.fetchone():
                break
            employee_count += 1
            emp_id = f"{company_code}{employee_count:03d}"
        
        # Check for duplicate phone/email
        if phone:
            cursor.execute("SELECT id FROM employees WHERE phone = %s", (phone,))
            if cursor.fetchone():
                flash("An employee with this phone number already exists.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('company.employee_self_register'))
        
        if email:
            cursor.execute("SELECT id FROM employees WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("An employee with this email already exists.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('company.employee_self_register'))
        
        # Get department and shift names
        department_name = None
        shift_name = None
        company_name = None
        
        # Get company name
        cursor.execute("SELECT company_name FROM companies WHERE id = %s", (company_id,))
        company_result = cursor.fetchone()
        if company_result:
            company_name = company_result['company_name']
        
        if department_id:
            cursor.execute("SELECT name FROM departments WHERE id = %s", (department_id,))
            dept_result = cursor.fetchone()
            if dept_result:
                department_name = dept_result['name']
        
        if shift_id:
            cursor.execute("SELECT name FROM shifts WHERE id = %s", (shift_id,))
            shift_result = cursor.fetchone()
            if shift_result:
                shift_name = shift_result['name']
        
        # Convert dates
        dob_obj = None
        joining_date_obj = None
        
        if dob:
            try:
                dob_obj = datetime.strptime(dob, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date of birth format.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('company.employee_self_register'))
        
        if joining_date:
            try:
                joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid joining date format.", "error")
                cursor.close()
                connection.close()
                return redirect(url_for('company.employee_self_register'))
        else:
            # Default to today if not provided
            joining_date_obj = datetime.now().date()
        
        # Insert new employee
        cursor.execute(
            """
            INSERT INTO employees (
                name, emp_id, email, phone, gender, dob, address, role, employee_role,
                company, department, shift, joining_date, status, company_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (name, emp_id, email or None, phone, gender or None, dob_obj, 
             address or None, role or None, employee_role, company_name or 'Unknown Company',
             department_name or 'General', shift_name or 'General', 
             joining_date_obj, 'registered', company_id)
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return render_template("employee/registration_success.html", 
                             employee_id=emp_id, name=name, company_name=company_name)


# Company Profile Routes
@company.route("/profile", methods=["GET", "POST"])
@company_required
def company_profile():
    """View and edit company profile"""
    company_id = session.get("company_id")
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    if request.method == "POST":
        # Handle profile update
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        pincode = request.form.get("pincode", "").strip()
        gst_number = request.form.get("gst_number", "").strip()
        
        # Handle logo upload
        logo_filename = None
        if 'logo' in request.files:
            logo_file = request.files['logo']
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
                logo_filename = f"company_{company_id}_{timestamp}_{filename}"
                logo_path = os.path.join(upload_dir, logo_filename)
                
                # Save the file
                logo_file.save(logo_path)
        
        # Validation
        errors = []
        if not company_name:
            errors.append("Company name is required.")
        if not email:
            errors.append("Email is required.")
            
        # Check email uniqueness (excluding current company)
        cursor.execute("SELECT id FROM companies WHERE email = %s AND id != %s", (email, company_id))
        if cursor.fetchone():
            errors.append("Email already exists for another company.")
        
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            # Update company profile
            update_query = """
                UPDATE companies SET 
                    company_name = %s, email = %s, phone = %s, address = %s,
                    city = %s, state = %s, pincode = %s, gst_number = %s,
                    updated_at = CURRENT_TIMESTAMP
            """
            update_params = [company_name, email, phone or None, address or None,
                           city or None, state or None, pincode or None, gst_number or None]
            
            if logo_filename:
                update_query += ", logo = %s"
                update_params.append(logo_filename)
            
            update_query += " WHERE id = %s"
            update_params.append(company_id)
            
            cursor.execute(update_query, update_params)
            connection.commit()
            
            flash("Profile updated successfully!", "success")
    
    # Fetch company data
    try:
        cursor.execute("""
            SELECT id, company_name, company_code, email, phone, address, city, state, 
                   pincode, logo, gst_number, status, created_at
            FROM companies 
            WHERE id = %s
        """, (company_id,))
        
        company = cursor.fetchone()
    except Exception as e:
        cursor.close()
        connection.close()
        flash(f"Database error: {str(e)}", "error")
        return redirect(url_for("company.company_dashboard"))
    
    cursor.close()
    connection.close()
    
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("company.company_dashboard"))
    
    return render_template("company/profile.html", company=company)

# Location and Face Capture Routes
@company.route("/location-data")
@company_required
def get_company_location_data():
    """Get company location data for validation"""
    company_id = session.get("company_id")
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT latitude, longitude, radius
            FROM companies 
            WHERE id = %s
        """, (company_id,))
        
        company = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if company and company['latitude'] and company['longitude']:
            return {
                "success": True,
                "latitude": float(company['latitude']),
                "longitude": float(company['longitude']),
                "radius": company['radius'] or 100
            }
        else:
            return {
                "success": False,
                "message": "Company location not configured"
            }
    except Exception as e:
        cursor.close()
        connection.close()
        return {
            "success": False,
            "message": f"Database error: {str(e)}"
        }

# Attendance QR and Processing Routes
@company.route("/attendance-qr")
@company_required
def generate_attendance_qr():
    """Generate QR code for employee attendance"""
    try:
        import qrcode
        import os
        from flask import current_app, jsonify
        
        company_id = session.get("company_id")
        
        # Generate attendance URL
        attendance_url = url_for('attendance.attendance_portal', company_id=company_id, _external=True)
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(attendance_url)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Ensure static/qr directory exists
        static_dir = os.path.join(current_app.root_path, 'static')
        qr_dir = os.path.join(static_dir, 'qr')
        
        if not os.path.exists(qr_dir):
            os.makedirs(qr_dir)
        
        # Save QR code image
        qr_filename = f'attendance_qr_{company_id}.png'
        qr_path = os.path.join(qr_dir, qr_filename)
        qr_img.save(qr_path)
        
        return jsonify({
            "success": True,
            "qr_image_path": f"/static/qr/{qr_filename}",
            "attendance_url": attendance_url
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error generating QR code: {str(e)}"
        })


# Create attendance blueprint
from flask import Blueprint
attendance = Blueprint("attendance", __name__, url_prefix="/attendance")

@attendance.route("/<int:company_id>")
def attendance_portal(company_id):
    """Attendance portal page for employees"""
    # Get company information
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT company_name, latitude, longitude, radius FROM companies WHERE id = %s", (company_id,))
        company = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not company:
            return render_template("attendance/error.html", 
                                 error="Company not found"), 404
        
        return render_template("attendance/portal.html", 
                             company=company, 
                             company_id=company_id)
    except Exception as e:
        cursor.close()
        connection.close()
        return render_template("attendance/error.html", 
                             error=f"Database error: {str(e)}"), 500


@attendance.route("/mark", methods=["POST"])
def mark_attendance():
    """Process attendance marking"""
    try:
        import json
        from datetime import date
        
        data = request.get_json()
        employee_id = data.get('employee_id', '').strip()
        company_id = data.get('company_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        face_image_data = data.get('face_image_data', '').strip()
        
        if not all([employee_id, company_id, latitude, longitude, face_image_data]):
            return jsonify({
                "success": False,
                "message": "Missing required data"
            })
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Check if employee exists
        cursor.execute("""
            SELECT id, name, face_image, company_id 
            FROM employees 
            WHERE emp_id = %s AND company_id = %s
        """, (employee_id, company_id))
        
        employee = cursor.fetchone()
        if not employee:
            cursor.close()
            connection.close()
            return jsonify({
                "success": False,
                "message": "Employee not found"
            })
        
        # Get company location settings
        cursor.execute("""
            SELECT latitude, longitude, radius, company_name
            FROM companies 
            WHERE id = %s
        """, (company_id,))
        
        company = cursor.fetchone()
        if not company:
            cursor.close()
            connection.close()
            return jsonify({
                "success": False,
                "message": "Company not found"
            })
        
        # Validate location
        def calculate_distance(lat1, lng1, lat2, lng2):
            import math
            R = 6371e3  # Earth's radius in meters
            φ1 = lat1 * math.pi/180
            φ2 = lat2 * math.pi/180
            Δφ = (lat2-lat1) * math.pi/180
            Δλ = (lng2-lng1) * math.pi/180
            
            a = math.sin(Δφ/2) * math.sin(Δφ/2) + \
                math.cos(φ1) * math.cos(φ2) * \
                math.sin(Δλ/2) * math.sin(Δλ/2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            return R * c
        
        distance = calculate_distance(
            float(latitude), float(longitude),
            float(company['latitude']), float(company['longitude'])
        )
        
        location_verified = distance <= (company['radius'] or 100)
        
        if not location_verified:
            cursor.close()
            connection.close()
            return jsonify({
                "success": False,
                "message": f"Location verification failed. You are {int(distance)}m away from company location."
            })
        
        # Check if already marked attendance today
        today = date.today()
        cursor.execute("""
            SELECT id FROM attendance 
            WHERE employee_id = %s AND company_id = %s AND date = %s
        """, (employee_id, company_id, today))
        
        existing_attendance = cursor.fetchone()
        if existing_attendance:
            cursor.close()
            connection.close()
            return jsonify({
                "success": False,
                "message": "Attendance already marked for today"
            })
        
        # Save face image for attendance
        face_filename = None
        if face_image_data:
            try:
                import base64
                import os
                from flask import current_app
                import time
                
                # Create attendance faces directory
                face_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'attendance_faces')
                os.makedirs(face_dir, exist_ok=True)
                
                # Remove data URL prefix
                if face_image_data.startswith('data:image'):
                    face_image_data = face_image_data.split(',')[1]
                
                # Decode base64 image
                image_data = base64.b64decode(face_image_data)
                
                # Generate filename
                timestamp = str(int(time.time()))
                face_filename = f"attendance_{employee_id}_{timestamp}.jpg"
                face_path = os.path.join(face_dir, face_filename)
                
                # Save image
                with open(face_path, 'wb') as f:
                    f.write(image_data)
                    
            except Exception as e:
                cursor.close()
                connection.close()
                return jsonify({
                    "success": False,
                    "message": f"Error processing face image: {str(e)}"
                })
        
        # Mark attendance
        cursor.execute("""
            INSERT INTO attendance (
                employee_id, company_id, date, face_image, 
                latitude, longitude, location_verified, face_verified
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            employee_id, company_id, today, face_filename,
            latitude, longitude, location_verified, True  # Face verification placeholder
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            "success": True,
            "message": f"Attendance marked successfully for {employee['name']}",
            "employee_name": employee['name'],
            "time": "now"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error processing attendance: {str(e)}"
        })


# Register attendance blueprint
def register_attendance_blueprint(app):
    app.register_blueprint(attendance)