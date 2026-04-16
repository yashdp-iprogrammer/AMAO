from pydantic import BaseModel
from typing import Optional


class ModelCreate(BaseModel):
    model_name: str
    provider: str
    token_size: int
    model_subscription: bool
    subscription_cost: float


class ModelUpdate(BaseModel):
    model_name: Optional[str] = None
    provider: Optional[str] =  None
    token_size: Optional[int] = None
    model_subscription: Optional[bool] = None
    subscription_cost: Optional[float] = None


class ModelRead(BaseModel):
    model_id: str
    model_name: str
    provider: str
    token_size: int
    model_subscription: bool
    subscription_cost: float

class ModelResponse(BaseModel):
    message: str
    model: ModelRead
    

class ModelResponseList(BaseModel):
    total: int
    page: int
    size: int
    data: list[ModelRead]