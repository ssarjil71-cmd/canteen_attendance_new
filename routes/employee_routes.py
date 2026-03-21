from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
import os
import base64
from werkzeug.utils import secure_filename
from database.db_connection import get_db_connection

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

def save_employee_to_database(name, emp_id, gender, dob, company, role, department, shift, joining_date, photo_data):
    """
    Common function to save employee data to database
    Used by both manager dashboard and QR registration forms
    """
    try:
        # Decode base64 image
        header, encoded = photo_data.split(',', 1) if ',' in photo_data else ('', photo_data)
        img_bytes = base64.b64decode(encoded)
        filename = secure_filename(f"{emp_id}_photo.png")
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        with open(file_path, 'wb') as f:
            f.write(img_bytes)
        db_img_path = f"static/uploads/{filename}"

        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO employees (name, emp_id, gender, dob, company, role, department, shift, joining_date, photo) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (name, emp_id, gender, dob, company, role, department, shift, joining_date, db_img_path))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "Employee registered successfully!"
    except Exception as e:
        if 'Duplicate entry' in str(e) and 'emp_id' in str(e):
            return False, 'Employee ID already exists. Please use a unique Employee ID.'
        else:
            return False, f'An error occurred while registering the employee: {str(e)}'

@employee_bp.route('/register', methods=['GET', 'POST'])
def employee_register():
    error = None
    if request.method == 'POST':
        # Get form data (same field names as manager form)
        name = request.form.get('name', '').strip()
        emp_id = request.form.get('emp_id', '').strip()
        gender = request.form.get('gender', '').strip()
        dob = request.form.get('dob', '').strip()
        company = request.form.get('company', '').strip()
        role = request.form.get('role', '').strip()
        department = request.form.get('department', '').strip()
        shift = request.form.get('shift', '').strip()
        joining_date = request.form.get('joining_date', '').strip()
        photo_data = request.form.get('photo_data', '').strip()

        # Validate all fields
        if not all([name, emp_id, gender, dob, company, role, department, shift, joining_date, photo_data]):
            error = 'All fields including photo are required.'
        else:
            # Use common function to save employee
            success, message = save_employee_to_database(
                name, emp_id, gender, dob, company, role, department, shift, joining_date, photo_data
            )
            if success:
                flash(message, 'success')
                return redirect(url_for('employee.employee_register'))
            else:
                error = message
    
    return render_template('employee_register.html', error=error)
