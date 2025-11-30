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
    expose_headers=["ETag", "etag", "Location", "Content-Type"]  # Expose ETag header to frontend
)

app.include_router(users.router)

# Include admin router if it exists
try:
    from routers import admin
    app.include_router(admin.router)
except ImportError:
    pass  # Admin router is optional

@app.get("/")
def root():
    return {"status": "Users Service running"}
