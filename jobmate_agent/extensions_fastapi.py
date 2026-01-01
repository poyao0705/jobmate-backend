"""FastAPI extensions and database setup for Jobmate.Agent."""
import os
from dotenv import load_dotenv
from sqlmodel import create_engine, Session, SQLModel
from typing import Generator
from passlib.context import CryptContext

# Load environment variables
load_dotenv()

# Password hashing context
bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _resolve_database_uri() -> str:
    """Resolve SQLAlchemy database URI from environment."""
    mode = (os.getenv("DATABASE_MODE") or os.getenv("DATABASE_ENV") or "sqlite").lower()
    if mode == "postgres":
        uri = os.getenv("DATABASE_PROD")
        if not uri:
            raise RuntimeError("DATABASE_PROD must be set when DATABASE_MODE=postgres")
        return uri
    uri = os.getenv("DATABASE_DEV") or "sqlite:///instance/efficientai.db"
    return uri


# Database configuration
SQLALCHEMY_DATABASE_URI = _resolve_database_uri()

# Create engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URI.startswith("sqlite") else {},
    pool_pre_ping=True,
)

# Session factory for backward compatibility with jwt_auth_fastapi
def SessionLocal():
    """Create a new database session (backward compatibility)."""
    return Session(engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database sessions.
    Use in FastAPI routes with: db: Session = Depends(get_db)
    """
    with Session(engine) as session:
        yield session


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.verify(plain_password, hashed_password)
