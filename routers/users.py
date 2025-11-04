from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import mysql.connector

router = APIRouter(prefix="/users", tags=["Users"])


# ----------------------
# DB
# ----------------------
def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", ''),
        database=os.getenv("DB_NAME", "friend_request_db")
    )


# ----------------------
# MODELS
# ----------------------
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


# ----------------------
# ROUTES
# ----------------------

@router.get("/")
def get_users():
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT * FROM Users")
    data = cur.fetchall()
    cur.close()
    cnx.close()
    return data


@router.get("/{username}")
def get_user_by_username(username: str):
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT * FROM Users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    cnx.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return row


@router.post("/")
def create_user(user: UserCreate):
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)

    sql = """
    INSERT INTO Users (first_name, last_name, username, email, profile_picture)
    VALUES (%s, %s, %s, %s, %s)
    """

    values = (user.first_name, user.last_name, user.username, user.email, user.profile_picture)

    cur.execute(sql, values)
    cnx.commit()
    cur.close()
    cnx.close()

    return {"status": "created", "user_id": cur.lastrowid}


@router.put("/{user_id}")
def update_user(user_id: int, user: UserUpdate):
    # build dynamic SQL only for provided fields
    fields = []
    values = []

    for key, value in user.dict().items():
        if value is not None:
            fields.append(f"{key} = %s")
            values.append(value)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    sql = f"UPDATE Users SET {', '.join(fields)} WHERE user_id = %s"
    values.append(user_id)

    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute(sql, tuple(values))
    cnx.commit()
    cur.close()
    cnx.close()

    return {"status": "updated", "user_id": user_id}


@router.delete("/{user_id}")
def delete_user(user_id: int):
    cnx = get_connection()
    cur = cnx.cursor(dictionary=True)
    cur.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
    cnx.commit()
    cur.close()
    cnx.close()

    return {"status": "deleted", "user_id": user_id}
