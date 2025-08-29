from decimal import Decimal
from datetime import date

def compute_duty(
    sku: str,
    origin: str,
    declared_value: Decimal,
    qty: Decimal,
    weight: Decimal | None,
    d: date,
    claimed_program: str | None,
    ocean: bool
) -> dict:
    base = Decimal("0")
    remedies = Decimal("0")
    mpf = Decimal("0")
    hmf = Decimal("0")
    adcvd = Decimal("0")
    total = base + remedies + mpf + hmf + adcvd
    return {
        "base": base,
        "remedies": remedies,
        "mpf": mpf,
        "hmf": hmf,
        "adcvd": adcvd,
        "total": total,
    }
