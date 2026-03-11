from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


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

class OverlandGeometry(BaseModel):
    type: str
    coordinates: List[float]  # GeoJSON format: [longitude, latitude]

class OverlandProperties(BaseModel):
    timestamp: datetime
    altitude: Optional[float] = None
    speed: Optional[float] = None
    horizontal_accuracy: Optional[float] = None
    vertical_accuracy: Optional[float] = None
    motion: Optional[List[str]] = None
    battery_state: Optional[str] = None
    battery_level: Optional[float] = None
    device_id: Optional[str] = None
    wifi: Optional[str] = None
    
    # Allow extra fields so validation doesn't fail if Overland adds new properties
    model_config = ConfigDict(extra="allow")

class OverlandLocation(BaseModel):
    type: str
    geometry: OverlandGeometry
    properties: OverlandProperties

class OverlandPayload(BaseModel):
    locations: List[OverlandLocation]