from database.connection import get_db


def create_sale(items, total, discount, final_total, payment_method, notes="",
                customer_id=None, paid_amount=None, tax=0, service=0,
                discount_type="amount", discount_value=0):
    with get_db() as conn:
        cur = conn.cursor()
        normalized_items = []
        for item in items:
            product_id = item.get("product_id")
            qty = int(item.get("quantity", 0))
            if qty <= 0:
                raise ValueError("كمية غير صحيحة في السلة")
            product = None
            if product_id:
                product = conn.execute(
                    "SELECT name, quantity, price, cost_price FROM products WHERE id = ?",
                    (product_id,),
                ).fetchone()
                if not product:
                    raise ValueError("منتج غير موجود في السلة")
                if product["quantity"] < qty:
                    raise ValueError(
                        f"المخزون غير كافي للمنتج '{product['name']}' "
                        f"(المتاح: {product['quantity']}, المطلوب: {qty})"
                    )
            normalized_items.append((item, qty, product))

        # cap discount to total so sales.discount never exceeds sales.total
        total   = float(total)
        discount = min(float(discount), total)

        paid = final_total if paid_amount is None else float(paid_amount)
        remaining = max(0, float(final_total) - paid)
        cur.execute(
            "INSERT INTO sales (total, discount, final_total, payment_method, notes, customer_id, paid_amount, remaining_amount, tax, service, discount_type, discount_value) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (total, discount, final_total, payment_method, notes, customer_id,
             paid, remaining, tax, service, discount_type, discount_value),
        )
        sale_id = cur.lastrowid
        if customer_id and remaining > 0:
            cur.execute(
                "UPDATE customers SET balance = balance + ? WHERE id = ?",
                (remaining, customer_id),
            )
        for item, qty, product in normalized_items:
            product_id = item.get("product_id")
            # always use server-side price to prevent client price manipulation
            if product_id and product:
                unit_price  = float(product["price"])
                cost_price  = float(product["cost_price"] or 0)
            else:
                unit_price  = float(item["unit_price"])
                cost_price  = float(item.get("cost_price", 0))
            total_price = unit_price * qty
            cur.execute(
                "INSERT INTO sale_items (sale_id, product_id, product_name, quantity, unit_price, cost_price, total_price) "
                "VALUES (?,?,?,?,?,?,?)",
                (sale_id, product_id, item["product_name"], qty, unit_price,
                 cost_price, total_price),
            )
            if product_id:
                cur.execute(
                    "UPDATE products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
                    (qty, product_id, qty),
                )
                if cur.rowcount != 1:
                    raise ValueError(
                        f"تعذر تحديث مخزون المنتج '{item['product_name']}'"
                    )
                product = conn.execute(
                    "SELECT quantity FROM products WHERE id = ?", (product_id,)
                ).fetchone()
                cur.execute(
                    "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, old_quantity, new_quantity, notes, ref_type, ref_id) "
                    "VALUES (?, ?, 'sale', ?, ?, ?, ?, 'sale', ?)",
                    (product_id, item["product_name"], -qty,
                     int(product["quantity"]) + qty, int(product["quantity"]),
                     f"بيع فاتورة #{sale_id}", sale_id),
                )
        return sale_id


def get_sale(sale_id):
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
        sale["items"] = [dict(i) for i in items]
        return sale


def get_last_sale():
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM sales WHERE voided = 0 ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
    return get_sale(row["id"])


def void_sale(sale_id):
    with get_db() as conn:
        sale = conn.execute(
            "SELECT * FROM sales WHERE id = ? AND voided = 0", (sale_id,)
        ).fetchone()
        if not sale:
            return False, "الفاتورة غير موجودة أو ملغاة بالفعل"

        items = conn.execute(
            "SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)
        ).fetchall()
        cur = conn.cursor()
        for item in items:
            if item["product_id"]:
                cur.execute(
                    "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                    (item["quantity"], item["product_id"]),
                )
                prod = conn.execute(
                    "SELECT quantity FROM products WHERE id = ?", (item["product_id"],)
                ).fetchone()
                cur.execute(
                    "INSERT INTO stock_movements (product_id, product_name, movement_type, "
                    "quantity, old_quantity, new_quantity, notes, ref_type, ref_id) "
                    "VALUES (?, ?, 'void', ?, ?, ?, ?, 'sale', ?)",
                    (item["product_id"], item["product_name"], item["quantity"],
                     int(prod["quantity"]) - item["quantity"], int(prod["quantity"]),
                     f"إلغاء فاتورة #{sale_id}", sale_id),
                )

        if sale["customer_id"] and sale["remaining_amount"] > 0:
            conn.execute(
                "UPDATE customers SET balance = balance - ? WHERE id = ?",
                (sale["remaining_amount"], sale["customer_id"]),
            )

        conn.execute(
            "UPDATE sales SET voided = 1 WHERE id = ?", (sale_id,)
        )
        return True, "تم إلغاء الفاتورة واسترجاع المخزون"
