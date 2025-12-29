# Flask to FastAPI Migration Guide

## Overview

This document describes the migration from Flask to FastAPI for the Jobmate backend application.

## What's Been Created

### Core Files

1. **`jobmate_agent/app_fastapi.py`** - Main FastAPI application factory
   - Replaces Flask's `app.py`
   - Uses FastAPI's lifespan events for startup/shutdown
   - Includes CORS middleware
   - Registers all API routers

2. **`jobmate_agent/extensions_fastapi.py`** - Database and extensions setup
   - Replaces Flask-SQLAlchemy with pure SQLAlchemy
   - Provides `get_db()` dependency for route injection
   - Includes bcrypt password hashing functions

3. **`jobmate_agent/models_fastapi.py`** - SQLAlchemy models for FastAPI
   - Pure SQLAlchemy models (not Flask-SQLAlchemy)
   - Compatible with FastAPI's dependency injection
   - All existing models converted

4. **`jobmate_agent/jwt_auth_fastapi.py`** - JWT authentication for FastAPI
   - Replaces Flask's `@require_jwt` decorator with FastAPI dependencies
   - Uses `HTTPBearer` security scheme
   - Provides `get_current_user()` and `get_current_user_with_profile()` dependencies

5. **`jobmate_agent/schemas.py`** - Pydantic models for request/response validation
   - Type-safe request bodies and responses
   - Automatic OpenAPI documentation
   - Data validation

### Routers (API Endpoints)

All Flask blueprints have been converted to FastAPI routers in `jobmate_agent/routers/`:

- **`resumes.py`** - Resume upload, download, listing, and search (FULLY IMPLEMENTED)
- **`chat.py`** - Chat endpoints (STUB - needs implementation)
- **`job_listings.py`** - Job listing endpoints (STUB)
- **`external_jobs.py`** - External job fetching (STUB)
- **`job_collections.py`** - Job collections management (STUB)
- **`user_profile.py`** - User profile management (IMPLEMENTED)
- **`gap.py`** - Skill gap analysis (STUB)
- **`langgraph_router.py`** - LangGraph integration (STUB)
- **`langgraph_dev.py`** - LangGraph dev features (STUB)
- **`tasks.py`** - Task management (STUB)

### Scripts

1. **`run_fastapi.py`** - Run the FastAPI server
2. **`fetch_jobs_fastapi.py`** - Fetch external jobs (updated for FastAPI)
3. **`asgi.py`** - ASGI entry point for production deployment

### Dependencies

- **`requirements_fastapi.txt`** - New requirements file with FastAPI dependencies

## Key Differences from Flask

### 1. Application Structure

**Flask:**
```python
from flask import Flask, request, jsonify, g

app = Flask(__name__)

@app.route("/api/endpoint", methods=["POST"])
def endpoint():
    data = request.get_json()
    return jsonify({"result": "data"})
```

**FastAPI:**
```python
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class RequestModel(BaseModel):
    field: str

@app.post("/api/endpoint")
async def endpoint(data: RequestModel):
    return {"result": "data"}
```

### 2. Authentication

**Flask:**
```python
@require_jwt(hydrate=True)
def protected_route():
    user_id = g.user_sub
    return jsonify({"user": user_id})
```

**FastAPI:**
```python
@router.get("/protected")
async def protected_route(
    user_data: Tuple = Depends(get_current_user_with_profile)
):
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    return {"user": user_id}
```

### 3. Database Access

**Flask:**
```python
from jobmate_agent.models import db, User

@app.route("/users")
def get_users():
    users = User.query.all()
    return jsonify({"users": users})
```

**FastAPI:**
```python
from jobmate_agent.models_fastapi import User
from sqlalchemy.orm import Session

@router.get("/users")
async def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {"users": users}
```

### 4. File Uploads

**Flask:**
```python
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    # process file
```

**FastAPI:**
```python
from fastapi import UploadFile, File

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    # process file
```

## Migration Steps

### Step 1: Install FastAPI Dependencies

```bash
pip install -r requirements_fastapi.txt
```

### Step 2: Test the FastAPI Application

```bash
python run_fastapi.py
```

Or with uvicorn directly:

```bash
uvicorn jobmate_agent.app_fastapi:app --reload --port 5000
```

### Step 3: Implement Remaining Routers

The following routers are stubs and need implementation:

1. **chat.py** - Implement chat functionality
   - Reference: `jobmate_agent/blueprints/api/chat.py`
   
