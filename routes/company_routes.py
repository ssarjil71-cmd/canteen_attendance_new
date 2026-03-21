from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

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


@company.route("/add_manager", methods=["GET", "POST"])
@company_required
def add_manager():
    company_id = session.get("company_id")

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not full_name or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("company/add_manager.html")

        if password != confirm_password:
            flash("Password and confirm password must match.", "error")
            return render_template("company/add_manager.html")

        username = email
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT id FROM managers WHERE username = %s OR email = %s", (username, email))
        existing_user = cursor.fetchone()
        if existing_user:
            cursor.close()
            connection.close()
            flash("A manager with this email already exists.", "error")
            return render_template("company/add_manager.html")

        cursor.execute(
            """
            INSERT INTO managers (username, full_name, email, password, company_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (username, full_name, email, password, company_id),
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash("Manager added successfully.", "success")
        return redirect(url_for("company.view_managers"))

    return render_template("company/add_manager.html")


@company.route("/managers")
@company_required
def view_managers():
    company_id = session.get("company_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, username, full_name, email, created_at
        FROM managers
        WHERE company_id = %s
        ORDER BY full_name ASC, id ASC
        """,
        (company_id,),
    )
    managers = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template("company/view_managers.html", managers=managers)
