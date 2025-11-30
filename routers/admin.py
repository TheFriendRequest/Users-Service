"""
Admin endpoints for role management
These endpoints allow updating user roles (admin-only operations)
"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import Optional, Dict, Any, cast
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import verify_firebase_token
from firebase_claims import set_user_role, get_user_role

# Import get_connection - duplicate function to avoid circular import
def get_connection():
    """Get database connection - same as in users.py"""
    import mysql.connector  # type: ignore
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", 'admin'),
        database=os.getenv("DB_NAME", "user_db"),
    )

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin_role(decoded_token: dict) -> bool:
    """
    Check if user has admin role from Firebase custom claims.
    Returns True if user is admin, False otherwise.
    """
    role = decoded_token.get("role")
    return role == "admin"


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role: str,
    request: Request
):
    """
    Update user role (admin-only).
    Updates both database and Firebase custom claims.
    Trusts x-firebase-uid header from API Gateway.
    NOTE: For admin operations, role verification should be done at API Gateway level
    or via Firebase Admin SDK using the firebase_uid from the header.
    """
    # Get firebase_uid from header
    firebase_uid = request.headers.get("x-firebase-uid") or request.headers.get("X-Firebase-Uid")
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Authentication required - x-firebase-uid header missing")
    
    # Get role from header (set by API Gateway) or from Firebase custom claims
    user_role = request.headers.get("x-user-role") or request.headers.get("X-User-Role")
    
    # If role not in header, try to get from Firebase custom claims
    if not user_role:
        try:
            user_role = get_user_role(firebase_uid)
        except Exception:
            user_role = "user"  # Default to user if we can't determine role
    
    # Check if current user is admin
    if not user_role or user_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can update user roles"
        )
    
    # Validate role
    valid_roles = ["user", "admin", "moderator"]  # Add more as needed
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )
    
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    
    # Get user's firebase_uid
    cur.execute("SELECT firebase_uid FROM Users WHERE user_id = %s", (user_id,))
    user = cast(Optional[Dict[str, Any]], cur.fetchone())
    
    if not user:
        cur.close()
        cnx.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    firebase_uid_target = user['firebase_uid']
    
    # Update role in database
    cur.execute("UPDATE Users SET role = %s WHERE user_id = %s", (role, user_id))
    cnx.commit()
    cur.close()
    cnx.close()
    
    # Update Firebase custom claims
    if set_user_role(firebase_uid_target, role):
        return {
            "status": "updated",
            "user_id": user_id,
            "firebase_uid": firebase_uid_target,
            "role": role,
            "message": "Role updated in both database and Firebase"
        }
    else:
        # Role updated in DB but Firebase sync failed
        return {
            "status": "updated",
            "user_id": user_id,
            "role": role,
            "warning": "Role updated in database, but Firebase custom claim update failed"
        }

