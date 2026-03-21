
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from database.db_connection import get_db_connection
import os
import base64
from werkzeug.utils import secure_filename
import qrcode

manager_bp = Blueprint('manager', __name__, url_prefix='/manager')

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
        return True, "Employee added successfully!"
    except Exception as e:
        if 'Duplicate entry' in str(e) and 'emp_id' in str(e):
            return False, 'Employee ID already exists. Please use a unique Employee ID.'
        else:
            return False, f'An error occurred while adding the employee: {str(e)}'

# QR Code Generation Route
@manager_bp.route('/generate_qr', methods=['GET'])
def generate_qr():
    qr_url = 'http://127.0.0.1:5000/employee/register'
    qr_img = qrcode.make(qr_url)
    qr_folder = os.path.join(current_app.root_path, 'static', 'qr_codes')
    os.makedirs(qr_folder, exist_ok=True)
    qr_path = os.path.join(qr_folder, 'add_employee_qr.png')
    qr_img.save(qr_path)
    return send_file(qr_path, mimetype='image/png')


# Add Employee (updated)

import os
import base64
from werkzeug.utils import secure_filename
from flask import current_app

@manager_bp.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    error = None
    if request.method == 'POST':
        # Get form data
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
                return redirect(url_for('manager.view_employee'))
            else:
                error = message
    
    return render_template('manager/add_employee.html', error=error)

# View Employee
@manager_bp.route('/view_employee')
def view_employee():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch only required fields: name, emp_id, department, shift, and id for actions
    cursor.execute('SELECT id, name, emp_id, department, shift FROM employees ORDER BY name')
    employees = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('manager/view_employee.html', employees=employees)

# Edit Employee Route
@manager_bp.route('/edit_employee/<int:id>')
def edit_employee(id):
    # TODO: Implement edit employee functionality
    flash(f'Edit employee functionality for ID {id} - Coming Soon!', 'info')
    return redirect(url_for('manager.view_employee'))

# Delete Employee Route
@manager_bp.route('/delete_employee/<int:id>')
def delete_employee(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Get employee name before deletion for confirmation message
        cursor.execute('SELECT name FROM employees WHERE id = %s', (id,))
        employee = cursor.fetchone()
        
        if employee:
            # Delete the employee
            cursor.execute('DELETE FROM employees WHERE id = %s', (id,))
            conn.commit()
            flash(f'Employee "{employee[0]}" deleted successfully!', 'success')
        else:
            flash('Employee not found!', 'error')
        
        cursor.close()
        conn.close()
    except Exception as e:
        flash(f'Error deleting employee: {str(e)}', 'error')
    
    return redirect(url_for('manager.view_employee'))

# Add Contractor
@manager_bp.route('/add_contractor', methods=['GET', 'POST'])
def add_contractor():
    if request.method == 'POST':
        name = request.form['name']
        company = request.form['company']
        phone = request.form['phone']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO contractors (name, company, phone) VALUES (%s, %s, %s)', (name, company, phone))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Contractor added successfully!', 'success')
        return redirect(url_for('manager.view_contractor'))
    return render_template('manager/add_contractor.html')

# View Contractor
@manager_bp.route('/view_contractor')
def view_contractor():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM contractors')
    contractors = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('manager/view_contractor.html', contractors=contractors)

# Manager Dashboard Route
@manager_bp.route('/dashboard')
def dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get employee count
        cursor.execute('SELECT COUNT(*) FROM employees')
        employee_count = cursor.fetchone()[0]
        
        # Get contractor count
        cursor.execute('SELECT COUNT(*) FROM contractors')
        contractor_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return render_template('manager/dashboard.html', 
                             employee_count=employee_count,
                             contractor_count=contractor_count)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('manager/dashboard.html', 
                             employee_count=0,
                             contractor_count=0)
