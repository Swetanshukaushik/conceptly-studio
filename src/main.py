import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.core.config import settings
from src.core.security import get_password_hash
from src.database.session import engine, Base, SessionLocal
from src.models.entities import User
from src.api.auth import router as auth_router
from src.api.reels import router as reels_router
from src.api.avatars import router as avatars_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Autonomous 9:16 Vertical Educational Reel Factory Platform for Conceptly",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media directory for video & audio playback in UI
os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.LOCAL_STORAGE_DIR), name="media")

@app.get("/", include_in_schema=False)
@app.get("/studio", include_in_schema=False)
def serve_studio_ui():
    index_file = os.path.join(os.path.dirname(__file__), "web", "index.html")
    return FileResponse(index_file)

@app.get("/system-design", include_in_schema=False)
def serve_system_design_ui():
    design_file = os.path.join(os.path.dirname(__file__), "web", "system_design.html")
    return FileResponse(design_file)

# Include API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(reels_router, prefix=settings.API_V1_STR)
app.include_router(avatars_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
def on_startup():
    # 1. Create tables if not existing
    Base.metadata.create_all(bind=engine)
    
    # 2. Seed initial admin user if not present
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin_user:
            hashed_pwd = get_password_hash(settings.ADMIN_PASSWORD)
            admin_user = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hashed_pwd,
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            print(f"✅ Conceptly Studio: Seeded admin user ({settings.ADMIN_EMAIL})")
    finally:
        db.close()

@app.get(f"{settings.API_V1_STR}/health", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "storage_provider": settings.STORAGE_PROVIDER
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=True)
