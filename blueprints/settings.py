import os
import tempfile

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from database import (
    get_settings, save_setting, get_categories, add_category, delete_category,
)
from helpers import admin_required
import services.backup as bk
import services.google_drive as gdb

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        for key in [
            "shop_name", "shop_address", "shop_phone",
            "backup_path", "low_stock_threshold", "printer_name",
            "service_percent", "tax_percent",
            "return_policy", "exchange_policy",
        ]:
            save_setting(key, request.form.get(key, ""))
        flash("تم حفظ الإعدادات ✓", "success")
        return redirect(url_for("settings.settings"))

    s           = get_settings()
    
    try:
        drive_path  = bk.find_google_drive_path()
    except Exception:
        drive_path  = None
    
    try:
        drive_email = gdb.get_connected_email()
    except Exception:
        drive_email = None
    
    try:
        has_creds   = gdb._has_custom_creds()
    except Exception:
        has_creds   = False
    
    try:
        categories  = get_categories()
    except Exception:
        categories  = []
    
    return render_template(
        "settings.html", settings=s, drive_path=drive_path,
        drive_email=drive_email, has_creds=has_creds, categories=categories,
    )


@settings_bp.route("/settings/restore", methods=["POST"])
@admin_required
def settings_restore():
    file = request.files.get("restore_file")
    if not file or not file.filename.lower().endswith(".xlsx"):
        flash("اختر ملف Excel (.xlsx) صالح", "danger")
        return redirect(url_for("settings.settings"))

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
            file.save(tmp_path)

        counts, errors = bk.restore_from_excel(tmp_path)

        parts = [
            f"{n} {bk._TABLE_LABELS.get(t, t)}"
            for t, n in counts.items() if n > 0
        ]
        summary = " | ".join(parts) if parts else "لم يتم استيراد أي بيانات"
        flash(f"تم الاستيراد بنجاح ✓  —  {summary}", "success")

        if errors:
            flash("تحذيرات: " + " | ".join(errors[:5]), "warning")

    except Exception as exc:
        flash(f"فشل الاستيراد: {exc}", "danger")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    return redirect(url_for("settings.settings"))


@settings_bp.route("/api/categories/add", methods=["POST"])
@admin_required
def api_category_add():
    name = (request.get_json() or {}).get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "اسم الفئة مطلوب"})
    add_category(name)
    return jsonify({"success": True, "categories": get_categories()})


@settings_bp.route("/api/categories/delete", methods=["POST"])
@admin_required
def api_category_delete():
    name = (request.get_json() or {}).get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "اسم الفئة مطلوب"})
    delete_category(name)
    return jsonify({"success": True, "categories": get_categories()})


@settings_bp.route("/api/drive/connect")
@admin_required
def drive_connect():
    from flask import session as flask_session, redirect as flask_redirect
    redirect_uri = url_for("settings.drive_callback", _external=True)
    url, state   = gdb.start_auth_flow(redirect_uri)
    if not url:
        flash(f"خطأ: {state}", "danger")
        return redirect(url_for("settings.settings"))
    flask_session["oauth_state"] = state
    return flask_redirect(url)


@settings_bp.route("/api/drive/callback")
@admin_required
def drive_callback():
    code = request.args.get("code")
    if not code:
        flash("فشل ربط جوجل درايف", "danger")
        return redirect(url_for("settings.settings"))
    redirect_uri = url_for("settings.drive_callback", _external=True)
    email, err   = gdb.finish_auth_flow(code, redirect_uri)
    if err:
        flash(f"خطأ: {err}", "danger")
    else:
        flash(f"تم ربط الحساب: {email} ✓", "success")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/api/drive/disconnect", methods=["POST"])
@admin_required
def drive_disconnect():
    gdb.disconnect()
    flash("تم فصل حساب جوجل ✓", "success")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/api/drive/backup", methods=["POST"])
@admin_required
def drive_backup_now():
    from database.connection import DB_PATH
    ok, msg = gdb.backup_to_drive(DB_PATH)
    return jsonify({"success": ok, "message": msg})


@settings_bp.route("/api/backup", methods=["POST"])
@admin_required
def api_backup():
    result = bk.do_backup()
    if result["success"]:
        return jsonify(
            {"success": True, "message": f"تم الحفظ في: {result['path']}"}
        )
    return jsonify({"success": False, "error": result["error"]})


@settings_bp.route("/api/reset-all-data", methods=["POST"])
@admin_required
def api_reset_all_data():
    from database.connection import get_db
    code = (request.get_json() or {}).get("code", "")
    if code != "001100":
        return jsonify({"success": False, "error": "الكود غير صحيح"})
    try:
        with get_db() as conn:
            for table in [
                "sale_items", "returns", "stock_movements",
                "purchase_items", "purchases", "sales",
                "products", "customers", "suppliers",
            ]:
                conn.execute(f"DELETE FROM {table}")
            try:
                conn.execute(
                    "DELETE FROM sqlite_sequence WHERE name IN "
                    "('sale_items','returns','stock_movements','purchase_items',"
                    "'purchases','sales','products','customers','suppliers')"
                )
            except Exception:
                pass
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@settings_bp.route("/api/network-qr")
@admin_required
def api_network_qr():
    import socket
    import io
    import base64
    import qrcode as _qr

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"

    url = f"http://{ip}:5000/login"
    qr = _qr.QRCode(version=1, box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({"qr": f"data:image/png;base64,{b64}", "url": url, "ip": ip})
