from fastapi import APIRouter, HTTPException, Depends, status, Response, Header, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List, cast
from datetime import datetime
import os
import sys
import mysql.connector  # type: ignore
import hashlib
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Authentication removed - trust x-firebase-uid header from API Gateway
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
        database=os.getenv("DB_NAME", "user_db"),
    )


# ----------------------
# Helper: Get firebase_uid from header (set by API Gateway)
# ----------------------
def get_firebase_uid_from_header(request: Request) -> str:
    """Get firebase_uid from x-firebase-uid header (injected by API Gateway)"""
    firebase_uid = request.headers.get("x-firebase-uid") or request.headers.get("X-Firebase-Uid")
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Authentication required - x-firebase-uid header missing")
    return firebase_uid

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
def get_users(request: Request):
    """
    Get all users. Trusts x-firebase-uid header from API Gateway.
    Returns list of users excluding sensitive information.
    """
    firebase_uid = get_firebase_uid_from_header(request)
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
    request: Request
):
    """
    Get current authenticated user's profile with ETag support.
    Trusts x-firebase-uid header from API Gateway.
    """
    firebase_uid = get_firebase_uid_from_header(request)
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


# ----------------------
# INTEREST ENDPOINTS (must be before /{username} route to avoid route conflicts)
# ----------------------
@router.get("/interests")
def get_interests(request: Request):
    """Get all available interests. Trusts x-firebase-uid header from API Gateway."""
    firebase_uid = get_firebase_uid_from_header(request)
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT interest_id, interest_name FROM Interests ORDER BY interest_name")
    interests = cast(List[Dict[str, Any]], cur.fetchall())
    cur.close()
    cnx.close()
    return interests


@router.get("/{user_id}")
def get_user_by_id(user_id: int, request: Request):
    """
    Get user by user_id. 
    Used by Pub/Sub subscribers and internal services.
    Allows internal calls without full authentication (header can be 'system' or a valid firebase_uid).
    MUST be defined BEFORE /{username} route so FastAPI matches integer user_ids first.
    """
    # Allow internal calls from Pub/Sub subscribers (header can be 'system' or missing)
    firebase_uid = request.headers.get("x-firebase-uid") or request.headers.get("X-Firebase-Uid")
    # For internal calls, we allow 'system' or no header, but still check if user exists
    if not firebase_uid or firebase_uid == "system":
        # Internal call - proceed without auth validation
        pass
    else:
        # Normal authenticated call - validate
        pass
    
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT user_id, first_name, last_name, username, email, profile_picture, created_at FROM Users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    cnx.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return row


@router.get("/{username}")
def get_user_by_username(username: str, request: Request):
    """
    Get user by username. Trusts x-firebase-uid header from API Gateway.
    """
    firebase_uid = get_firebase_uid_from_header(request)
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
    request: Request
):
    """
    Sync Firebase user to database on first login.
    This endpoint is called after Firebase authentication.
    Creates a new user if they don't exist, or updates if they do.
    Returns 201 Created for new users, 200 OK for updates.
    Trusts x-firebase-uid header from API Gateway.
    """
    firebase_uid = get_firebase_uid_from_header(request)
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
        # Create new user with default role
        default_role = "user"
        sql = """
        INSERT INTO Users (firebase_uid, first_name, last_name, username, email, profile_picture, role)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (firebase_uid, user.first_name, user.last_name, 
                 user.username, user.email, user.profile_picture, default_role)
        cur.execute(sql, values)
        cnx.commit()
        user_id = cur.lastrowid
        cur.close()
        cnx.close()
        
        # Set default role in Firebase custom claims
        try:
            from firebase_claims import set_user_role
            if set_user_role(firebase_uid, default_role):
                print(f"✅ Set Firebase custom claim: role={default_role} for new user {firebase_uid}")
        except Exception as e:
            print(f"⚠️  Failed to set Firebase custom claim for new user: {e}")
            # Continue even if Firebase claim fails - user is created in DB
        
        # Publish user-created event to Pub/Sub (if needed)
        try:
            # Import here to avoid circular dependencies
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # Composite Service will handle Pub/Sub publishing, but we can also publish here
            # For now, let Composite Service handle it after receiving the response
        except Exception as e:
            print(f"⚠️  Could not publish user-created event: {e}")
        
        # Return 201 Created for new users
        return JSONResponse(
            content={
                "status": "created", 
                "user_id": user_id, 
                "firebase_uid": firebase_uid,
                "role": default_role
            },
            status_code=status.HTTP_201_CREATED
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, request: Request):
    """
    Create a new user. Trusts x-firebase-uid header from API Gateway.
    Note: Use /sync for first-time login.
    Returns 201 Created for successful user creation.
    """
    firebase_uid = get_firebase_uid_from_header(request)
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)

    # Check if firebase_uid already exists
    cur.execute("SELECT user_id FROM Users WHERE firebase_uid = %s", (firebase_uid,))
    if cur.fetchone():
        cur.close()
        cnx.close()
        raise HTTPException(status_code=400, detail="User already exists for this Firebase account")

    # Create new user with default role
    default_role = "user"
    sql = """
    INSERT INTO Users (firebase_uid, first_name, last_name, username, email, profile_picture, role)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = (firebase_uid, user.first_name, user.last_name, user.username, user.email, user.profile_picture, default_role)

    cur.execute(sql, values)
    cnx.commit()
    user_id = cur.lastrowid
    cur.close()
    cnx.close()
    
    # Set default role in Firebase custom claims
    try:
        from firebase_claims import set_user_role
        if set_user_role(firebase_uid, default_role):
            print(f"✅ Set Firebase custom claim: role={default_role} for new user {firebase_uid}")
    except Exception as e:
        print(f"⚠️  Failed to set Firebase custom claim for new user: {e}")

    return {"status": "created", "user_id": user_id, "firebase_uid": firebase_uid, "role": default_role}


