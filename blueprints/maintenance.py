import sys

from flask import Blueprint, render_template

from database import init_db, get_settings
from helpers import admin_required
import services.receipt as rp
import services.backup as bk

maintenance_bp = Blueprint("maintenance", __name__)


@maintenance_bp.route("/maintenance")
@admin_required
def maintenance_page():
    checks = []
    try:
        init_db()
        checks.append(("قاعدة البيانات", True, "تم الفحص بنجاح"))
    except Exception as exc:
        checks.append(("قاعدة البيانات", False, str(exc)))

    try:
        printers = rp.list_printers()
        settings = get_settings()
        configured = settings.get("printer_name", "").strip()
        if not rp.WIN32_OK:
            checks.append((
                "الطابعة", False,
                "مكتبة pywin32 غير مثبتة — لا يمكن الوصول للطابعات",
            ))
        elif printers:
            details = f"{len(printers)} طابعة مثبتة: " + ", ".join(printers)
            if configured:
                match = any(configured.lower() == p.lower() for p in printers)
                if match:
                    details += f"\nالطابعة المختارة: {configured} ✓"
                else:
                    details += f"\n⚠ الطابعة '{configured}' غير موجودة بين الطابعات المثبتة"
            else:
                details += "\nلم يتم اختيار طابعة — الفواتور تفتح في المتصفح"
            checks.append(("الطابعة", True, details))
        else:
            checks.append((
                "الطابعة", False,
                "لا توجد طابعات مثبتة في النظام",
            ))
    except Exception as exc:
        checks.append(("الطابعة", False, str(exc)))

    try:
        result = bk.do_backup()
        checks.append((
            "النسخ الاحتياطي", result["success"],
            result.get("path") or result.get("error"),
        ))
    except Exception as exc:
        checks.append(("النسخ الاحتياطي", False, str(exc)))

    checks.append((
        "قارئ الباركود", True,
        "قارئ الباركود يعمل كلوحة مفاتيح — يكفي توصيله بالـ USB "
        "واختباره من شاشة نقطة البيع (امسح أي باركود)",
    ))

    checks.append((
        "بيئة التشغيل", True,
        f"Python {sys.version.split()[0]} | "
        f"pywin32: {'مثبت ✓' if rp.WIN32_OK else 'غير مثبت ✗'}",
    ))

    return render_template("maintenance.html", checks=checks)
