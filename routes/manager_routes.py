from flask import Blueprint, flash, redirect, url_for

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


@manager_bp.route("/dashboard")
def manager_dashboard_home():
    return redirect(url_for("auth.manager_dashboard"))


@manager_bp.route("/add_employee", methods=["GET", "POST"])
def add_employee():
    flash("Add Employee module is temporarily unavailable in this build.", "error")
    return redirect(url_for("auth.manager_dashboard"))


@manager_bp.route("/view_employee")
def view_employee():
    flash("View Employee module is temporarily unavailable in this build.", "error")
    return redirect(url_for("auth.manager_dashboard"))


@manager_bp.route("/add_contractor", methods=["GET", "POST"])
def add_contractor():
    flash("Add Contractor module is temporarily unavailable in this build.", "error")
    return redirect(url_for("auth.manager_dashboard"))


@manager_bp.route("/view_contractor")
def view_contractor():
    flash("View Contractor module is temporarily unavailable in this build.", "error")
    return redirect(url_for("auth.manager_dashboard"))
