from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from database import (
    get_sale, get_all_products, get_returns, get_stock_movements,
    return_sale_item, exchange_sale_item, inventory_adjust,
    get_product_by_barcode, get_product_by_id, void_sale,
    get_sale_with_return_status, get_returns_paginated, undo_return,
)
from helpers import admin_required, is_admin

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/returns", methods=["GET", "POST"])
def returns_page():
    sale = None
    if request.method == "POST":
        action  = request.form.get("action")
        sale_id = request.form.get("sale_id")
        notes   = request.form.get("notes", "")

        if action == "return_all":
            sale_data = get_sale_with_return_status(sale_id)
            if sale_data:
                returned_count = 0
                for item in sale_data.get("items", []):
                    qty = item.get("available_to_return", 0)
                    if qty <= 0:
                        continue
                    ok, _ = return_sale_item(
                        sale_id, item["product_id"],
                        qty, notes or "إرجاع كامل للفاتورة"
                    )
                    if ok:
                        returned_count += 1
                if returned_count:
                    flash(f"تم إرجاع كل المنتجات ({returned_count} منتج)", "success")
                else:
                    flash("لم يتم إرجاع أي منتج (تم الإرجاع مسبقاً أو خطأ)", "danger")
            else:
                flash("الفاتورة غير موجودة", "danger")
            return redirect(url_for("inventory.returns_page", sale_id=sale_id))

        elif action == "void":
            if not is_admin():
                flash("هذه الصلاحية للمدير فقط", "danger")
                return redirect(url_for("inventory.returns_page", sale_id=sale_id))
            ok, msg = void_sale(sale_id)
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("inventory.returns_page", sale_id=sale_id))

        elif action == "return":
            qty = request.form.get("quantity", 1)
            ok, msg = return_sale_item(
                sale_id, request.form.get("product_id"), qty, notes
            )
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("inventory.returns_page", sale_id=sale_id))

        elif action == "exchange":
            qty = request.form.get("quantity", 1)
            ok, msg = exchange_sale_item(
                sale_id, request.form.get("product_id"),
                request.form.get("new_product_id"), qty, notes,
            )
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("inventory.returns_page", sale_id=sale_id))

    sale_id = request.args.get("sale_id", "").strip()
    if sale_id:
        sale = get_sale(sale_id)
        if not sale:
            flash("الفاتورة غير موجودة", "danger")
    return render_template(
        "returns.html", sale=sale, returns=get_returns(),
        products=get_all_products(), sale_id=sale_id,
    )


@inventory_bp.route("/api/returns/sale/<sale_id>")
def api_get_sale(sale_id):
    sale = get_sale_with_return_status(sale_id)
    if not sale:
        return jsonify({"success": False, "error": "الفاتورة غير موجودة"})
    return jsonify({"success": True, "sale": sale})


@inventory_bp.route("/api/returns/return", methods=["POST"])
def api_return():
    data = request.get_json(silent=True) or {}
    sale_id = data.get("sale_id") or request.form.get("sale_id")
    product_id = data.get("product_id") or request.form.get("product_id")
    quantity = data.get("quantity") or request.form.get("quantity", 1)
    notes = data.get("notes", "")
    if not sale_id or not product_id:
        return jsonify({"success": False, "error": "بيانات ناقصة"})
    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "كمية غير صحيحة"})
    ok, msg = return_sale_item(sale_id, product_id, quantity, notes)
    return jsonify({"success": ok, "message": msg})


@inventory_bp.route("/api/returns/exchange", methods=["POST"])
def api_exchange():
    data = request.get_json(silent=True) or {}
    sale_id = data.get("sale_id") or request.form.get("sale_id")
    product_id = data.get("product_id") or request.form.get("product_id")
    new_product_id = data.get("new_product_id") or request.form.get("new_product_id")
    quantity = data.get("quantity") or request.form.get("quantity", 1)
    notes = data.get("notes", "")
    if not sale_id or not product_id or not new_product_id:
        return jsonify({"success": False, "error": "بيانات ناقصة"})
    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "كمية غير صحيحة"})
    ok, msg = exchange_sale_item(sale_id, product_id, new_product_id, quantity, notes)
    return jsonify({"success": ok, "message": msg})


@inventory_bp.route("/api/returns/void", methods=["POST"])
def api_void():
    if not is_admin():
        return jsonify({"success": False, "error": "هذه الصلاحية للمدير فقط"}), 403
    data = request.get_json(silent=True) or {}
    sale_id = data.get("sale_id") or request.form.get("sale_id")
    if not sale_id:
        return jsonify({"success": False, "error": "رقم الفاتورة مطلوب"})
    ok, msg = void_sale(sale_id)
    return jsonify({"success": ok, "message": msg})


@inventory_bp.route("/api/returns/return-all", methods=["POST"])
def api_return_all():
    data = request.get_json(silent=True) or {}
    sale_id = data.get("sale_id") or request.form.get("sale_id")
    notes = data.get("notes", "إرجاع كامل للفاتورة")
    if not sale_id:
        return jsonify({"success": False, "error": "رقم الفاتورة مطلوب"})
    sale_data = get_sale_with_return_status(sale_id)
    if not sale_data:
        return jsonify({"success": False, "error": "الفاتورة غير موجودة"})
    returned_count = 0
    for item in sale_data.get("items", []):
        qty = item.get("available_to_return", 0)
        if qty <= 0:
            continue
        ok, _ = return_sale_item(
            sale_id, item["product_id"],
            qty, notes
        )
        if ok:
            returned_count += 1
    if returned_count:
        return jsonify({"success": True, "message": f"تم إرجاع كل المنتجات ({returned_count} منتج)"})
    return jsonify({"success": False, "error": "لم يتم إرجاع أي منتج (تم الإرجاع مسبقاً أو خطأ)"})


@inventory_bp.route("/api/returns/undo", methods=["POST"])
def api_undo():
    if not is_admin():
        return jsonify({"success": False, "error": "هذه الصلاحية للمدير فقط"}), 403
    data = request.get_json(silent=True) or {}
    return_id = data.get("return_id") or request.form.get("return_id")
    if not return_id:
        return jsonify({"success": False, "error": "رقم العملية مطلوب"})
    ok, msg = undo_return(return_id)
    return jsonify({"success": ok, "message": msg})


@inventory_bp.route("/api/returns/history")
def api_returns_history():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    result = get_returns_paginated(page, per_page, search, date_from, date_to)
    return jsonify({"success": True, **result})


@inventory_bp.route("/inventory", methods=["GET", "POST"])
@admin_required
def inventory_page():
    scanned = None
    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        actual  = request.form.get("actual_quantity", "").strip()
        product = get_product_by_barcode(barcode) or (
            get_product_by_id(int(barcode)) if barcode.isdigit() else None
        )
        if not product:
            flash("المنتج غير موجود", "danger")
        elif actual:
            ok, msg = inventory_adjust(product["id"], actual)
            flash(msg, "success" if ok else "danger")
        else:
            scanned = product
    return render_template(
        "inventory.html", scanned=scanned,
        movements=get_stock_movements(limit=80),
    )


@inventory_bp.route("/stock")
@admin_required
def stock_page():
    product_id = request.args.get("product_id", "").strip()
    products   = get_all_products()
    movements  = get_stock_movements(
        int(product_id) if product_id.isdigit() else None
    )
    return render_template(
        "stock.html", movements=movements, products=products,
        selected_product_id=product_id,
    )
