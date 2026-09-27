import os

from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

try:
    import win32print
    import win32ui
    from PIL import ImageWin
    WIN32_OK = True
except ImportError:
    WIN32_OK = False

RECEIPT_W = 550


def _ar(text):
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def _font(size):
    for path in [
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _center_x(draw, text, font, width):
    bb = draw.textbbox((0, 0), text, font=font)
    return (width - (bb[2] - bb[0])) // 2


def _right_x(draw, text, font, width, margin=20):
    bb = draw.textbbox((0, 0), text, font=font)
    return width - (bb[2] - bb[0]) - margin


def generate_receipt_image(sale, settings):
    shop_name    = settings.get("shop_name", "المتجر")
    shop_address = settings.get("shop_address", "")
    shop_phone   = settings.get("shop_phone", "")
    items        = sale.get("items", [])

    LINE = 32
    height = 220 + len(items) * LINE + 340
    img  = Image.new("RGB", (RECEIPT_W, height), "white")
    draw = ImageDraw.Draw(img)

    fL = _font(30)
    fM = _font(22)
    fS = _font(18)
    fB = _font(26)

    y = 20

    name_txt = _ar(shop_name)
    draw.text((_center_x(draw, name_txt, fL, RECEIPT_W), y), name_txt, font=fL, fill="black")
    y += 38

    if shop_address:
        t = _ar(shop_address)
        draw.text((_center_x(draw, t, fS, RECEIPT_W), y), t, font=fS, fill="#555")
        y += 24
    if shop_phone:
        t = _ar(f"تليفون: {shop_phone}")
        draw.text((_center_x(draw, t, fS, RECEIPT_W), y), t, font=fS, fill="#555")
        y += 24

    def divider(dashed=False):
        nonlocal y
        y += 6
        if dashed:
            for x in range(20, RECEIPT_W - 20, 8):
                draw.line([(x, y), (x + 4, y)], fill="#aaa", width=1)
        else:
            draw.line([(20, y), (RECEIPT_W - 20, y)], fill="black", width=1)
        y += 8

    divider()

    def meta_row(label, value):
        nonlocal y
        draw.text((_right_x(draw, _ar(label), fS, RECEIPT_W), y), _ar(label), font=fS, fill="#777")
        draw.text((20, y), value, font=fS, fill="black")
        y += 24

    meta_row("رقم الفاتورة", f"#{sale['id']}")
    meta_row("التاريخ",      sale["created_at"][:16])
    meta_row("طريقة الدفع", sale["payment_method"])

    divider()

    draw.text((470, y), _ar("الإجمالي"), font=fS, fill="#999")
    draw.text((390, y), _ar("السعر"),    font=fS, fill="#999")
    draw.text((330, y), _ar("الكمية"),   font=fS, fill="#999")
    draw.text((20,  y), _ar("المنتج"),   font=fS, fill="#999")
    y += 24
    divider(dashed=True)

    for item in items:
        name_r = _ar(item["product_name"])
        draw.text((20,  y), name_r,                       font=fM, fill="black")
        draw.text((330, y), str(item["quantity"]),         font=fM, fill="black")
        draw.text((385, y), f"{item['unit_price']:.2f}",  font=fM, fill="black")
        draw.text((460, y), f"{item['total_price']:.2f}", font=fM, fill="black")
        y += LINE

    divider()

    sub_label = _ar("المجموع الفرعي")
    sub_val   = f"{sale['total']:.2f} ج"
    draw.text((_right_x(draw, sub_label, fS, RECEIPT_W), y), sub_label, font=fS, fill="#777")
    draw.text((20, y), sub_val, font=fS, fill="black")
    y += 24

    if sale.get("discount", 0) > 0:
        disc_label = _ar("الخصم")
        disc_val   = f"- {sale['discount']:.2f} ج"
        draw.text((_right_x(draw, disc_label, fS, RECEIPT_W), y), disc_label, font=fS, fill="#e53e3e")
        draw.text((20, y), disc_val, font=fS, fill="#e53e3e")
        y += 24

    draw.line([(20, y), (RECEIPT_W - 20, y)], fill="black", width=2)
    y += 8

    total_label = _ar("الإجمالي")
    total_v     = f"{sale['final_total']:.2f} ج"
    draw.text((_right_x(draw, total_label, fB, RECEIPT_W), y), total_label, font=fB, fill="black")
    draw.text((20, y), total_v, font=fB, fill="black")
    y += 40

    paid_label = _ar("المدفوع")
    paid_v     = f"{sale.get('paid_amount', sale['final_total']):.2f} ج"
    draw.text((_right_x(draw, paid_label, fS, RECEIPT_W), y), paid_label, font=fS, fill="#777")
    draw.text((20, y), paid_v, font=fS, fill="black")
    y += 24

    remaining = sale.get("remaining_amount", 0)
    if remaining and float(remaining) > 0:
        rem_label = _ar("المتبقي")
        rem_v     = f"{float(remaining):.2f} ج"
        draw.text((_right_x(draw, rem_label, fS, RECEIPT_W), y), rem_label, font=fS, fill="#e53e3e")
        draw.text((20, y), rem_v, font=fS, fill="#e53e3e")
        y += 24

    notes = sale.get("notes", "")
    if notes:
        notes_label = _ar("ملاحظة")
        notes_val   = _ar(str(notes))
        draw.text((_right_x(draw, notes_label, fS, RECEIPT_W), y), notes_label, font=fS, fill="#777")
        draw.text((20, y), notes_val, font=fS, fill="black")
        y += 24

    divider(dashed=True)

    footer = _ar("شكراً لتسوقك منا!")
    draw.text((_center_x(draw, footer, fS, RECEIPT_W), y), footer, font=fS, fill="#aaa")
    y += 30

    return_policy   = settings.get("return_policy",   "مرتجع خلال يومين من تاريخ الفاتورة")
    exchange_policy = settings.get("exchange_policy", "استبدال خلال 14 يوم من تاريخ الفاتورة")

    if return_policy or exchange_policy:
        divider(dashed=True)

        policy_title = _ar("سياسة الاسترجاع والاستبدال")
        draw.text((_center_x(draw, policy_title, fS, RECEIPT_W), y), policy_title, font=fS, fill="#444")
        y += 26

        if return_policy:
            line1 = _ar(return_policy)
            draw.text((_center_x(draw, line1, fS, RECEIPT_W), y), line1, font=fS, fill="#333")
            y += 24

        if exchange_policy:
            line2 = _ar(exchange_policy)
            draw.text((_center_x(draw, line2, fS, RECEIPT_W), y), line2, font=fS, fill="#333")

    return img


def list_printers():
    if not WIN32_OK:
        return []
    try:
        return [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []


def get_effective_printer(settings):
    """Return the printer to use: explicitly configured > Windows default > None."""
    name = (settings.get("printer_name") or "").strip()
    if name:
        return name
    if not WIN32_OK:
        return None
    try:
        return win32print.GetDefaultPrinter() or None
    except Exception:
        return None


def print_receipt(sale, settings):
    if not WIN32_OK:
        return False, "pywin32 غير مثبت"

    printer_name = get_effective_printer(settings)
    if not printer_name:
        return False, "لا توجد طابعة متصلة — اختر طابعة من الإعدادات"

    try:
        img = generate_receipt_image(sale, settings)

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        hdc.StartDoc("Receipt")
        hdc.StartPage()

        pw = hdc.GetDeviceCaps(110)
        ph = hdc.GetDeviceCaps(111)
        scale      = pw / img.width
        new_height = int(img.height * scale)

        img_scaled = img.resize((pw, new_height), Image.LANCZOS)
        dib = ImageWin.Dib(img_scaled)
        dib.draw(hdc.GetHandleOutput(), (0, 0, pw, new_height))

        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
        return True, "تمت الطباعة"

    except Exception as e:
        return False, str(e)
