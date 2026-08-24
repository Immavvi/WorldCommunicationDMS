from decimal import Decimal


def indian_number(value, places=2):
    number = f"{abs(Decimal(value)):.{places}f}"
    whole, fraction = number.split(".")
    grouped = whole[-3:]
    remaining = whole[:-3]
    while remaining:
        grouped = f"{remaining[-2:]},{grouped}"
        remaining = remaining[:-2]
    sign = "-" if Decimal(value) < 0 else ""
    return f"{sign}{grouped}.{fraction}"


def currency(value):
    return f"INR {indian_number(value)}"


def address_text(value):
    if not value:
        return "-"
    parts = [
        value.get("label"),
        value.get("address_line_1"),
        value.get("address_line_2"),
        value.get("city"),
        value.get("district"),
        value.get("state"),
        value.get("postal_code"),
        value.get("country"),
    ]
    return ", ".join(str(part) for part in parts if part)


def party_text(value):
    if not value:
        return "-"
    name = value.get("legal_name") or value.get("registered_name") or value.get("name") or "-"
    details = [value.get("gstin"), value.get("email"), value.get("phone")]
    return "\n".join([str(name), *(str(detail) for detail in details if detail)])


def safe_filename(identifier, extension):
    safe = "".join(
        character if character.isalnum() or character in "-_" else "-" for character in identifier
    )
    return f"{safe.strip('-') or 'document'}.{extension}"
