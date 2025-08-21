from typing import Literal, List
from pydantic import BaseModel, Field

LOG_SIZE = 80

LANGUAGE_TYPE = Literal["Indonesia", "English"]
TONE_TYPE = Literal["Formal", "Casual", "Friendly", "Professional"]

class GeneratedRetrieveQuery(BaseModel):
    queries: List[str] = Field(
        ..., description="List of search queries to retrieve data from document")
