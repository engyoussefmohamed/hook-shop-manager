import threading

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash

from database import (
    get_settings, get_all_products, get_product_by_id, get_product_by_barcode,
    add_product, update_product_quantity, create_sale, get_sale, get_last_sale,
    get_daily_stats, get_payment_summary, get_top_products, void_sale,
)
from helpers import current_user, is_admin, generate_qr, admin_required
import services.receipt as rp
import services.backup as bk

pos_bp = Blueprint("pos", __name__)


@pos_bp.route("/pos")
def pos():
    from database import get_categories
    categories = ["الكل"] + get_categories()
    settings = get_settings()
    return render_template("pos.html", categories=categories, settings=settings)


@pos_bp.route("/")
def index():
    if current_user() and is_admin():
        stats   = get_daily_stats()
        from database import get_low_stock_custom, get_monthly_revenue
        low     = get_low_stock_custom()
        monthly = get_monthly_revenue()[:6]
        top     = get_top_products(5)
        settings = get_settings()
        return render_template("index.html", stats=stats, low_stock=low,
                               monthly=monthly, top_products=top, settings=settings)
    return redirect(url_for("pos.pos"))


@pos_bp.route("/cashier/last-receipt")
def cashier_last_receipt():
    sale = get_last_sale()
    if not sale:
        flash("لا توجد فواتير بعد", "danger")
        return redirect(url_for("pos.pos"))
    return redirect(url_for("pos.receipt", sale_id=sale["id"]))


@pos_bp.route("/api/product/<barcode>")
def api_product(barcode):
    settings = get_settings()
    prefix = settings.get("scale_barcode_prefix", "20")
    if barcode.startswith(prefix) and len(barcode) >= 12:
        base_code = barcode[:7]
        product = get_product_by_barcode(base_code)
        if product:
            return jsonify({"success": True, "product": product, "scale_qty": 1})
    product = get_product_by_barcode(barcode)
    if not product:
        try:
            product = get_product_by_id(int(barcode))
        except (ValueError, TypeError):
            pass

    if not product:
        return jsonify({"success": False, "error": "المنتج غير موجود"})

    if product["quantity"] <= 0:
        return jsonify(
            {"success": False, "error": f"المنتج '{product['name']}' نفذ من المخزون"}
        )

    return jsonify({"success": True, "product": product})


@pos_bp.route("/api/products/search")
def api_products_search():
    q   = request.args.get("q", "").strip()
    cat = request.args.get("category", "")
    results = get_all_products(
        q or None, cat if cat and cat != "الكل" else None
    )
    return jsonify(results)


@pos_bp.route("/api/products/quick-add", methods=["POST"])
def api_products_quick_add():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "error": "اسم المنتج مطلوب"})

    try:
        pid = add_product(
            name=name,
            category=str(data.get("category") or "ملابس").strip() or "ملابس",
            price=float(data.get("price") or 0),
            cost_price=float(data.get("cost_price") or 0),
            size=str(data.get("size") or "").strip(),
            color=str(data.get("color") or "").strip(),
            quantity=int(data.get("quantity") or 0),
            barcode=str(data.get("barcode") or "").strip(),
        )
        generate_qr(pid)
        return jsonify({"success": True, "product": get_product_by_id(pid)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@pos_bp.route("/api/product/<int:pid>/quantity", methods=["POST"])
def api_product_quantity(pid):
    data = request.get_json() or {}
    try:
        quantity = max(0, int(data.get("quantity") or 0))
        update_product_quantity(pid, quantity)
        return jsonify({"success": True, "product": get_product_by_id(pid)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@pos_bp.route("/api/sale/complete", methods=["POST"])
def api_sale_complete():
    data = request.get_json()
    if not data or not data.get("items"):
        return jsonify({"success": False, "error": "لا توجد منتجات"})

    try:
        sale_id = create_sale(
            items          = data["items"],
            total          = float(data.get("total", 0)),
            discount       = float(data.get("discount", 0)),
            final_total    = float(data.get("final_total", 0)),
            payment_method = data.get("payment_method", "كاش"),
            notes          = data.get("notes", ""),
            customer_id    = data.get("customer_id") or None,
            paid_amount    = data.get("paid_amount"),
            tax            = float(data.get("tax", 0)),
            service        = float(data.get("service", 0)),
            discount_type  = data.get("discount_type", "amount"),
            discount_value = float(data.get("discount_value", data.get("discount", 0))),
        )
        threading.Thread(target=bk.auto_backup, daemon=True).start()

        settings           = get_settings()
        printer_configured = bool(rp.get_effective_printer(settings))
        if printer_configured:
            sale = get_sale(sale_id)
            threading.Thread(
                target=rp.print_receipt, args=(sale, settings), daemon=True
            ).start()

        return jsonify({
            "success": True, "sale_id": sale_id,
            "printer_configured": printer_configured,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@pos_bp.route("/api/sale/<int:sale_id>/void", methods=["POST"])
def api_void_sale(sale_id):
    if not current_user():
        return jsonify({"success": False, "error": "غير مصرح"}), 401
    if not is_admin():
        return jsonify({"success": False, "error": "هذه الصلاحية للمدير فقط"}), 403
    ok, msg = void_sale(sale_id)
    return jsonify({"success": ok, "message": msg})


@pos_bp.route("/api/sale/last")
def api_last_sale():
    sale = get_last_sale()
    if not sale:
        return jsonify({"success": False, "error": "لا توجد فواتير"})
    return jsonify({"success": True, "sale": sale})


@pos_bp.route("/api/day-summary")
def api_day_summary():
    from datetime import datetime
    date = request.args.get("date", "").strip() or None
    return jsonify({
        "success": True,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "stats": get_daily_stats(date),
        "payments": get_payment_summary(date),
        "top_products": get_top_products(5),
    })


@pos_bp.route("/receipt/<int:sale_id>")
def receipt(sale_id):
    sale     = get_sale(sale_id)
    settings = get_settings()
    if not sale:
        return "الفاتورة غير موجودة", 404
    return render_template("receipt.html", sale=sale, settings=settings)


@pos_bp.route("/api/sale/<int:sale_id>")
def api_sale_detail(sale_id):
    sale = get_sale(sale_id)
    if not sale:
        return jsonify({"success": False})
    return jsonify({"success": True, "sale": sale})


@pos_bp.route("/api/printers")
@admin_required
def api_printers():
    return jsonify(rp.list_printers())
