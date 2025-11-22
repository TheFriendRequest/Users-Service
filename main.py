from fastapi import FastAPI
from routers import users
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Users Service", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)


@app.get("/")
def root():
    return {"status": "Users Service running"}
