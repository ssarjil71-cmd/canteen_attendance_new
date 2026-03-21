from flask import Flask
from config import Config
from database.bootstrap import ensure_database_ready

# Import routes


from routes.auth_routes import auth
from routes.admin_routes import admin
from routes.company_routes import company
from routes.manager_routes import manager_bp
from routes.employee_routes import employee_bp

app = Flask(__name__)
app.config.from_object(Config)

if not ensure_database_ready():
    raise RuntimeError("Database bootstrap failed. Check DB credentials and MySQL server status.")

# Register Blueprints


app.register_blueprint(auth)
app.register_blueprint(admin)
app.register_blueprint(company)
app.register_blueprint(manager_bp)
app.register_blueprint(employee_bp)

if __name__ == "__main__":
    app.run(debug=True)