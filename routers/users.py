from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/")
def get_users():
    return {"msg": "GET users - not implemented"}

@router.post("/")
def create_user():
    return {"msg": "POST user - not implemented"}

@router.put("/{user_id}")
def update_user(user_id: int):
    return {"msg": f"PUT user {user_id} - not implemented"}

@router.delete("/{user_id}")
def delete_user(user_id: int):
    return {"msg": f"DELETE user {user_id} - not implemented"}
