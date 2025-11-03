"""
Main application entry point for the FastAPI backend.
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config.settings import SESSION_SECRET_KEY, FRONTEND_BASE_URL
from .core.lifespan import lifespan

from .api.routers import auth as auth_router
from .api.routers import users



# Create the main app instance
app = FastAPI(
    title="User Management API",
    root_path="/api",
    lifespan=lifespan  # Use the lifespan context manager
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY
)

# CORS Configuration - Allow both local development and production
origins = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8000",
    "http://127.0.0.1:8127",
    "https://easyform.m4rkus28.de",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True}


# Include your existing routers under this api_router
app.include_router(users.router)
app.include_router(auth_router.api_router)

# The root path "/" is now outside the /api prefix
@app.get("/")
async def root():
    """Status endpoint for the API."""
    return {"message": "Welcome to Piatto API. Visit /api/docs for API documentation."}

