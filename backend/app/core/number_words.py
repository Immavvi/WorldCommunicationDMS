from decimal import ROUND_HALF_UP, Decimal

ONES = (
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def _under_thousand(value: int) -> str:
    words = []
    if value >= 100:
        words.extend((ONES[value // 100], "Hundred"))
        value %= 100
    if value >= 20:
        words.append(TENS[value // 10])
        value %= 10
    if value:
        words.append(ONES[value])
    return " ".join(words)


def _integer_words(value: int) -> str:
    if value == 0:
        return "Zero"
    parts = []
    for divisor, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")):
        if value >= divisor:
            parts.extend((_integer_words(value // divisor), name))
            value %= divisor
    if value:
        parts.append(_under_thousand(value))
    return " ".join(parts)


def inr_amount_in_words(amount: Decimal) -> str:
    normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized < 0:
        raise ValueError("Amount in words requires a non-negative value.")
    rupees = int(normalized)
    paise = int((normalized - Decimal(rupees)) * 100)
    result = f"Indian Rupees {_integer_words(rupees)}"
    if paise:
        result += f" and {_integer_words(paise)} Paise"
    return f"{result} Only"
