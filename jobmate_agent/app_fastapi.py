"""
FastAPI application factory for Jobmate.Agent.
Sets up configuration, database, CORS, and registers routers.
"""

import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env FIRST before importing database extensions
load_dotenv()

# Import database and extensions AFTER loading environment
from jobmate_agent.extensions_fastapi import SessionLocal, engine, Base


def _resolve_database_uri() -> str:
    """Resolve SQLAlchemy database URI from environment.

    Supports dual modes:
    - sqlite via `DATABASE_MODE=sqlite` and `DATABASE_DEV`
    - postgres via `DATABASE_MODE=postgres` and `DATABASE_PROD`

    Falls back to `DATABASE_ENV` for compatibility with scripts.
    """
    mode = (os.getenv("DATABASE_MODE") or os.getenv("DATABASE_ENV") or "sqlite").lower()
    if mode == "postgres":
        uri = os.getenv("DATABASE_PROD")
        if not uri:
            raise RuntimeError("DATABASE_PROD must be set when DATABASE_MODE=postgres")
        return uri
    # default sqlite dev path
    uri = os.getenv("DATABASE_DEV") or "sqlite:///instance/efficientai.db"
    return uri


def _ensure_instance_dir() -> None:
    """Ensure the instance directory exists (for SQLite and local storage)."""
    try:
        instance_path = Path("instance")
        instance_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Non-fatal; continue even if instance dir can't be created
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown tasks."""
    # Startup
    logging.info("Starting up FastAPI application...")
    
    # Ensure instance directory exists
    _ensure_instance_dir()
    
    # Initialize Chroma collections
    if not os.getenv("SKIP_CHROMA_INIT"):
        try:
            from jobmate_agent.services.vector_store import init_collections
            init_collections()
        except Exception as exc:
            logging.error(f"Failed to initialize Chroma collections: {exc}")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    logging.info("FastAPI application started successfully")
    
    yield
    
    # Shutdown
    logging.info("Shutting down FastAPI application...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # .env already loaded at module import
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create FastAPI app with lifespan
    app = FastAPI(
        title="Jobmate Agent API",
        description="AI-powered career assistance API",
        version="2.0.0",
        lifespan=lifespan
    )

    # Enable CORS
    # Get allowed origins from environment or use defaults
    allowed_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if allowed_origins_str:
        allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]
    else:
        # Default development origins
        allowed_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
        ]
    
    logging.info(f"CORS allowed origins: {allowed_origins}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Register API routers
    from jobmate_agent.routers import (
        chat,
        resumes,
        job_listings,
        external_jobs,
        job_collections,
        user_profile,
        gap,
        langgraph_router,
        langgraph_dev,
        tasks,
    )

    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(resumes.router, prefix="/api", tags=["resumes"])
    app.include_router(job_listings.router, prefix="/api", tags=["job_listings"])
    app.include_router(external_jobs.router, prefix="/api", tags=["external_jobs"])
    app.include_router(job_collections.router, prefix="/api", tags=["job_collections"])
    app.include_router(user_profile.router, prefix="/api", tags=["user_profile"])
    app.include_router(gap.router, prefix="/api", tags=["gap"])
    app.include_router(langgraph_router.router, prefix="/api", tags=["langgraph"])
    app.include_router(langgraph_dev.router, prefix="/api", tags=["langgraph_dev"])
    app.include_router(tasks.router, prefix="/api", tags=["tasks"])

    # Health check endpoint
    @app.get("/api/ping", tags=["health"])
    async def ping():
        """Unprotected health check endpoint to verify server is alive."""
        return {"ok": True, "message": "pong"}

    return app


# Create app instance
app = create_app()
