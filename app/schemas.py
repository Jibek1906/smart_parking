from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class VehicleEntryCreate(BaseModel):
    plate_number: str
    entry_image: Optional[str] = None
    parking_spot: Optional[int] = None

class VehicleEntryUpdate(BaseModel):
    exit_time: Optional[datetime] = None
    exit_image: Optional[str] = None
    parking_fee: Optional[float] = None
    paid: Optional[bool] = None

class VehicleEntryResponse(BaseModel):
    id: int
    plate_number: str
    entry_time: datetime
    exit_time: Optional[datetime]
    parking_fee: float
    paid: bool
    
    class Config:
        from_attributes = True

class ParkingSettingsUpdate(BaseModel):
    base_price_per_hour: Optional[float] = None
    additional_price_per_hour: Optional[float] = None
    free_minutes: Optional[int] = None

class ParkingSettingsResponse(BaseModel):
    id: int
    base_price_per_hour: float
    additional_price_per_hour: float
    free_minutes: int
    
    class Config:
        from_attributes = True

class PaymentRequest(BaseModel):
    vehicle_id: int
    amount: float
