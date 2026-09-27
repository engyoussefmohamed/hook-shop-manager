from database.connection import get_db


def get_all_products(search=None, category=None, page=None, per_page=50):
    with get_db() as conn:
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        if search:
            query += " AND (name LIKE ? OR barcode LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY name"

        if page is not None:
            count_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM products WHERE 1=1"
                + (" AND (name LIKE ? OR barcode LIKE ?)" if search else "")
                + (" AND category = ?" if category else ""),
                params,
            ).fetchone()
            total = count_row["cnt"]
            offset = (page - 1) * per_page
            rows = conn.execute(
                query + " LIMIT ? OFFSET ?", params + [per_page, offset]
            ).fetchall()
            return [dict(r) for r in rows], total

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_product_by_id(product_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return dict(row) if row else None


def get_product_by_barcode(barcode):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE barcode = ?", (barcode,)
        ).fetchone()
        return dict(row) if row else None


def add_product(name, category, price, cost_price, size, color, quantity, barcode, min_stock=5):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO products (name, category, price, cost_price, size, color, quantity, barcode, min_stock) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, category, float(price), float(cost_price), size, color,
             int(quantity), barcode or None, int(min_stock or 5)),
        )
        product_id = cur.lastrowid
        if not barcode:
            auto_barcode = f"{product_id:010d}"
            cur.execute(
                "UPDATE products SET barcode=? WHERE id=?", (auto_barcode, product_id)
            )
        if int(quantity) != 0:
            cur.execute(
                "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, old_quantity, new_quantity, notes) "
                "VALUES (?, ?, 'add', ?, 0, ?, 'إضافة منتج جديد')",
                (product_id, name, int(quantity), int(quantity)),
            )
        return product_id


def update_product(product_id, name, category, price, cost_price, size, color,
                   quantity, barcode, min_stock=5):
    with get_db() as conn:
        old = conn.execute(
            "SELECT name, quantity FROM products WHERE id=?", (product_id,)
        ).fetchone()
        conn.execute(
            "UPDATE products SET name=?, category=?, price=?, cost_price=?, size=?, color=?, quantity=?, barcode=?, min_stock=? "
            "WHERE id=?",
            (name, category, float(price), float(cost_price), size, color,
             int(quantity), barcode or None, int(min_stock or 5), product_id),
        )
        if old and int(old["quantity"]) != int(quantity):
            conn.execute(
                "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, old_quantity, new_quantity, notes) "
                "VALUES (?, ?, 'adjust', ?, ?, ?, 'تعديل بيانات المنتج')",
                (product_id, name, int(quantity) - int(old["quantity"]),
                 int(old["quantity"]), int(quantity)),
            )


def update_product_quantity(product_id, quantity, notes="تعديل كمية يدوي"):
    with get_db() as conn:
        old = conn.execute(
            "SELECT name, quantity FROM products WHERE id=?", (product_id,)
        ).fetchone()
        conn.execute(
            "UPDATE products SET quantity = ? WHERE id = ?", (int(quantity), product_id)
        )
        if old:
            conn.execute(
                "INSERT INTO stock_movements (product_id, product_name, movement_type, quantity, old_quantity, new_quantity, notes) "
                "VALUES (?, ?, 'adjust', ?, ?, ?, ?)",
                (product_id, old["name"], int(quantity) - int(old["quantity"]),
                 int(old["quantity"]), int(quantity), notes),
            )


def delete_product(product_id):
    with get_db() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


def get_low_stock_custom():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE quantity <= COALESCE(min_stock, 5) ORDER BY quantity ASC"
        ).fetchall()
        return [dict(r) for r in rows]
