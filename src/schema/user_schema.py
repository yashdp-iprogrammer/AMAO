from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field


class UserCreate(BaseModel):
    client_id: str
    user_name: str
    user_mobile: Optional[str]
    user_email: str
    user_password: str
    role_id: int

class UserRead(BaseModel):
    user_id: str
    client_id: str
    user_name: str
    user_mobile: Optional[str]
    user_email: str
    role_id: int
    is_disabled: bool
    

class UserResponse(BaseModel):
    message: str
    user: UserRead

class UserUpdate(BaseModel):
    user_name: Optional[str] = None
    user_password: Optional[str] = None
    phone: Optional[str] = None
    role_id: Optional[int] = None
    is_disabled: Optional[bool] = None


class CurrentUser(BaseModel):
    user_id: str
    client_id: str
    user_name: str
    user_email: str
    role_id: int
    role_name: str

class UserResponseList(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    data: list[UserRead]

class Login(BaseModel):
    username: str = Field(max_length=255)
    password: str
    
