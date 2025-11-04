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
from .api.routers import api_tokens
from .api.routers import files
from .api.routers import form



# Create the main app instance
app = FastAPI(
    title="EasyForm API",
    description="API for EasyForm - AI-powered form filling browser extension",
    version="1.0.0",
    root_path="/api",
    lifespan=lifespan  # Use the lifespan context manager
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY
)

# CORS Configuration - Allow all origins for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (required for browser extensions)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True}


# Include routers
app.include_router(auth_router.api_router)
app.include_router(users.router)
app.include_router(api_tokens.router)
app.include_router(files.router)
app.include_router(form.router)

# The root path "/" is now outside the /api prefix
@app.get("/")
async def root():
    """Status endpoint for the API."""
    return {"message": "Welcome to EasyForm API. Visit /api/docs for API documentation."}

