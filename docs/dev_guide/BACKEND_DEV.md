# Backend Development Guide

This guide teaches developers how to work with the Jobmate.Agent Flask backend. The system uses Flask app factory pattern with Auth0 JWT authentication, dual database support (SQLite/PostgreSQL), Chroma vector store (skills collection only in current mode), and S3-backed file uploads.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Environment Configuration](#environment-configuration)
- [Database Management](#database-management)
- [Authentication System](#authentication-system)
- [API Routes & Endpoints](#api-routes--endpoints)
- [Vector Store Integration](#vector-store-integration)
- [File Upload System](#file-upload-system)
- [Creating New Endpoints](#creating-new-endpoints)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Local Development Setup

1. **Create virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Set environment variables** (see [Environment Configuration](#environment-configuration))

3. **Initialize database schema:**
   ```bash
   export FLASK_APP=app:create_app
   flask db upgrade
   ```

4. **Run the application:**
   ```bash
   flask run --port=5001 --debug
   ```
   The app will be available at `http://localhost:5001`

### Production Deployment

```bash
# Set production environment variables
export DATABASE_MODE=postgres
export DATABASE_PROD=postgresql+psycopg2://user:pass@host:5432/dbname

# Run database migrations
flask db upgrade

# Start the application
python run.py
```

## Architecture Overview

### Flask App Factory Pattern

The backend uses Flask's app factory pattern for better testability and configuration:

```python
# app.py
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from extensions import db, migrate

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config.from_object('config.Config')
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, origins=['http://localhost:3000'])
    
    # Register blueprints
    from blueprints.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app
```

### Key Components

- **Authentication**: Auth0 JWT with optional user hydration
- **Database**: SQLite (dev) / PostgreSQL (prod) with Flask-Migrate
- **Vector Store**: Chroma for skills ontology only (no resume/job vectors in current mode)
- **File Storage**: S3 for resume uploads and document management
- **AI Integration**: DeepSeek API for chat functionality

## Environment Configuration

### Required Environment Variables

#### Authentication (Auth0)
```bash
# Auth0 Configuration
AUTH0_DOMAIN=https://dev-xxxxx.us.auth0.com
AUTH0_AUDIENCE=your-api-identifier
AUTH0_MGMT_CLIENT_ID=your-m2m-client-id
AUTH0_MGMT_CLIENT_SECRET=your-m2m-client-secret
```

#### Database Configuration
```bash
# Database Mode Selection
DATABASE_MODE=sqlite  # or 'postgres'

# Development Database (SQLite)
DATABASE_DEV=sqlite:///instance/efficientai.db

# Production Database (PostgreSQL)
DATABASE_PROD=postgresql+psycopg2://user:password@host:5432/dbname
```

#### Vector Store (Chroma)
```bash
# Chroma persistence directory
CHROMA_PERSIST_DIR=./instance/chroma
```

#### File Storage (S3)
```bash
# AWS S3 Configuration
S3_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-southeast-2
```

#### AI Services (DeepSeek)
```bash
# DeepSeek API Configuration
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### Environment-Specific Configuration

#### Development (.env)
```bash
# Development settings
FLASK_ENV=development
DATABASE_MODE=sqlite
CHROMA_PERSIST_DIR=./instance/chroma
```

#### Production (.env.production)
```bash
# Production settings
FLASK_ENV=production
DATABASE_MODE=postgres
CHROMA_PERSIST_DIR=/app/data/chroma
```

## Database Management

### Database Modes

The application supports two database modes:

#### SQLite (Development)
```bash
# Default development database
DATABASE_MODE=sqlite
DATABASE_DEV=sqlite:///instance/efficientai.db
```

**Benefits:**
- No external database setup required
- Fast for development and testing
- File-based storage

#### PostgreSQL (Production)
```bash
# Production database
DATABASE_MODE=postgres
DATABASE_PROD=postgresql+psycopg2://user:password@host:5432/dbname
```

**Benefits:**
- Better performance for production workloads
- Advanced features (JSON columns, full-text search)
- Concurrent access support

### Database Migrations

#### Creating Migrations
```bash
# Create a new migration
export FLASK_APP=app:create_app
flask db migrate -m "Add user profiles table"
```

#### Applying Migrations
```bash
# Apply pending migrations
flask db upgrade

# Downgrade to previous version
flask db downgrade
```

#### Migration Best Practices
```python
# Example migration file
"""Add user profiles table

Revision ID: 1234567890ab
Revises: previous_revision
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create user_profiles table
    op.create_table('user_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('auth0_sub', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('auth0_sub')
    )

def downgrade():
    op.drop_table('user_profiles')
```

## Authentication System

### Auth0 JWT Authentication

The backend uses Auth0 for authentication with JWT tokens:

```python
# jwt_auth.py
from functools import wraps
from flask import g, jsonify, request
import jwt
from jwt import PyJWKClient

def require_jwt(hydrate=False, required_scopes=None):
    """Decorator for JWT-protected routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'missing_or_invalid_authorization'}), 401
            
            token = auth_header.split(' ')[1]
            
            try:
                # Verify JWT token
                payload = verify_jwt_token(token)
                g.jwt_payload = payload
                g.user_sub = payload['sub']
                
                # Optional user hydration
                if hydrate:
                    g.user_profile = get_or_create_user_profile(payload['sub'])
                
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'token_expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'invalid_token'}), 401
            except Exception as e:
                return jsonify({'error': 'auth_failure'}), 401
        
        return decorated_function
    return decorator
```

### Using Authentication in Routes

```python
# Example protected route
from flask import Blueprint, jsonify, g
from jwt_auth import require_jwt

api_bp = Blueprint("api", __name__)

@api_bp.route("/api/me", methods=["GET"])
@require_jwt(hydrate=True)
def get_user_profile():
    """Get current user profile"""
    profile = g.user_profile
    
    return jsonify({
        "id": profile.id,
        "auth0_sub": profile.auth0_sub,
        "email": profile.email,
        "name": profile.name,
        "created_at": profile.created_at.isoformat()
    })

@api_bp.route("/api/protected-data", methods=["GET"])
@require_jwt(required_scopes=['read:data'])
def get_protected_data():
    """Route with scope requirements"""
    return jsonify({"data": "sensitive information"})
```

### Authentication Context

When using `@require_jwt(hydrate=True)`, the following context variables are available:

```python
# Available in protected routes
g.jwt_payload    # Decoded JWT claims
g.user_sub       # Auth0 subject (e.g., 'google-oauth2|123456')
g.user_profile   # UserProfile model instance (when hydrated)
```

### Error Handling

Standard authentication errors:

| Status | Error Code | Description |
|--------|------------|-------------|
| 401 | `missing_or_invalid_authorization` | No or invalid Authorization header |
| 401 | `token_expired` | JWT token has expired |
| 401 | `invalid_token` | JWT token is malformed or invalid |
| 401 | `auth_failure` | General authentication failure |
| 403 | `insufficient_scope` | Token lacks required scopes |
| 404 | `user_not_found_in_auth0` | User not found in Auth0 |
| 502 | `mgmt_api_error` | Auth0 Management API error |
| 500 | `hydrate_failure` | User profile hydration failed |

## API Routes & Endpoints

### Available Endpoints

The backend provides the following main API categories:

- **Health**: `GET /api/ping-protected` (protected)
- **Resumes**: Upload, manage, and download resume files (S3-backed)
- **Jobs**: List, search, and manage job postings with pagination
- **Profile**: User contact information management
- **Chat**: Streaming chat with AI integration

### Example: Resume Upload Endpoint (aligned with current code)

```python
@api_bp.route("/api/resume/upload", methods=["POST"])
@require_jwt(hydrate=True)
def upload_resume():
    """Handle resume upload with S3 storage and processing pipeline"""
    if 'resume_file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['resume_file']
    
    # Validate file type and size
    allowed_extensions = {'.pdf', '.docx', '.txt'}
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        return jsonify({"error": "Invalid file type"}), 400
    
    if len(file.read()) > 10 * 1024 * 1024:  # 10MB limit
        return jsonify({"error": "File too large"}), 400
    
    file.seek(0)  # Reset file pointer
    
    try:
        from jobmate_agent.services.resume_management import ResumePipeline
        pipeline = ResumePipeline()
        result = pipeline.process_uploaded_file(file, g.user_sub, extract_sections=False)
        if result.get("success"):
            return jsonify({
                "resume_id": result.get("resume_id"),
                "message": "Resume uploaded and processed successfully",
                "chunks_created": result.get("chunks_created", 0),
                "text_length": result.get("text_length", 0),
                "s3_key": result.get("s3_key"),
                "bucket": result.get("bucket"),
            })
        return jsonify({"error": result.get("error", "Upload failed")}), 500
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500
```

### Example: Job Listings with Pagination

```python
@api_bp.route("/api/jobs", methods=["GET"])
@require_jwt()
def get_jobs():
    """Get paginated job listings with filters"""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    job_type = request.args.get('job_type')
    location = request.args.get('location')
    
    # Build query with filters
    query = Job.query.filter_by(is_active=True)
    
    if job_type:
        query = query.filter(Job.job_type == job_type)
    if location:
        query = query.filter(Job.location.ilike(f'%{location}%'))
    
    # Pagination
    jobs = query.paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        "jobs": [{
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "job_type": job.job_type,
            "description": job.description,
            "created_at": job.created_at.isoformat()
        } for job in jobs.items],
        "pagination": {
            "total": jobs.total,
            "current_page": jobs.page,
            "total_pages": jobs.pages,
            "has_next": jobs.has_next,
            "has_prev": jobs.has_prev
        }
    })
```

## Vector Store Integration

### Chroma Setup (skill-only mode)

The application uses Chroma for vector storage and semantic search:

```python
# vector_store.py
import chromadb
from chromadb.config import Settings

def init_chroma_client():
    """Initialize Chroma client with persistence"""
    return chromadb.PersistentClient(
        path=os.getenv('CHROMA_PERSIST_DIR', './instance/chroma'),
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )

def init_collections():
    """Initialize required collections"""
    client = init_chroma_client()
    
    collections = {
        'skills_ontology': 'Skills taxonomy and relationships'
    }
    
    for name, description in collections.items():
        try:
            client.get_collection(name)
        except ValueError:
            client.create_collection(
                name=name,
                metadata={"description": description}
            )
```

### Using Vector Store

```python
# In current mode, only the skills_ontology collection is used.
```

## File Upload System

### S3 Integration

The application uses AWS S3 for file storage with a simple S3Manager class:

```python
# s3_client.py
import boto3
from botocore.exceptions import ClientError

class S3Manager:
    def __init__(self):
        self.client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'ap-southeast-2')
        )
        self.bucket = os.getenv('S3_BUCKET_NAME')
    
    def upload_file(self, file_obj, key):
        """Upload file to S3"""
        try:
            self.client.upload_fileobj(file_obj, self.bucket, key)
            return f"https://{self.bucket}.s3.amazonaws.com/{key}"
        except ClientError as e:
            raise Exception(f"Error uploading file: {e}")
```

**Key Features:**
- File validation (type and size limits)
- S3 key generation with user-specific paths
- Database record creation
- Error handling for upload failures

## Creating New Endpoints

### Step 1: Define the Route

```python
# In blueprints/api.py
@api_bp.route("/api/new-feature", methods=["GET"])
@require_jwt(hydrate=True)
def get_new_feature():
    """Get new feature data"""
    # Implementation here
    pass
```

### Step 2: Add Database Models (if needed)

```python
# In models.py
class NewFeature(db.Model):
    __tablename__ = 'new_features'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_profiles.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('UserProfile', backref='new_features')
```

### Step 3: Create Migration

```bash
# Create migration for new model
flask db migrate -m "Add new features table"
flask db upgrade
```

### Step 4: Implement Endpoint Logic

```python
@api_bp.route("/api/new-features", methods=["GET"])
@require_jwt(hydrate=True)
def get_new_features():
    """Get user's new features"""
    features = NewFeature.query.filter_by(user_id=g.user_profile.id).all()
    
    return jsonify({
        "features": [{
            "id": feature.id,
            "name": feature.name,
            "description": feature.description,
            "created_at": feature.created_at.isoformat()
        } for feature in features]
    })

@api_bp.route("/api/new-features", methods=["POST"])
@require_jwt(hydrate=True)
def create_new_feature():
    """Create a new feature"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('name'):
        return jsonify({"error": "Name is required"}), 400
    
    # Create new feature
    feature = NewFeature(
        user_id=g.user_profile.id,
        name=data['name'],
        description=data.get('description', '')
    )
    
    db.session.add(feature)
    db.session.commit()
    
    return jsonify({
        "id": feature.id,
        "name": feature.name,
        "description": feature.description,
        "created_at": feature.created_at.isoformat()
    }), 201
```

## Best Practices

### 1. Error Handling

```python
# Consistent error responses
def handle_error(error_code, message, status_code=400):
    return jsonify({
        "error": error_code,
        "message": message
    }), status_code

# Usage in endpoints
@api_bp.route("/api/example", methods=["POST"])
@require_jwt()
def example_endpoint():
    try:
        # Endpoint logic
        pass
    except ValueError as e:
        return handle_error("validation_error", str(e), 400)
    except Exception as e:
        return handle_error("server_error", "Internal server error", 500)
```

### 2. Input Validation

```python
from marshmallow import Schema, fields, ValidationError

class NewFeatureSchema(Schema):
    name = fields.Str(required=True, validate=lambda x: len(x) > 0)
    description = fields.Str(missing="")

@api_bp.route("/api/new-features", methods=["POST"])
@require_jwt()
def create_new_feature():
    try:
        data = NewFeatureSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({"error": "validation_error", "details": e.messages}), 400
    
    # Use validated data
    pass
```

### 3. Database Transactions

```python
# Use database transactions for complex operations
@api_bp.route("/api/complex-operation", methods=["POST"])
@require_jwt()
def complex_operation():
    try:
        with db.session.begin():
            # Multiple database operations
            obj1 = Model1(...)
            obj2 = Model2(...)
            
            db.session.add(obj1)
            db.session.add(obj2)
            # Transaction will be committed automatically
    except Exception as e:
        # Transaction will be rolled back automatically
        return jsonify({"error": "operation_failed"}), 500
```

### 4. Logging

```python
import logging

logger = logging.getLogger(__name__)

@api_bp.route("/api/example", methods=["POST"])
@require_jwt()
def example_endpoint():
    logger.info(f"Processing request for user {g.user_sub}")
    
    try:
        # Endpoint logic
        logger.info("Request processed successfully")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        return jsonify({"error": "server_error"}), 500
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Check database configuration
   echo $DATABASE_MODE
   echo $DATABASE_DEV
   echo $DATABASE_PROD
   
   # Test database connection
   flask shell
   >>> from app import create_app
   >>> app = create_app()
   >>> with app.app_context():
   ...     from extensions import db
   ...     db.engine.execute('SELECT 1')
   ```

2. **Auth0 Authentication Issues**
   ```bash
   # Verify Auth0 configuration
   echo $AUTH0_DOMAIN
   echo $AUTH0_AUDIENCE
   
   # Test JWT token
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:5000/api/ping-protected
   ```

3. **S3 Upload Failures**
   ```bash
   # Check AWS credentials
   aws s3 ls s3://$S3_BUCKET_NAME
   
   # Verify bucket permissions
   aws s3api get-bucket-acl --bucket $S3_BUCKET_NAME
   ```

4. **Chroma Vector Store Issues**
   ```bash
   # Check Chroma directory
   ls -la $CHROMA_PERSIST_DIR
   
   # Reset Chroma if needed
   rm -rf $CHROMA_PERSIST_DIR
   ```

### Debug Mode

Enable debug logging for development:

```python
# In app.py
import logging

if app.config['DEBUG']:
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Performance Monitoring

```python
# Add request timing
import time
from flask import g

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        response.headers['X-Response-Time'] = f"{duration:.3f}s"
    return response
```

This guide provides comprehensive coverage of the Flask backend architecture, from basic setup to advanced features like vector storage and file uploads. Follow these patterns to maintain consistency and reliability in your backend development.
