from flask import Flask
from config import Config

# Import routes


from routes.auth_routes import auth
from routes.admin_routes import admin
from routes.manager_routes import manager_bp
from routes.employee_routes import employee_bp
from routes.company_routes import company_bp
from routes.secure_company_routes import secure_company_bp

app = Flask(__name__)
app.config.from_object(Config)

# Register Blueprints


app.register_blueprint(auth)
app.register_blueprint(admin)
app.register_blueprint(manager_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(company_bp)
app.register_blueprint(secure_company_bp)

if __name__ == "__main__":
    app.run(debug=True)