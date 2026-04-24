from flask import Flask, session
from config import Config
from database.bootstrap import ensure_database_ready
from module_access import update_module_flags_in_session
from database.db_connection import get_db_connection

# Import routes
from routes.auth_routes import auth
from routes.admin_routes import admin
from routes.company_routes import company, employee_registration_bp
from routes.employee_routes import employee_bp
from routes.attendance_routes import attendance
from routes.meal_confirmation_routes import meal_confirmation
from routes.salary_routes import salary_bp

app = Flask(__name__)
app.config.from_object(Config)

if not ensure_database_ready():
    raise RuntimeError("Database bootstrap failed. Check DB credentials and MySQL server status.")

# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(admin)
app.register_blueprint(company)
app.register_blueprint(attendance)  # Face recognition attendance system
app.register_blueprint(meal_confirmation)  # Meal confirmation dashboard
app.register_blueprint(salary_bp)

app.register_blueprint(employee_registration_bp)  # Public employee registration
app.register_blueprint(employee_bp)


@app.before_request
def sync_company_module_flags():
    role = session.get("role")
    company_id = session.get("company_id")
    if role in {"company", "canteen"} and company_id:
        try:
            update_module_flags_in_session(company_id)
        except Exception as exc:
            app.logger.warning("Module flag sync skipped due to DB error: %s", exc)


@app.context_processor
def inject_company_logo():
    logo = None
    company_id = session.get("company_id")
    if company_id and session.get("role") in {"company", "canteen"}:
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT logo FROM companies WHERE id = %s", (company_id,))
            row = cursor.fetchone()
            cursor.close()
            connection.close()
            if row:
                logo = row.get("logo")
        except Exception:
            pass
    return {"company_logo": logo}

if __name__ == "__main__":
    app.run(debug=True)