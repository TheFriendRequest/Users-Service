from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    profile_picture: Optional[str] = None


class UserSync(BaseModel):
    """Model for syncing Firebase user to database"""
    first_name: str
    last_name: str
    username: str
    email: str
    profile_picture: Optional[str] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    profile_picture: Optional[str] = None
    role: Optional[str] = None  # Role can be updated (admin-only typically)


class FriendRequestCreate(BaseModel):
    """Model for creating a friend request"""
    to_user_id: int


class FriendRequestResponse(BaseModel):
    """Model for friend request response"""
    friendship_id: int
    user_id_1: int
    user_id_2: int
    status: str
    created_at: str