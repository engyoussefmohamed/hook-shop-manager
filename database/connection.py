import logging
import os
import sqlite3
from contextlib import contextmanager

from werkzeug.security import generate_password_hash

from config import APP_DIR

logger = logging.getLogger(__name__)

DB_PATH = APP_DIR + "/shop.db"

_DEFAULT_CATEGORIES = ["تيشرت", "كوتش", "جاكيت", "بنطلون", "قميص"]


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                category    TEXT    DEFAULT 'ملابس',
                price       REAL    NOT NULL,
                cost_price  REAL    DEFAULT 0,
                size        TEXT    DEFAULT '',
                color       TEXT    DEFAULT '',
                quantity    INTEGER DEFAULT 0,
                barcode     TEXT    UNIQUE,
                created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS sales (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                total          REAL NOT NULL,
                discount       REAL DEFAULT 0,
                final_total    REAL NOT NULL,
                payment_method TEXT DEFAULT 'كاش',
                notes          TEXT DEFAULT '',
                created_at     TEXT DEFAULT (datetime('now', 'localtime')),
                voided         INTEGER DEFAULT 0,
                customer_id    INTEGER,
                paid_amount    REAL DEFAULT 0,
                remaining_amount REAL DEFAULT 0,
                tax            REAL DEFAULT 0,
                service        REAL DEFAULT 0,
                discount_type  TEXT DEFAULT 'amount',
                discount_value REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sale_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id      INTEGER NOT NULL,
                product_id   INTEGER,
                product_name TEXT    NOT NULL,
                quantity     INTEGER NOT NULL,
                unit_price   REAL    NOT NULL,
                cost_price   REAL    DEFAULT 0,
                total_price  REAL    NOT NULL,
                FOREIGN KEY (sale_id)    REFERENCES sales(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'cashier',
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER,
                product_name TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                quantity    INTEGER NOT NULL,
                old_quantity INTEGER DEFAULT 0,
                new_quantity INTEGER DEFAULT 0,
                notes       TEXT DEFAULT '',
                ref_type    TEXT DEFAULT '',
                ref_id      INTEGER,
                created_at  TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS customers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                phone       TEXT DEFAULT '',
                notes       TEXT DEFAULT '',
                balance     REAL DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                phone       TEXT DEFAULT '',
                notes       TEXT DEFAULT '',
                balance     REAL DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER,
                total       REAL DEFAULT 0,
                paid        REAL DEFAULT 0,
                notes       TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS purchase_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                product_id  INTEGER,
                product_name TEXT NOT NULL,
                quantity    INTEGER NOT NULL,
                unit_cost   REAL DEFAULT 0,
                total_cost  REAL DEFAULT 0,
                FOREIGN KEY (purchase_id) REFERENCES purchases(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS returns (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id     INTEGER,
                product_id  INTEGER,
                product_name TEXT NOT NULL,
                quantity    INTEGER NOT NULL,
                amount      REAL DEFAULT 0,
                return_type TEXT DEFAULT 'return',
                exchange_product_id INTEGER,
                notes       TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            );

            INSERT OR IGNORE INTO settings (key, value) VALUES ('shop_name',    'محل الملابس');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('shop_address', 'المطرية - القاهرة');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('shop_phone',   '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('backup_path',  '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('low_stock_threshold', '5');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('printer_name', '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('tax_percent', '0');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('service_percent', '0');

            CREATE INDEX IF NOT EXISTS idx_sales_created_at    ON sales(created_at);
            CREATE INDEX IF NOT EXISTS idx_sales_voided        ON sales(voided);
            CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id  ON sale_items(sale_id);
            CREATE INDEX IF NOT EXISTS idx_sale_items_prod_id  ON sale_items(product_id);
            CREATE INDEX IF NOT EXISTS idx_returns_sale_id     ON returns(sale_id);
            CREATE INDEX IF NOT EXISTS idx_returns_product_id  ON returns(product_id);
            CREATE INDEX IF NOT EXISTS idx_movements_prod_id   ON stock_movements(product_id);
            CREATE INDEX IF NOT EXISTS idx_movements_created   ON stock_movements(created_at);
        """)

        for stmt in [
            "ALTER TABLE sales ADD COLUMN voided INTEGER DEFAULT 0",
            "ALTER TABLE sale_items ADD COLUMN cost_price REAL DEFAULT 0",
            "ALTER TABLE sales ADD COLUMN customer_id INTEGER",
            "ALTER TABLE sales ADD COLUMN paid_amount REAL DEFAULT 0",
            "ALTER TABLE sales ADD COLUMN remaining_amount REAL DEFAULT 0",
            "ALTER TABLE sales ADD COLUMN tax REAL DEFAULT 0",
            "ALTER TABLE sales ADD COLUMN service REAL DEFAULT 0",
            "ALTER TABLE sales ADD COLUMN discount_type TEXT DEFAULT 'amount'",
            "ALTER TABLE sales ADD COLUMN discount_value REAL DEFAULT 0",
            "ALTER TABLE products ADD COLUMN min_stock INTEGER DEFAULT 5",
            "ALTER TABLE returns ADD COLUMN affected_balance REAL DEFAULT 0",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        admin_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'"
        ).fetchone()["cnt"]
        if admin_count == 0:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("hook", generate_password_hash("hook66"), "admin"),
            )
            logger.warning(
                "Default admin account created (username: hook, password: hook66). "
                "Please change the password after first login."
            )
            creds_file = os.path.join(APP_DIR, "FIRST_LOGIN.txt")
            try:
                with open(creds_file, "w", encoding="utf-8") as f:
                    f.write("بيانات الدخول الافتراضية للمدير\n")
                    f.write("================================\n")
                    f.write("اسم المستخدم : hook\n")
                    f.write("كلمة السر    : hook66\n\n")
                    f.write("يرجى تغيير كلمة السر فور الدخول الأول من صفحة الإعدادات.\n")
            except Exception:
                pass

        for cat in _DEFAULT_CATEGORIES:
            try:
                conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
            except Exception:
                pass
