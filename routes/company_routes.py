from flask import Blueprint, render_template, session, redirect, url_for, flash
from database.db_connection import get_db_connection

company_bp = Blueprint('company', __name__, url_prefix='/company')

@company_bp.route('/dashboard')
def company_dashboard():
    # Check if user is logged in as company
    if session.get('role') != 'company':
        flash('Access denied. Please login as a company.', 'error')
        return redirect(url_for('auth.role_login', role='company'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        company_id = session.get('company_id')
        
        # Get employee count for this company
        cursor.execute('SELECT COUNT(*) FROM employees WHERE company = (SELECT company_name FROM companies WHERE id = %s)', (company_id,))
        employee_count = cursor.fetchone()[0]
        
        # Get manager count for this company
        cursor.execute('SELECT COUNT(*) FROM managers WHERE company_id = %s', (company_id,))
        manager_count = cursor.fetchone()[0]
        
        # Get contractor count (assuming contractors are also company-specific)
        cursor.execute('SELECT COUNT(*) FROM contractors')
        contractor_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return render_template('company/company_dashboard.html', 
                             employee_count=employee_count,
                             manager_count=manager_count,
                             contractor_count=contractor_count)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('company/company_dashboard.html', 
                             employee_count=0,
                             manager_count=0,
                             contractor_count=0)

@company_bp.route('/employees')
def company_employees():
    # Placeholder for company employees view
    flash('Company employees view - Coming Soon!', 'info')
    return redirect(url_for('company.company_dashboard'))

@company_bp.route('/attendance')
def company_attendance():
    # Placeholder for company attendance reports
    flash('Attendance reports - Coming Soon!', 'info')
    return redirect(url_for('company.company_dashboard'))

@company_bp.route('/managers')
def company_managers():
    # Placeholder for company managers overview
    flash('Manager overview - Coming Soon!', 'info')
    return redirect(url_for('company.company_dashboard'))

@company_bp.route('/settings')
def company_settings():
    # Placeholder for company settings
    flash('Company settings - Coming Soon!', 'info')
    return redirect(url_for('company.company_dashboard'))

@company_bp.route('/profile')
def company_profile():
    # Placeholder for company profile
    flash('Company profile - Coming Soon!', 'info')
    return redirect(url_for('company.company_dashboard'))