from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, cast
import os
import sys
import mysql.connector
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import verify_firebase_token, get_firebase_uid
from models import UserCreate, UserSync, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


# ----------------------
# DB
# ----------------------
def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", 'admin'),
        database=os.getenv("DB_NAME", "friend_request_db")
    )


# ----------------------
# ROUTES
# ----------------------

@router.get("/")
def get_users(firebase_uid: str = Depends(get_firebase_uid)):
    """
    Get all users (requires Firebase authentication).
    Returns list of users excluding sensitive information.
    """
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id, first_name, last_name, username, email, profile_picture, created_at FROM Users")
    data = cur.fetchall()
    cur.close()
    cnx.close()
    return data


@router.get("/me")
def get_current_user(firebase_uid: str = Depends(get_firebase_uid)):
    """
    Get current authenticated user's profile.
    """
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id, firebase_uid, first_name, last_name, username, email, profile_picture, created_at FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    row = cur.fetchone()
    cur.close()
    cnx.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found in database. Please sync your account first.")

    return row


@router.get("/{username}")
def get_user_by_username(username: str, firebase_uid: str = Depends(get_firebase_uid)):
    """
    Get user by username (requires Firebase authentication).
    """
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id, first_name, last_name, username, email, profile_picture, created_at FROM Users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    cnx.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return row


@router.post("/sync")
def sync_firebase_user(
    user: UserSync,
    firebase_uid: str = Depends(get_firebase_uid)
):
    """
    Sync Firebase user to database on first login.
    This endpoint is called after Firebase authentication.
    Creates a new user if they don't exist, or updates if they do.
    Returns 201 Created for new users, 200 OK for updates.
    """
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    
    # Check if user already exists by firebase_uid
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    existing_user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if existing_user:
        # Update existing user
        sql = """
        UPDATE Users 
        SET first_name = %s, last_name = %s, username = %s, 
            email = %s, profile_picture = %s
        WHERE firebase_uid = %s
        """
        values = (user.first_name, user.last_name, user.username, 
                 user.email, user.profile_picture, firebase_uid)
        cur.execute(sql, values)
        cnx.commit()
        user_id = existing_user['user_id']
        cur.close()
        cnx.close()
        # Return 200 OK for updates
        return JSONResponse(
            content={"status": "updated", "user_id": user_id, "firebase_uid": firebase_uid},
            status_code=status.HTTP_200_OK
        )
    else:
        # Create new user
        sql = """
        INSERT INTO Users (firebase_uid, first_name, last_name, username, email, profile_picture)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (firebase_uid, user.first_name, user.last_name, 
                 user.username, user.email, user.profile_picture)
        cur.execute(sql, values)
        cnx.commit()
        user_id = cur.lastrowid
        cur.close()
        cnx.close()
        # Return 201 Created for new users
        return JSONResponse(
            content={"status": "created", "user_id": user_id, "firebase_uid": firebase_uid},
            status_code=status.HTTP_201_CREATED
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, firebase_uid: str = Depends(get_firebase_uid)):
    """
    Create a new user (requires Firebase authentication).
    Note: This endpoint requires authentication. Use /sync for first-time login.
    Returns 201 Created for successful user creation.
    """
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)

    # Check if firebase_uid already exists
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    if cur.fetchone():
        cur.close()
        cnx.close()
        raise HTTPException(status_code=400, detail="User already exists for this Firebase account")

    sql = """
    INSERT INTO Users (firebase_uid, first_name, last_name, username, email, profile_picture)
    VALUES (%s, %s, %s, %s, %s, %s)
    """

    values = (firebase_uid, user.first_name, user.last_name, user.username, user.email, user.profile_picture)

    cur.execute(sql, values)
    cnx.commit()
    user_id = cur.lastrowid
    cur.close()
    cnx.close()

    return {"status": "created", "user_id": user_id, "firebase_uid": firebase_uid}


@router.put("/{user_id}")
def update_user(user_id: int, user: UserUpdate, firebase_uid: str = Depends(get_firebase_uid)):
    """
    Update user (requires Firebase authentication).
    Users can only update their own profile.
    """
    # Verify user owns this account
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    current_user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not current_user:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only update your own profile")
    
    if current_user['user_id'] != user_id:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only update your own profile")
    
    # build dynamic SQL only for provided fields
    fields = []
    values = []

    for key, value in user.dict().items():
        if value is not None:
            fields.append(f"{key} = %s")
            values.append(value)

    if not fields:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=400, detail="No fields to update")

    sql = f"UPDATE Users SET {', '.join(fields)} WHERE user_id = %s"
    values.append(user_id)

    cur.execute(sql, tuple(values))
    cnx.commit()
    cur.close()
    cnx.close()

    return {"status": "updated", "user_id": user_id}


@router.delete("/{user_id}")
def delete_user(user_id: int, firebase_uid: str = Depends(get_firebase_uid)):
    """
    Delete user (requires Firebase authentication).
    Users can only delete their own account.
    """
    # Verify user owns this account
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    current_user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not current_user:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only delete your own account")
    
    if current_user['user_id'] != user_id:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only delete your own account")
    
    cur.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
    cnx.commit()
    cur.close()
    cnx.close()

    return {"status": "deleted", "user_id": user_id}
