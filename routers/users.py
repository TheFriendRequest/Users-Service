from fastapi import APIRouter, HTTPException, Depends, status, Response, Header
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List, cast
import os
import sys
import mysql.connector
import hashlib
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import get_firebase_uid
from models import UserCreate, UserSync, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


# ----------------------
# DB
# ----------------------
def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", 'admin'),
        database=os.getenv("DB_NAME", "user_db")
    )


# ----------------------
# Helper: Generate eTag
# ----------------------
def generate_etag(data: Any) -> str:
    """Generate eTag from data"""
    data_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(data_str.encode()).hexdigest()


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
    print(f"[Users Service] Connected to database: {cnx}")
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id, first_name, last_name, username, email, profile_picture, created_at FROM Users")
    data = cur.fetchall()
    cur.close()
    cnx.close()
    return data


@router.get("/me")
def get_current_user(
    response: Response,
    firebase_uid: str = Depends(get_firebase_uid)
):
    """
    Get current authenticated user's profile with ETag support.
    """
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id, firebase_uid, first_name, last_name, username, email, profile_picture, created_at FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    row = cur.fetchone()
    cur.close()
    cnx.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found in database. Please sync your account first.")

    # Generate eTag for the user profile
    etag = generate_etag(row)
    response.headers["ETag"] = f'"{etag}"'
    print(f"[Users Service] Generated ETag for user profile: {etag}")
    print(f"[Users Service] ETag header set: {response.headers.get('ETag')}")

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


# ----------------------
# SCHEDULE ENDPOINTS
# ----------------------
@router.get("/{user_id}/schedules")
def get_user_schedules(
    user_id: int,
    response: Response,
    firebase_uid: str = Depends(get_firebase_uid)
):
    """Get all schedules for a user with ETag support"""
    # Verify user owns this account
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    current_user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not current_user:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="Authentication required")
    
    if current_user['user_id'] != user_id:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only view your own schedules")
    
    cur.execute("""
        SELECT schedule_id, user_id, start_time, end_time, type, title
        FROM UserSchedule
        WHERE user_id = %s
        ORDER BY start_time ASC
    """, (user_id,))
    schedules = cur.fetchall()
    cur.close()
    cnx.close()
    
    # Generate eTag for the schedules collection
    etag = generate_etag(schedules)
    response.headers["ETag"] = f'"{etag}"'
    print(f"[Users Service] Generated ETag for schedules: {etag}")
    print(f"[Users Service] ETag header set: {response.headers.get('ETag')}")
    
    return schedules


@router.post("/{user_id}/schedules", status_code=status.HTTP_201_CREATED)
def create_user_schedule(
    user_id: int,
    schedule: Dict[str, Any],
    firebase_uid: str = Depends(get_firebase_uid)
):
    """Create a new schedule for a user"""
    # Verify user owns this account
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    current_user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not current_user:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="Authentication required")
    
    if current_user['user_id'] != user_id:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only create schedules for yourself")
    
    sql = """
        INSERT INTO UserSchedule (user_id, start_time, end_time, type, title)
        VALUES (%s, %s, %s, %s, %s)
    """
    values = (
        user_id,
        schedule['start_time'],
        schedule['end_time'],
        schedule['type'],
        schedule['title']
    )
    cur.execute(sql, values)
    cnx.commit()
    schedule_id = cur.lastrowid
    cur.close()
    cnx.close()
    return {"status": "created", "schedule_id": schedule_id}


@router.delete("/{user_id}/schedules/{schedule_id}")
def delete_user_schedule(
    user_id: int,
    schedule_id: int,
    firebase_uid: str = Depends(get_firebase_uid)
):
    """Delete a schedule for a user"""
    # Verify user owns this account
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    current_user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not current_user:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="Authentication required")
    
    if current_user['user_id'] != user_id:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only delete your own schedules")
    
    cur.execute("DELETE FROM UserSchedule WHERE schedule_id = %s AND user_id = %s", (schedule_id, user_id))
    cnx.commit()
    cur.close()
    cnx.close()
    return {"status": "deleted", "schedule_id": schedule_id}


# ----------------------
# INTEREST ENDPOINTS
# ----------------------
@router.get("/interests")
def get_interests(firebase_uid: str = Depends(get_firebase_uid)):
    """Get all available interests"""
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT interest_id, interest_name FROM Interests ORDER BY interest_name")
    interests = cast(List[Dict[str, Any]], cur.fetchall())
    cur.close()
    cnx.close()
    return interests


@router.get("/{user_id}/interests")
def get_user_interests(user_id: int, firebase_uid: str = Depends(get_firebase_uid)):
    """Get all interests for a user"""
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("""
        SELECT i.interest_id, i.interest_name
        FROM Interests i
        INNER JOIN UserInterests ui ON i.interest_id = ui.interest_id
        WHERE ui.user_id = %s
        ORDER BY i.interest_name
    """, (user_id,))
    interests = cast(List[Dict[str, Any]], cur.fetchall())
    cur.close()
    cnx.close()
    return interests


@router.post("/{user_id}/interests", status_code=status.HTTP_201_CREATED)
def add_user_interests(
    user_id: int,
    interest_ids: List[int],
    firebase_uid: str = Depends(get_firebase_uid)
):
    """Add interests to a user (replaces existing)"""
    # Verify user owns this account
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    current_user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not current_user:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="Authentication required")
    
    if current_user['user_id'] != user_id:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=403, detail="You can only update your own interests")
    
    # Delete existing interests
    cur.execute("DELETE FROM UserInterests WHERE user_id = %s", (user_id,))
    
    # Add new interests
    for interest_id in interest_ids:
        # Verify interest exists
        cur.execute("SELECT interest_id FROM Interests WHERE interest_id = %s", (interest_id,))
        if not cur.fetchone():
            cur.close()
            cnx.close()
            raise HTTPException(status_code=400, detail=f"Interest {interest_id} not found")
        
        cur.execute(
            "INSERT INTO UserInterests (user_id, interest_id) VALUES (%s, %s)",
            (user_id, interest_id)
        )
    
    cnx.commit()
    cur.close()
    cnx.close()
    return {"status": "updated", "user_id": user_id, "interest_ids": interest_ids}
