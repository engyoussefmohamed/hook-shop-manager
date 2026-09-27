import os
import sys


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = app_dir()

PER_PAGE = 50
SALES_PER_PAGE = 30

OPEN_ENDPOINTS = {
    "pos.pos", "pos.index",
    "pos.api_product", "pos.api_products_search",
    "pos.api_sale_complete", "pos.api_last_sale",
    "pos.api_day_summary",
    "pos.receipt", "pos.cashier_last_receipt",
    "static", "auth.logout",
    # Returns — cashier can return/exchange without login
    "inventory.returns_page",
    "inventory.api_get_sale",
    "inventory.api_return",
    "inventory.api_exchange",
    "inventory.api_return_all",
    "inventory.api_returns_history",
}
