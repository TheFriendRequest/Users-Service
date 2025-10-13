from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr
    hobbies: Optional[str] = None
    free_time: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    hobbies: Optional[str] = None
    free_time: Optional[str] = None

class User(UserBase):
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True