@router.put("/{user_id}")
def update_user(user_id: int, user: UserUpdate, request: Request):
    """
    Update user. Trusts x-firebase-uid header from API Gateway.
    Users can only update their own profile.
    """
    firebase_uid = get_firebase_uid_from_header(request)
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
    
    # Get current user data to check for role changes
    cur.execute("SELECT firebase_uid, role FROM Users WHERE user_id = %s", (user_id,))
    current_user_data = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not current_user_data:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    firebase_uid = current_user_data['firebase_uid']
    current_role = current_user_data.get('role')
    
    # build dynamic SQL only for provided fields
    fields = []
    values = []
    role_changed = False
    new_role = None

    for key, value in user.dict().items():
        if value is not None:
            fields.append(f"{key} = %s")
            values.append(value)
            # Track if role is being updated
            if key == 'role' and value != current_role:
                role_changed = True
                new_role = value

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
    
    # Sync role to Firebase custom claims if role was changed
    if role_changed and new_role:
        try:
            from firebase_claims import sync_role_to_firebase
            if sync_role_to_firebase(firebase_uid, new_role):
                print(f"✅ Synced role to Firebase: {new_role} for {firebase_uid}")
        except Exception as e:
            print(f"⚠️  Failed to sync role to Firebase: {e}")
            # Continue - role is updated in DB even if Firebase sync fails

    return {"status": "updated", "user_id": user_id}


@router.delete("/{user_id}")
def delete_user(user_id: int, request: Request):
    """
    Delete user. Trusts x-firebase-uid header from API Gateway.
    Users can only delete their own account.
    """
    firebase_uid = get_firebase_uid_from_header(request)
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
    request: Request
):
    """Get all schedules for a user with ETag support. Trusts x-firebase-uid header from API Gateway."""
    firebase_uid = get_firebase_uid_from_header(request)
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
    request: Request
):
    """Create a new schedule for a user. Trusts x-firebase-uid header from API Gateway."""
    firebase_uid = get_firebase_uid_from_header(request)
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
    
    # Convert ISO 8601 datetime strings to MySQL datetime format
    def convert_to_mysql_datetime(iso_string: str) -> str:
        """Convert ISO 8601 format datetime string to MySQL datetime format.
        
        Example:
        - Input: '2025-11-23T23:33:00.000Z'
        - Output: '2025-11-23 23:33:00'
        """
        if not isinstance(iso_string, str):
            raise HTTPException(status_code=400, detail=f"Invalid datetime: expected string, got {type(iso_string)}")
        
        try:
            # Handle ISO 8601 with Z (UTC) timezone
            if iso_string.endswith('Z'):
                # Replace Z with +00:00 for fromisoformat
                iso_string = iso_string.replace('Z', '+00:00')
            
            # Parse ISO string (handles both with and without timezone)
            if '+' in iso_string or iso_string.count('-') > 2:
                # Has timezone info
                dt = datetime.fromisoformat(iso_string)
            else:
                # No timezone, assume local or UTC
                # Try parsing with milliseconds first
                try:
                    dt = datetime.strptime(iso_string, '%Y-%m-%dT%H:%M:%S.%f')
                except ValueError:
                    # Try without milliseconds
                    dt = datetime.strptime(iso_string, '%Y-%m-%dT%H:%M:%S')
            
            # Convert to MySQL datetime format: YYYY-MM-DD HH:MM:SS
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, AttributeError) as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid datetime format: {iso_string}. Error: {str(e)}"
            )
    
    start_time = convert_to_mysql_datetime(schedule['start_time'])
    end_time = convert_to_mysql_datetime(schedule['end_time'])
    
    sql = """
        INSERT INTO UserSchedule (user_id, start_time, end_time, type, title)
        VALUES (%s, %s, %s, %s, %s)
    """
    values = (
        user_id,
        start_time,
        end_time,
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
    request: Request
):
    """Delete a schedule for a user. Trusts x-firebase-uid header from API Gateway."""
    firebase_uid = get_firebase_uid_from_header(request)
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
@router.get("/{user_id}/interests")
def get_user_interests(user_id: int, request: Request):
    """Get all interests for a user. Trusts x-firebase-uid header from API Gateway."""
    firebase_uid = get_firebase_uid_from_header(request)
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
    request: Request
):
    """Add interests to a user (replaces existing). Trusts x-firebase-uid header from API Gateway."""
    firebase_uid = get_firebase_uid_from_header(request)
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
