from database.connection import get_db


def get_settings():
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def save_setting(key, value):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


def get_categories():
    with get_db() as conn:
        rows = conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
        return [r["name"] for r in rows]


def add_category(name):
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))


def delete_category(name):
    with get_db() as conn:
        conn.execute("DELETE FROM categories WHERE name = ?", (name,))
