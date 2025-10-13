from fastapi import FastAPI
from routers import users

app = FastAPI(title="Users Service", version="1.0")

app.include_router(users.router)

@app.get("/")
def root():
    return {"status": "Users Service running"}
