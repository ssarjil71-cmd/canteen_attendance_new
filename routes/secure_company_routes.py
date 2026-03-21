from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from database.db_connection import get_db_connection

secure_company_bp = Blueprint('secure_company', __name__, url_prefix='/company')

def company_login_required(f):
    """Decorator to require company login"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'company_id' not in session or session.get('role') != 'company':
            flash('Please login to access the company dashboard.', 'error')
            return redirect(url_for('secure_company.company_login'))
        return f(*args, **kwargs)
    return decorated_function

@secure_company_bp.route('/login', methods=['GET', 'POST'])
def company_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('company/login.html')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Get company by email
            cursor.execute('SELECT id, name, email, password, company_code FROM company WHERE email = %s', (email,))
            company = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if company and check_password_hash(company['password'], password):
                # Login successful
                session['company_id'] = company['id']
                session['company_name'] = company['name']
                session['company_email'] = company['email']
                session['company_code'] = company['company_code']
                session['role'] = 'company'
                session['user_id'] = company['id']
                session['username'] = company['email']
                
                flash(f'Welcome back, {company["name"]}!', 'success')
                return redirect(url_for('secure_company.company_dashboard'))
            else:
                flash('Invalid email or password', 'error')
                return render_template('company/login.html')
                
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
            return render_template('company/login.html')
    
    return render_template('company/login.html')

@secure_company_bp.route('/dashboard')
@company_login_required
def company_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        company_id = session.get('company_id')
        company_name = session.get('company_name')
        
        # Get employee count for this company
        cursor.execute('SELECT COUNT(*) FROM employees WHERE company = %s', (company_name,))
        employee_count = cursor.fetchone()[0]
        
        # Get manager count for this company (from old companies table)
        cursor.execute('''
            SELECT COUNT(*) FROM managers m 
            JOIN companies c ON m.company_id = c.id 
            WHERE c.company_name = %s
        ''', (company_name,))
        manager_count = cursor.fetchone()[0]
        
        # Get contractor count (general)
        cursor.execute('SELECT COUNT(*) FROM contractors')
        contractor_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return render_template('company/secure_dashboard.html', 
                             employee_count=employee_count,
                             manager_count=manager_count,
                             contractor_count=contractor_count)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('company/secure_dashboard.html', 
                             employee_count=0,
                             manager_count=0,
                             contractor_count=0)

@secure_company_bp.route('/logout')
def company_logout():
    # Clear company session
    session.pop('company_id', None)
    session.pop('company_name', None)
    session.pop('company_email', None)
    session.pop('company_code', None)
    session.pop('role', None)
    session.pop('user_id', None)
    session.pop('username', None)
    
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('secure_company.company_login'))

@secure_company_bp.route('/employees')
@company_login_required
def company_employees():
    flash('Company employees view - Coming Soon!', 'info')
    return redirect(url_for('secure_company.company_dashboard'))

@secure_company_bp.route('/reports')
@company_login_required
def company_reports():
    flash('Company reports - Coming Soon!', 'info')
    return redirect(url_for('secure_company.company_dashboard'))

@secure_company_bp.route('/settings')
@company_login_required
def company_settings():
    flash('Company settings - Coming Soon!', 'info')
    return redirect(url_for('secure_company.company_dashboard'))