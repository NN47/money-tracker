from dataclasses import dataclass
from typing import Optional


@dataclass
class Participant:
    id: int
    name: str
    created_at: str


@dataclass
class User:
    telegram_id: int
    default_currency: str = "RUB"


@dataclass
class Transaction:
    id: int
    participant_id: int
    type: str
    amount: float
    currency: str
    category: str
    comment: Optional[str]
    created_at: str


@dataclass
class Payment:
    id: int
    participant_id: int
    title: str
    amount: float
    due_date: str
    is_paid: bool
