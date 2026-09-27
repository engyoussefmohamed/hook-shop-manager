from database.connection import get_db
from database.products import get_product_by_id, update_product_quantity


def get_stock_movements(product_id=None, limit=300):
    with get_db() as conn:
        if product_id:
            rows = conn.execute(
                "SELECT * FROM stock_movements WHERE product_id=? ORDER BY created_at DESC LIMIT ?",
                (product_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM stock_movements ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def return_sale_item(sale_id, product_id, quantity, notes=""):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            item = conn.execute(
                "SELECT * FROM sale_items WHERE sale_id=? AND product_id=?",
                (sale_id, product_id),
            ).fetchone()
            if not item:
                raise ValueError("المنتج غير موجود في الفاتورة")
            returned = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS qty FROM returns "
                "WHERE sale_id=? AND product_id=? AND return_type IN ('return', 'exchange')",
                (sale_id, product_id),
            ).fetchone()["qty"]
            qty = int(quantity)
            available_to_return = int(item["quantity"]) - int(returned or 0)
            if qty <= 0 or qty > available_to_return:
                raise ValueError("كمية المرتجع غير صحيحة")

            amount = float(item["unit_price"]) * qty
            returned_item_total = float(item["total_price"]) * qty / int(item["quantity"])

            # حساب affected_balance قبل أي تعديل (كم يتم خصمه فعلاً من رصيد العميل)
            sale_pre = conn.execute(
                "SELECT customer_id, remaining_amount FROM sales WHERE id = ?", (sale_id,)
            ).fetchone()
            affected_balance = 0.0
            if sale_pre and sale_pre["customer_id"] and float(sale_pre["remaining_amount"] or 0) > 0:
                affected_balance = min(returned_item_total, float(sale_pre["remaining_amount"]))

            product = conn.execute(
                "SELECT quantity FROM products WHERE id=?", (product_id,)
            ).fetchone()
            old_qty = int(product["quantity"]) if product else 0
            new_qty = old_qty + qty

            cur.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id=?", (qty, product_id)
            )
            cur.execute(
                "INSERT INTO returns (sale_id, product_id, product_name, quantity, amount, "
                "return_type, notes, affected_balance) "
                "VALUES (?, ?, ?, ?, ?, 'return', ?, ?)",
                (sale_id, product_id, item["product_name"], qty, amount, notes, affected_balance),
            )
            cur.execute(
                "UPDATE sales SET total = total - ?, final_total = final_total - ? WHERE id = ?",
                (returned_item_total, returned_item_total, sale_id),
            )
            if affected_balance > 0:
                cur.execute(
                    "UPDATE customers SET balance = balance - ? WHERE id = ?",
                    (affected_balance, sale_pre["customer_id"]),
                )
                cur.execute(
                    "UPDATE sales SET remaining_amount = remaining_amount - ? WHERE id = ?",
                    (affected_balance, sale_id),
                )
            cur.execute(
                "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, "
                "old_quantity, new_quantity, notes, ref_type, ref_id) "
                "VALUES (?, ?, 'return', ?, ?, ?, ?, 'sale_return', ?)",
                (product_id, item["product_name"], qty, old_qty, new_qty,
                 f"مرتجع من فاتورة #{sale_id}", sale_id),
            )
            return True, f"تم إرجاع {qty} من {item['product_name']}"
    except Exception as exc:
        return False, str(exc)


