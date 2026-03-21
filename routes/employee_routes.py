from flask import Blueprint, flash, redirect, url_for

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


@employee_bp.route("/register", methods=["GET", "POST"])
def employee_register():
    flash("Employee self-registration is temporarily unavailable in this build.", "error")
    return redirect(url_for("auth.landing_page"))
