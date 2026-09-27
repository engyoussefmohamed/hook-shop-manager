import os
from functools import wraps

import qrcode
from flask import g, session, request, redirect, url_for, flash, jsonify

from config import APP_DIR, OPEN_ENDPOINTS
from database.users import get_user_by_id
from database.products import get_product_by_id

QR_DIR = os.path.join(APP_DIR, "qr_codes")
os.makedirs(QR_DIR, exist_ok=True)


def _positive_int(value, default=1):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    if not hasattr(g, "_current_user"):
        g._current_user = get_user_by_id(user_id)
    return g._current_user


def is_admin():
    user = current_user()
    return bool(user and user.get("role") == "admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("auth.login", next=request.path))
        if not is_admin():
            flash("هذه الصلاحية للمدير فقط", "danger")
            return redirect(url_for("pos.pos"))
        return view(*args, **kwargs)
    return wrapped


def check_auth():
    if request.endpoint in {None, "auth.login", "static"}:
        return
    if request.endpoint in OPEN_ENDPOINTS:
        return
    user = current_user()
    if not user:
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "غير مصرح"}), 401
        return redirect(url_for("auth.login", next=request.path))


def inject_globals():
    if request.path.startswith("/api/"):
        return {}
    from database import get_settings, get_low_stock_custom
    if not hasattr(g, "_settings"):
        g._settings = get_settings()
    if not hasattr(g, "_low_stock_count"):
        g._low_stock_count = len(get_low_stock_custom())
    s = g._settings
    return {
        "shop_name":       s.get("shop_name", "محل الملابس"),
        "low_stock_count": g._low_stock_count,
        "now":             __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        "current_user":    current_user(),
        "is_admin":        is_admin(),
    }


def generate_qr(product_id):
    product = get_product_by_id(product_id)
    if not product:
        return
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(product["barcode"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(os.path.join(QR_DIR, f"{product_id}.png"))