def exchange_sale_item(sale_id, old_product_id, new_product_id, quantity, notes=""):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            qty = int(quantity)
            old_item = conn.execute(
                "SELECT * FROM sale_items WHERE sale_id=? AND product_id=?",
                (sale_id, old_product_id),
            ).fetchone()
            new_product = conn.execute(
                "SELECT * FROM products WHERE id=?", (new_product_id,)
            ).fetchone()
            if not old_item or not new_product:
                raise ValueError("بيانات الاستبدال غير صحيحة")
            returned = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS qty FROM returns "
                "WHERE sale_id=? AND product_id=? AND return_type IN ('return', 'exchange')",
                (sale_id, old_product_id),
            ).fetchone()["qty"]
            available_to_exchange = int(old_item["quantity"]) - int(returned or 0)
            if qty <= 0 or qty > available_to_exchange:
                raise ValueError("كمية الاستبدال غير صحيحة")
            if int(new_product["quantity"]) < qty:
                raise ValueError(
                    f"المخزون غير كافي للمنتج الجديد '{new_product['name']}'"
                )

            old_prod = conn.execute(
                "SELECT quantity FROM products WHERE id=?", (old_product_id,)
            ).fetchone()
            old_before = int(old_prod["quantity"]) if old_prod else 0
            new_before = int(new_product["quantity"])

            cur.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id=?",
                (qty, old_product_id),
            )
            cur.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id=?",
                (qty, new_product_id),
            )
            diff = (float(new_product["price"]) - float(old_item["unit_price"])) * qty
            cur.execute(
                "INSERT INTO returns (sale_id, product_id, product_name, quantity, amount, "
                "return_type, exchange_product_id, notes) "
                "VALUES (?, ?, ?, ?, ?, 'exchange', ?, ?)",
                (sale_id, old_product_id, old_item["product_name"], qty, diff,
                 new_product_id, notes),
            )
            # update sale total and customer credit balance for the exchange price difference
            if diff != 0:
                cur.execute(
                    "UPDATE sales SET total = total + ?, final_total = final_total + ? WHERE id = ?",
                    (diff, diff, sale_id),
                )
                sale_row = conn.execute(
                    "SELECT customer_id, remaining_amount FROM sales WHERE id = ?", (sale_id,)
                ).fetchone()
                if sale_row and sale_row["customer_id"]:
                    old_rem = float(sale_row["remaining_amount"] or 0)
                    new_rem = max(0.0, old_rem + diff)
                    actual_change = new_rem - old_rem
                    if actual_change != 0:
                        cur.execute(
                            "UPDATE sales SET remaining_amount = ? WHERE id = ?",
                            (new_rem, sale_id),
                        )
                        cur.execute(
                            "UPDATE customers SET balance = balance + ? WHERE id = ?",
                            (actual_change, sale_row["customer_id"]),
                        )
            cur.execute(
                "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, "
                "old_quantity, new_quantity, notes, ref_type, ref_id) "
                "VALUES (?, ?, 'exchange_in', ?, ?, ?, ?, 'exchange', ?)",
                (old_product_id, old_item["product_name"], qty, old_before,
                 old_before + qty, f"استبدال من فاتورة #{sale_id}", sale_id),
            )
            cur.execute(
                "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, "
                "old_quantity, new_quantity, notes, ref_type, ref_id) "
                "VALUES (?, ?, 'exchange_out', ?, ?, ?, ?, 'exchange', ?)",
                (new_product_id, new_product["name"], -qty, new_before,
                 new_before - qty, f"استبدال من فاتورة #{sale_id}", sale_id),
            )
            return True, f"تم الاستبدال. فرق السعر: {diff:.2f} ج"
    except Exception as exc:
        return False, str(exc)


def get_returns(limit=200):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM returns ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_sale_with_return_status(sale_id):
    with get_db() as conn:
        sale = conn.execute(
            "SELECT * FROM sales WHERE id = ?", (sale_id,)
        ).fetchone()
        if not sale:
            return None
        sale = dict(sale)
        items = conn.execute(
            "SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)
        ).fetchall()
        sale["items"] = []
        for item in items:
            d = dict(item)
            returned = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS qty FROM returns "
                "WHERE sale_id=? AND product_id=? AND return_type IN ('return', 'exchange')",
                (sale_id, d["product_id"]),
            ).fetchone()["qty"]
            d["already_returned"] = int(returned or 0)
            d["available_to_return"] = int(d["quantity"]) - d["already_returned"]
            d["returned_amount"] = d["already_returned"] * float(d["unit_price"])
            sale["items"].append(d)
        total_returned = sum(i["returned_amount"] for i in sale["items"])
        total_original = sum(float(i["unit_price"]) * int(i["quantity"]) for i in sale["items"])
        sale["total_returned_amount"] = total_returned
        sale["total_original_amount"] = total_original
        sale["remaining_amount_calc"] = total_original - total_returned
        return sale


