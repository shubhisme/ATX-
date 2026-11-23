"""
Payment processing module for the sample application.
Handles card validation, Stripe-style charges, and refunds.
"""
import re
from utils import generate_uuid, utcnow_iso


_transactions: dict[str, dict] = {}


def validate_card(card_number: str) -> bool:
    """Validate a credit card number using the Luhn algorithm."""
    card_number = re.sub(r"[\s\-]", "", card_number)
    if not card_number.isdigit() or not (13 <= len(card_number) <= 19):
        return False
    total = 0
    for i, digit in enumerate(card_number[::-1]):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def calculate_fee(amount: float, rate: float = 0.029) -> float:
    """Calculate the processing fee for a transaction."""
    return round(amount * rate + 0.30, 2)


def process_payment(card_number: str, amount: float, currency: str = "USD") -> dict:
    """Process a payment for the given card and amount.
    
    Raises:
        ValueError: If the card number is invalid or amount is non-positive.
    """
    if not validate_card(card_number):
        raise ValueError(f"Invalid card number: {card_number[:4]}****")
    if amount <= 0:
        raise ValueError(f"Amount must be positive; got {amount}")
    fee = calculate_fee(amount)
    transaction_id = generate_uuid()
    _transactions[transaction_id] = {
        "transaction_id": transaction_id,
        "card_last4": card_number[-4:],
        "amount": amount,
        "fee": fee,
        "currency": currency,
        "status": "completed",
        "created_at": utcnow_iso(),
    }
    return _transactions[transaction_id]


def charge_stripe(token: str, amount: float) -> dict:
    """Simulate a Stripe charge using a payment token."""
    if not token or not token.startswith("tok_"):
        raise ValueError("Invalid Stripe token format")
    charge_id = "ch_" + generate_uuid().replace("-", "")[:24]
    return {
        "id": charge_id,
        "object": "charge",
        "amount": int(amount),
        "currency": "usd",
        "status": "succeeded",
        "created": utcnow_iso(),
    }


def refund_payment(transaction_id: str) -> dict:
    """Refund a previously completed transaction.
    
    Raises:
        KeyError: If the transaction_id does not exist.
        ValueError: If the transaction is already refunded.
    """
    if transaction_id not in _transactions:
        raise KeyError(f"Transaction {transaction_id} not found")
    txn = _transactions[transaction_id]
    if txn["status"] == "refunded":
        raise ValueError(f"Transaction {transaction_id} already refunded")
    _transactions[transaction_id]["status"] = "refunded"
    return {
        "transaction_id": transaction_id,
        "refunded_amount": txn["amount"],
        "status": "refunded",
        "refunded_at": utcnow_iso(),
    }
