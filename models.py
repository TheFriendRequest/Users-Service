from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr
    hobbies: Optional[str] = None
    free_time: Optional[str] = None

class User(UserBase):
    user_id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    profile_picture: str | None = None

class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    email: str | None = None
    profile_picture: str | None = None