def get_returns_paginated(page=1, per_page=20, search="", date_from="", date_to=""):
    with get_db() as conn:
        where_clauses = []
        params = []
        if search:
            where_clauses.append("(r.product_name LIKE ? OR CAST(r.sale_id AS TEXT) LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if date_from:
            where_clauses.append("r.created_at >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("r.created_at <= ?")
            params.append(date_to + " 23:59:59")
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        total = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM returns r{where_sql}", params
        ).fetchone()["cnt"]
        offset = (max(1, int(page)) - 1) * int(per_page)
        rows = conn.execute(
            f"SELECT r.* FROM returns r{where_sql} ORDER BY r.created_at DESC LIMIT ? OFFSET ?",
            params + [int(per_page), offset],
        ).fetchall()
        return {
            "returns": [dict(r) for r in rows],
            "total": total,
            "page": int(page),
            "per_page": int(per_page),
            "total_pages": max(1, -(-total // int(per_page))),
        }


def undo_return(return_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            ret = conn.execute(
                "SELECT * FROM returns WHERE id=?", (return_id,)
            ).fetchone()
            if not ret:
                raise ValueError("عملية المرتجع غير موجودة")
            ret = dict(ret)
            product_id = ret["product_id"]
            qty = int(ret["quantity"])
            return_type = ret["return_type"]
            sale_id = ret["sale_id"]

            product = conn.execute(
                "SELECT quantity FROM products WHERE id=?", (product_id,)
            ).fetchone()
            if not product:
                raise ValueError("المنتج غير موجود")
            old_qty = int(product["quantity"])
            new_qty = old_qty - qty
            if new_qty < 0:
                raise ValueError("لا يمكن التراجع - المخزون لا يكفي")

            cur.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id=?", (qty, product_id)
            )

            if return_type == "exchange" and ret.get("exchange_product_id"):
                new_pid = ret["exchange_product_id"]
                new_prod = conn.execute(
                    "SELECT quantity, name FROM products WHERE id=?", (new_pid,)
                ).fetchone()
                if new_prod:
                    new_prod_old = int(new_prod["quantity"])
                    cur.execute(
                        "UPDATE products SET quantity = quantity + ? WHERE id=?",
                        (qty, new_pid),
                    )
                    cur.execute(
                        "INSERT INTO stock_movements (product_id, product_name, movement_type, "
                        "quantity, old_quantity, new_quantity, notes, ref_type, ref_id) "
                        "VALUES (?, ?, 'exchange_in', ?, ?, ?, ?, 'exchange', ?)",
                        (new_pid, new_prod["name"], qty, new_prod_old,
                         new_prod_old + qty, f"تراجع استبدال مرتجع #{return_id}", sale_id),
                    )

            cur.execute(
                "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, "
                "old_quantity, new_quantity, notes, ref_type, ref_id) "
                "VALUES (?, ?, 'sale', ?, ?, ?, ?, 'sale_return', ?)",
                (product_id, ret["product_name"], -qty, old_qty, new_qty,
                 f"تراجع مرتجع #{return_id} فاتورة #{sale_id}", sale_id),
            )

            cur.execute("DELETE FROM returns WHERE id=?", (return_id,))

            if return_type == "exchange":
                # during exchange diff was ADDED to sale total; undo must subtract it
                ret_amount = -float(ret["amount"])
            else:
                # during return, returned_item_total was deducted (= total_price * qty / orig_qty)
                # recalculate from sale_items to get the exact amount that was removed
                item_row = conn.execute(
                    "SELECT total_price, quantity FROM sale_items WHERE sale_id=? AND product_id=?",
                    (sale_id, ret["product_id"]),
                ).fetchone()
                if item_row and int(item_row["quantity"]) > 0:
                    ret_amount = float(item_row["total_price"]) * qty / int(item_row["quantity"])
                else:
                    ret_amount = float(ret["amount"])
            cur.execute(
                "UPDATE sales SET total = total + ?, final_total = final_total + ? WHERE id = ?",
                (ret_amount, ret_amount, sale_id),
            )

            # استخدام affected_balance المخزون عند الإرجاع الأصلي لضمان الدقة
            affected = float(ret.get("affected_balance") or 0)
            orig_sale = conn.execute(
                "SELECT customer_id FROM sales WHERE id = ?", (sale_id,)
            ).fetchone()
            if orig_sale and orig_sale["customer_id"] and affected > 0:
                cur.execute(
                    "UPDATE customers SET balance = balance + ? WHERE id = ?",
                    (affected, orig_sale["customer_id"]),
                )
                cur.execute(
                    "UPDATE sales SET remaining_amount = remaining_amount + ? WHERE id = ?",
                    (affected, sale_id),
                )

            return True, "تم التراجع عن عملية المرتجع"
    except Exception as exc:
        return False, str(exc)


def inventory_adjust(product_id, actual_quantity, notes="جرد سريع"):
    product = get_product_by_id(product_id)
    if not product:
        return False, "المنتج غير موجود"
    update_product_quantity(product_id, int(actual_quantity), notes)
    diff = int(actual_quantity) - int(product["quantity"])
    return True, f"تم الجرد. الفرق: {diff}"


def create_purchase(supplier_id, items, paid=0, notes=""):
    with get_db() as conn:
        try:
            cur = conn.cursor()
            total = sum(
                float(i.get("unit_cost", 0)) * int(i.get("quantity", 0))
                for i in items
            )
            cur.execute(
                "INSERT INTO purchases (supplier_id, total, paid, notes) VALUES (?, ?, ?, ?)",
                (supplier_id, total, paid, notes),
            )
            purchase_id = cur.lastrowid
            if supplier_id:
                cur.execute(
                    "UPDATE suppliers SET balance = balance + ? WHERE id=?",
                    (total - float(paid), supplier_id),
                )
            for item in items:
                pid = item.get("product_id")
                qty = int(item.get("quantity", 0))
                cost = float(item.get("unit_cost", 0))
                if qty <= 0:
                    continue
                product = conn.execute(
                    "SELECT * FROM products WHERE id=?", (pid,)
                ).fetchone()
                if not product:
                    raise ValueError("منتج غير موجود في المشتريات")
                old_qty = int(product["quantity"])
                new_qty = old_qty + qty
                cur.execute(
                    "UPDATE products SET quantity=?, cost_price=? WHERE id=?",
                    (new_qty, cost, pid),
                )
                cur.execute(
                    "INSERT INTO purchase_items (purchase_id, product_id, product_name, "
                    "quantity, unit_cost, total_cost) VALUES (?, ?, ?, ?, ?, ?)",
                    (purchase_id, pid, product["name"], qty, cost, qty * cost),
                )
                cur.execute(
                    "INSERT INTO stock_movements (product_id, product_name, movement_type, "
                    "quantity, old_quantity, new_quantity, notes, ref_type, ref_id) "
                    "VALUES (?, ?, 'purchase', ?, ?, ?, ?, 'purchase', ?)",
                    (pid, product["name"], qty, old_qty, new_qty,
                     f"مشتريات #{purchase_id}", purchase_id),
                )
            return purchase_id
        except Exception:
            raise


def get_purchases(limit=200):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.*, s.name AS supplier_name
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            ORDER BY p.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
