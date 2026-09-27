from datetime import datetime

from database.connection import get_db


def get_daily_stats(date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS count,
                   COALESCE(SUM(final_total), 0) AS revenue,
                   COALESCE(SUM(discount), 0) AS discount,
                   COALESCE((
                       SELECT SUM(si.total_price - si.cost_price * si.quantity)
                       FROM sale_items si
                       JOIN sales s2 ON s2.id = si.sale_id
                       WHERE date(s2.created_at) = ? AND s2.voided = 0
                   ), 0)
                   - COALESCE(SUM(discount), 0)
                   - COALESCE((
                       SELECT SUM(si2.unit_price * r.quantity - si2.cost_price * r.quantity)
                       FROM returns r
                       JOIN sale_items si2 ON si2.sale_id = r.sale_id AND si2.product_id = r.product_id
                       JOIN sales s3 ON s3.id = r.sale_id
                       WHERE r.return_type IN ('return', 'exchange')
                         AND date(s3.created_at) = ? AND s3.voided = 0
                   ), 0) AS profit
            FROM sales
            WHERE date(created_at) = ? AND voided = 0
        """, (date, date, date)).fetchone()
        return dict(row) if row else {"count": 0, "revenue": 0, "discount": 0, "profit": 0}


def get_payment_summary(date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        rows = conn.execute("""
            SELECT payment_method,
                   COUNT(*) AS count,
                   COALESCE(SUM(final_total), 0) AS total
            FROM sales
            WHERE date(created_at) = ? AND voided = 0
            GROUP BY payment_method
            ORDER BY total DESC
        """, (date,)).fetchall()
        return [dict(r) for r in rows]


def get_sales_by_date(date=None, page=None, per_page=30):
    date = date or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        if page is not None:
            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM sales WHERE date(created_at) = ? AND voided = 0",
                (date,),
            ).fetchone()["cnt"]
            offset = (page - 1) * per_page
            rows = conn.execute(
                "SELECT * FROM sales WHERE date(created_at) = ? AND voided = 0 "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (date, per_page, offset),
            ).fetchall()
            return [dict(r) for r in rows], total

        rows = conn.execute(
            "SELECT * FROM sales WHERE date(created_at) = ? AND voided = 0 ORDER BY created_at DESC",
            (date,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_monthly_revenue():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT strftime('%Y-%m', created_at) AS month,
                   COUNT(*)                      AS count,
                   COALESCE(SUM(final_total), 0) AS revenue
            FROM sales
            WHERE voided = 0
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """).fetchall()
        return [dict(r) for r in rows]


