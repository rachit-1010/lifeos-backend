from datetime import datetime

from pydantic import BaseModel


class Transaction(BaseModel):
    id: str
    vendor: str
    amount: float
    timestamp: datetime


class TransactionOut(BaseModel):
    id: str
    vendor: str
    amount: float
    timestamp: datetime
    created_at: datetime
