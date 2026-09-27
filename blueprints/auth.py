from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from database import get_user_by_username

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            default_url = url_for("pos.index") if user["role"] == "admin" else url_for("pos.pos")
            next_url = request.args.get("next") or default_url
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = default_url
            return redirect(next_url)
        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
