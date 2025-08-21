from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class BaseResponse(BaseModel, Generic[T]):
    status_code: int = 200
    fulfilled: bool = True
    message: str
    data: Optional[T] = None
    pagination: Optional[Pagination] = None
    error: Optional[Dict[str, Any]] = None
    extra_fields: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(exclude_none=True)

    def dict_response(self):
        response_dict = self.model_dump()
        return {k: v for k, v in response_dict.items() if v is not None}

    def add_extra_field(self, key: str, value: Any):
        if self.extra_fields is None:
            self.extra_fields = {}
        self.extra_fields[key] = value