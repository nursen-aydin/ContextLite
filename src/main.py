from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.config import settings
from src.api.routes import router as api_router
from src.api.auth import router as auth_router
from src.api.files import router as files_router

from contextlib import asynccontextmanager
from src.services.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(api_router, prefix="/api")
app.include_router(files_router, prefix="/api/files", tags=["files"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name}

@app.get("/")
async def serve_landing():
    return FileResponse("src/static/landing.html")

@app.get("/login")
async def serve_login():
    return FileResponse("src/static/login.html")

@app.get("/signup")
async def serve_signup():
    return FileResponse("src/static/signup.html")

@app.get("/verify-email")
async def serve_verify_email():
    return FileResponse("src/static/login.html")

@app.get("/reset-password")
async def serve_reset_password():
    return FileResponse("src/static/login.html")

@app.get("/setup")
async def serve_setup():
    return FileResponse("src/static/setup.html")

@app.get("/app")
async def serve_app():
    return FileResponse("src/static/app.html")

@app.get("/account/verify")
async def verify_account_page():
    return FileResponse("src/static/verify.html")

# Mount static files (js, css, images)
app.mount("/static", StaticFiles(directory="src/static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
