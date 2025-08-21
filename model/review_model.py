from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReviewModel(BaseModel):
    id: Optional[int] = None
    batch_raw: Optional[str] = None
    batch_summary: Optional[str] = None
    final_summary: Optional[str] = None
    file_url: Optional[str] = None
    created_at: Optional[datetime] = None