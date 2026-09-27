from database.connection import get_db


def get_customers():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def add_customer(name, phone="", notes=""):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, notes) VALUES (?, ?, ?)",
            (name, phone, notes),
        )
        return cur.lastrowid


def update_customer(cid, name, phone="", notes=""):
    with get_db() as conn:
        conn.execute(
            "UPDATE customers SET name=?, phone=?, notes=? WHERE id=?",
            (name, phone, notes, cid),
        )


def delete_customer(cid):
    with get_db() as conn:
        conn.execute("DELETE FROM customers WHERE id=?", (cid,))


def pay_customer_debt(cid, amount):
    with get_db() as conn:
        customer = conn.execute("SELECT balance FROM customers WHERE id=?", (cid,)).fetchone()
        if not customer:
            raise ValueError("العميل غير موجود")
        balance = float(customer["balance"])
        amount  = float(amount)
        if amount <= 0:
            raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
        if amount > balance:
            raise ValueError(f"المبلغ ({amount:.2f} ج) أكبر من الرصيد ({balance:.2f} ج)")
        new_balance = balance - amount
        conn.execute("UPDATE customers SET balance=? WHERE id=?", (new_balance, cid))
        return new_balance


def get_suppliers():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def add_supplier(name, phone="", notes=""):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO suppliers (name, phone, notes) VALUES (?, ?, ?)",
            (name, phone, notes),
        )
        return cur.lastrowid


def update_supplier(sid, name, phone="", notes=""):
    with get_db() as conn:
        conn.execute(
            "UPDATE suppliers SET name=?, phone=?, notes=? WHERE id=?",
            (name, phone, notes, sid),
        )


def delete_supplier(sid):
    with get_db() as conn:
        conn.execute("DELETE FROM suppliers WHERE id=?", (sid,))


def pay_supplier_debt(sid, amount):
    with get_db() as conn:
        supplier = conn.execute("SELECT balance FROM suppliers WHERE id=?", (sid,)).fetchone()
        if not supplier:
            raise ValueError("المورد غير موجود")
        new_balance = max(0, float(supplier["balance"]) - float(amount))
        conn.execute("UPDATE suppliers SET balance=? WHERE id=?", (new_balance, sid))
        return new_balance
