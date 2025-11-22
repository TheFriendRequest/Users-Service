from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

import os
import mysql.connector
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, auth

# ---------- Env & DB setup ----------

load_dotenv()

router = APIRouter(prefix="/users", tags=["users"])

FIREBASE_CRED_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json"
)

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)


def get_connection():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    db = os.getenv("DB_NAME")

    print("----DEBUG MYSQL CONNECTION PARAMS (USERS)----")
    print("HOST =", host)
    print("PORT =", port)
    print("USER =", user)
    print("DB   =", db)
    print("---------------------------------------------")

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
    )


# ---------- Firebase helpers ----------


def get_firebase_uid(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    id_token = authorization.split(" ", 1)[1]

    try:
        decoded = auth.verify_id_token(id_token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")


class UserSync(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None


# ---------- Routes ----------


@router.get("/me")
def get_current_user(firebase_uid: str = Depends(get_firebase_uid)):
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)

    cur.execute(
        """
        SELECT user_id, firebase_uid, email, display_name, created_at
        FROM Users
        WHERE firebase_uid = %s
        """,
        (firebase_uid,),
    )
    row = cur.fetchone()

    cur.close()
    cnx.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="User not found in database. Please sync your account first.",
        )

    return row


@router.post("/sync")
def sync_user(user: UserSync, firebase_uid: str = Depends(get_firebase_uid)):
    """
    Ensure there is a Users row for the currently logged-in Firebase user.
    - If it exists: update email/display_name, return 200.
    - If it doesn't: insert, return 201.
    """
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)

    # Check if user already exists
    cur.execute(
        """
        SELECT user_id, firebase_uid, email, display_name, created_at
        FROM Users
        WHERE firebase_uid = %s
        """,
        (firebase_uid,),
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            """
            UPDATE Users
            SET email = %s, display_name = %s
            WHERE firebase_uid = %s
            """,
            (user.email, user.display_name, firebase_uid),
        )
        cnx.commit()

        cur.execute(
            """
            SELECT user_id, firebase_uid, email, display_name, created_at
            FROM Users
            WHERE firebase_uid = %s
            """,
            (firebase_uid,),
        )
        row = cur.fetchone()

        cur.close()
        cnx.close()
        return row  # 200 OK

    # Insert new user
    cur.execute(
        """
        INSERT INTO Users (firebase_uid, email, display_name)
        VALUES (%s, %s, %s)
        """,
        (firebase_uid, user.email, user.display_name),
    )
    cnx.commit()
    user_id = cur.lastrowid

    cur.execute(
        """
        SELECT user_id, firebase_uid, email, display_name, created_at
        FROM Users
        WHERE user_id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()

    cur.close()
    cnx.close()

    return JSONResponse(status_code=201, content=row)
