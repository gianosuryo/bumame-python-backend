from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReviewItemsModel(BaseModel):
    id: Optional[int] = None
    review_id: int
    ota_platform: str
    username: str
    review: str
    review_level: Optional[int] = None
    reply: Optional[str] = None
    date_created: Optional[datetime] = None
    created_at: Optional[datetime] = None