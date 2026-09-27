from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import (
    get_customers, add_customer, update_customer, delete_customer, pay_customer_debt,
    get_suppliers, add_supplier, update_supplier, delete_supplier, pay_supplier_debt,
    get_all_products, get_purchases, create_purchase,
)
from helpers import admin_required

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/customers", methods=["GET", "POST"])
@admin_required
def customers_page():
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "add":
            name = request.form.get("name", "").strip()
            if not name:
                flash("اسم العميل مطلوب", "danger")
                return redirect(url_for("customers.customers_page"))
            add_customer(
                name,
                request.form.get("phone", "").strip(),
                request.form.get("notes", "").strip(),
            )
            flash("تم إضافة العميل", "success")
        elif action == "edit":
            cid = request.form.get("id")
            if cid:
                update_customer(
                    int(cid),
                    request.form.get("name", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("notes", "").strip(),
                )
                flash("تم تعديل العميل", "success")
        elif action == "delete":
            cid = request.form.get("id")
            if cid:
                delete_customer(int(cid))
                flash("تم حذف العميل", "success")
        elif action == "pay":
            cid = request.form.get("id")
            amount = request.form.get("amount", 0)
            if cid and amount:
                try:
                    new_bal = pay_customer_debt(int(cid), float(amount))
                    flash(f"تم الدفع. الرصيد المتبقي: {new_bal:.2f} ج", "success")
                except ValueError as e:
                    flash(str(e), "danger")
        return redirect(url_for("customers.customers_page"))
    return render_template("customers.html", customers=get_customers())


@customers_bp.route("/suppliers", methods=["GET", "POST"])
@admin_required
def suppliers_page():
    if request.method == "POST":
        action = request.form.get("action", "supplier")
        if action == "supplier":
            name = request.form.get("name", "").strip()
            if not name:
                flash("اسم المورد مطلوب", "danger")
                return redirect(url_for("customers.suppliers_page"))
            add_supplier(
                name,
                request.form.get("phone", "").strip(),
                request.form.get("notes", "").strip(),
            )
            flash("تم إضافة المورد", "success")
        elif action == "edit":
            sid = request.form.get("id")
            if sid:
                update_supplier(
                    int(sid),
                    request.form.get("name", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("notes", "").strip(),
                )
                flash("تم تعديل المورد", "success")
        elif action == "delete":
            sid = request.form.get("id")
            if sid:
                delete_supplier(int(sid))
                flash("تم حذف المورد", "success")
        elif action == "pay":
            sid = request.form.get("id")
            amount = request.form.get("amount", 0)
            if sid and amount:
                try:
                    new_bal = pay_supplier_debt(int(sid), float(amount))
                    flash(f"تم الدفع. الرصيد المتبقي: {new_bal:.2f} ج", "success")
                except ValueError as e:
                    flash(str(e), "danger")
        elif action == "purchase":
            items = []
            for pid, qty, cost in zip(
                request.form.getlist("product_id"),
                request.form.getlist("quantity"),
                request.form.getlist("unit_cost"),
            ):
                if pid and qty:
                    items.append({
                        "product_id": int(pid),
                        "quantity": int(qty),
                        "unit_cost": float(cost or 0),
                    })
            if items:
                create_purchase(
                    request.form.get("supplier_id") or None, items,
                    float(request.form.get("paid") or 0),
                    request.form.get("notes", ""),
                )
                flash("تم تسجيل المشتريات وتحديث المخزون", "success")
            else:
                flash("أضف منتجات على الأقل", "danger")
        return redirect(url_for("customers.suppliers_page"))
    return render_template(
        "suppliers.html", suppliers=get_suppliers(),
        products=get_all_products(), purchases=get_purchases(),
    )