def get_top_products(limit=10):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT si.product_name,
                   SUM(si.quantity)    AS total_qty,
                   SUM(si.total_price) AS total_revenue,
                   SUM(si.total_price - si.cost_price * si.quantity)
                   - SUM(CASE WHEN s.total > 0 THEN si.total_price * s.discount / s.total ELSE 0 END)
                   - COALESCE((
                       SELECT SUM(si2.unit_price * r.quantity - si2.cost_price * r.quantity)
                       FROM returns r
                       JOIN sale_items si2 ON si2.sale_id = r.sale_id AND si2.product_id = r.product_id
                       JOIN sales s2 ON s2.id = r.sale_id
                       WHERE r.product_id = si.product_id
                         AND r.return_type IN ('return', 'exchange')
                         AND s2.voided = 0
                   ), 0) AS total_profit
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.voided = 0
            GROUP BY si.product_name
            ORDER BY total_qty DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_last_30_days():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT date(created_at)              AS day,
                   COALESCE(SUM(final_total), 0) AS revenue,
                   COUNT(*)                      AS count
            FROM sales
            WHERE created_at >= date('now', 'localtime', '-30 days')
              AND voided = 0
            GROUP BY day
            ORDER BY day ASC
        """).fetchall()
        return [dict(r) for r in rows]


def get_all_sales_for_export(date_from=None, date_to=None):
    with get_db() as conn:
        query = """
            SELECT s.id, s.created_at, s.total, s.discount, s.final_total,
                   s.payment_method, s.notes,
                   COALESCE(SUM(si.total_price - si.cost_price * si.quantity), 0)
                   - s.discount
                   - COALESCE((
                       SELECT SUM(si2.unit_price * r.quantity - si2.cost_price * r.quantity)
                       FROM returns r
                       JOIN sale_items si2 ON si2.sale_id = r.sale_id AND si2.product_id = r.product_id
                       WHERE r.sale_id = s.id
                         AND r.return_type IN ('return', 'exchange')
                   ), 0) AS profit
            FROM sales s
            LEFT JOIN sale_items si ON si.sale_id = s.id
            WHERE s.voided = 0
        """
        params = []
        if date_from:
            query += " AND date(s.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date(s.created_at) <= ?"
            params.append(date_to)
        query += " GROUP BY s.id ORDER BY s.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def search_sales(sale_id=None, date_from=None, date_to=None,
                 payment_method=None, product_query=None):
    with get_db() as conn:
        query = """
            SELECT DISTINCT s.*
            FROM sales s
            LEFT JOIN sale_items si ON si.sale_id = s.id
            WHERE s.voided = 0
        """
        params = []
        if sale_id:
            query += " AND s.id = ?"
            params.append(int(sale_id))
        if date_from:
            query += " AND date(s.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date(s.created_at) <= ?"
            params.append(date_to)
        if payment_method:
            query += " AND s.payment_method = ?"
            params.append(payment_method)
        if product_query:
            query += " AND si.product_name LIKE ?"
            params.append(f"%{product_query}%")
        query += " ORDER BY s.created_at DESC LIMIT 300"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_all_receipts(page=1, per_page=30, date_from=None, date_to=None,
                     payment_method=None, sale_id=None, show_voided=False):
    with get_db() as conn:
        where_clauses = []
        params = []
        if not show_voided:
            where_clauses.append("s.voided = 0")
        if sale_id:
            where_clauses.append("s.id = ?")
            params.append(int(sale_id))
        if date_from:
            where_clauses.append("date(s.created_at) >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("date(s.created_at) <= ?")
            params.append(date_to)
        if payment_method:
            where_clauses.append("s.payment_method = ?")
            params.append(payment_method)
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM sales s{where_sql}", params
        ).fetchone()["cnt"]

        offset = (max(1, int(page)) - 1) * int(per_page)
        rows = conn.execute(
            f"SELECT s.* FROM sales s{where_sql} ORDER BY s.created_at DESC LIMIT ? OFFSET ?",
            params + [int(per_page), offset],
        ).fetchall()

        return [dict(r) for r in rows], total


def get_receipts_stats(date_from=None, date_to=None, show_voided=False):
    with get_db() as conn:
        where_clauses = []
        s2_clauses = []
        s3_clauses = []
        params = []
        sub_params = []
        if not show_voided:
            where_clauses.append("s.voided = 0")
            s2_clauses.append("s2.voided = 0")
            s3_clauses.append("s3.voided = 0")
        if date_from:
            where_clauses.append("date(s.created_at) >= ?")
            s2_clauses.append("date(s2.created_at) >= ?")
            s3_clauses.append("date(s3.created_at) >= ?")
            params.append(date_from)
            sub_params.append(date_from)
        if date_to:
            where_clauses.append("date(s.created_at) <= ?")
            s2_clauses.append("date(s2.created_at) <= ?")
            s3_clauses.append("date(s3.created_at) <= ?")
            params.append(date_to)
            sub_params.append(date_to)
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        s2_where = (' WHERE ' + ' AND '.join(s2_clauses)) if s2_clauses else ''
        s3_extra = (' AND ' + ' AND '.join(s3_clauses)) if s3_clauses else ''

        row = conn.execute(f"""
            SELECT COUNT(*) AS count,
                   COALESCE(SUM(s.final_total), 0) AS revenue,
                   COALESCE(SUM(s.discount), 0) AS discount,
                   COALESCE((
                        SELECT SUM(si.total_price - si.cost_price * si.quantity)
                        FROM sale_items si
                        JOIN sales s2 ON s2.id = si.sale_id
                        {s2_where}
                    ), 0)
                    - COALESCE(SUM(s.discount), 0)
                    - COALESCE((
                        SELECT SUM(si2.unit_price * r.quantity - si2.cost_price * r.quantity)
                        FROM returns r
                        JOIN sale_items si2 ON si2.sale_id = r.sale_id AND si2.product_id = r.product_id
                        JOIN sales s3 ON s3.id = r.sale_id
                        WHERE r.return_type IN ('return', 'exchange')
                          {s3_extra}
                    ), 0) AS profit
            FROM sales s{where_sql}
        """, sub_params + sub_params + params).fetchone()
        return dict(row) if row else {"count": 0, "revenue": 0, "discount": 0, "profit": 0}


def get_period_stats(since_date=None):
    with get_db() as conn:
        if since_date:
            f_main = "AND date(created_at) >= ?"
            f_s2   = "AND date(s2.created_at) >= ?"
            f_s3   = "AND date(s3.created_at) >= ?"
            params = [since_date, since_date, since_date]
        else:
            f_main = f_s2 = f_s3 = ""
            params = []

        row = conn.execute(f"""
            SELECT COUNT(*) AS count,
                   COALESCE(SUM(final_total), 0) AS revenue,
                   COALESCE(SUM(discount), 0) AS discount,
                   COALESCE((
                       SELECT SUM(si.total_price - si.cost_price * si.quantity)
                       FROM sale_items si JOIN sales s2 ON s2.id = si.sale_id
                       WHERE s2.voided = 0 {f_s2}
                   ), 0)
                   - COALESCE(SUM(discount), 0)
                   - COALESCE((
                       SELECT SUM(si2.unit_price * r.quantity - si2.cost_price * r.quantity)
                       FROM returns r
                       JOIN sale_items si2 ON si2.sale_id = r.sale_id AND si2.product_id = r.product_id
                       JOIN sales s3 ON s3.id = r.sale_id
                       WHERE r.return_type IN ('return', 'exchange') AND s3.voided = 0 {f_s3}
                   ), 0) AS profit
            FROM sales WHERE voided = 0 {f_main}
        """, params).fetchone()
        return dict(row) if row else {"count": 0, "revenue": 0.0, "discount": 0.0, "profit": 0.0}
