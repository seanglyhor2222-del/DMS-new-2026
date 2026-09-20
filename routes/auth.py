from functools import wraps
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User, AuditLog

auth_bp = Blueprint("auth", __name__)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("អ្នកមិនមានសិទ្ធិចូលប្រើទំព័រនេះទេ (Admin only).", "danger")
            return redirect(url_for("documents.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def permission_required(flag_name):
    """e.g. @permission_required('can_edit')"""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.permission(flag_name):
                flash("អ្នកគ្មានសិទ្ធិប្រើមុខងារនេះទេ។", "danger")
                return redirect(url_for("documents.dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("documents.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("ឈ្មោះអ្នកប្រើ ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវ។", "danger")
            return render_template("login.html")

        if not user.is_active_account:
            flash("គណនីនេះត្រូវបានផ្អាកដោយអ្នកគ្រប់គ្រង។", "danger")
            return render_template("login.html")

        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.add(AuditLog(user_id=user.id, action="login", detail=f"{user.username} logged in"))
        db.session.commit()
        return redirect(url_for("documents.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