2. **job_listings.py** - Implement job listing endpoints
   - Reference: `jobmate_agent/blueprints/api/jobListings.py`
   
3. **external_jobs.py** - Implement external job fetching
   - Reference: `jobmate_agent/blueprints/api/external_jobs.py`
   
4. **job_collections.py** - Implement job collections
   - Reference: `jobmate_agent/blueprints/api/job_collections.py`
   
5. **gap.py** - Implement skill gap analysis
   - Reference: `jobmate_agent/blueprints/api/gap.py`
   
6. **langgraph_router.py** - Implement LangGraph integration
   - Reference: `jobmate_agent/blueprints/api/langgraph.py`
   
7. **langgraph_dev.py** - Implement LangGraph dev features
   - Reference: `jobmate_agent/blueprints/api/langgraph_dev.py`
   
8. **tasks.py** - Implement task management
   - Reference: `jobmate_agent/blueprints/api/tasks.py`

### Step 4: Update Services

Some services may need updates to work with FastAPI's dependency injection:

1. Update import statements from `jobmate_agent.extensions` to `jobmate_agent.extensions_fastapi`
2. Update imports from `jobmate_agent.models` to `jobmate_agent.models_fastapi`
3. Replace `db.session` with session passed via dependency injection

### Step 5: Update External Scripts

Any scripts that use Flask's application context need to be updated:

```python
# OLD (Flask)
from jobmate_agent.app import create_app, db
app = create_app()
with app.app_context():
    # do work
    db.session.commit()

# NEW (FastAPI)
from jobmate_agent.extensions_fastapi import SessionLocal
db = SessionLocal()
try:
    # do work
    db.commit()
finally:
    db.close()
```

### Step 6: Test All Endpoints

Use the automatic API documentation at:
- Swagger UI: http://127.0.0.1:5000/docs
- ReDoc: http://127.0.0.1:5000/redoc

### Step 7: Update Frontend

Update frontend API calls if needed (endpoints remain the same, but response format might differ slightly)

## Benefits of FastAPI

1. **Automatic API Documentation** - Interactive docs at `/docs`
2. **Type Safety** - Pydantic models provide compile-time type checking
3. **Better Performance** - Async support and optimized for speed
4. **Modern Python** - Uses Python 3.7+ features like type hints
5. **Dependency Injection** - Clean, testable code architecture
6. **OpenAPI Standard** - Standards-compliant API specification

## Running in Production

### Using Uvicorn

```bash
uvicorn jobmate_agent.app_fastapi:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Gunicorn with Uvicorn Workers

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker jobmate_agent.app_fastapi:app
```

### Using the ASGI file

```bash
uvicorn asgi:app --host 0.0.0.0 --port 8000
```

## Database Migrations

The database schema remains the same. Continue using Alembic:

```bash
# Make sure SQLALCHEMY_DATABASE_URI is set correctly in environment
alembic revision --autogenerate -m "Migration message"
alembic upgrade head
```

Note: You may need to update migration files to import from `jobmate_agent.models_fastapi` instead of `jobmate_agent.models`.

## Troubleshooting

### Import Errors

If you see import errors:
1. Make sure `jobmate_agent/routers/__init__.py` exists
2. Check that all router files are in `jobmate_agent/routers/`
3. Verify imports in `app_fastapi.py`

### Database Connection Issues

1. Check environment variables (DATABASE_MODE, DATABASE_DEV, DATABASE_PROD)
2. Ensure database URI is correct in `.env` file
3. Check that database migrations are up to date

### Authentication Issues

1. Verify AUTH0_DOMAIN and AUTH0_AUDIENCE are set
2. Check JWT token format
3. Ensure Auth0 configuration is correct

## Next Steps

1. **Complete Router Implementation** - Implement all stub routers
2. **Update Services** - Ensure all services work with FastAPI
3. **Add Tests** - Write tests using FastAPI's TestClient
4. **Performance Optimization** - Add caching, connection pooling
5. **Monitoring** - Add logging, metrics, and health checks

## Parallel Development

Both Flask and FastAPI versions can run side-by-side during migration:

- Flask: `python jobmate_agent/run.py` (port 5000)
- FastAPI: `python run_fastapi.py` (port 5001, for example)

This allows gradual migration and testing.

## Questions?

Refer to:
- FastAPI Documentation: https://fastapi.tiangolo.com/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- Pydantic Documentation: https://docs.pydantic.dev/
