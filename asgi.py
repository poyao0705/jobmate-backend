"""
ASGI configuration for FastAPI application.
Use with production ASGI servers like uvicorn or gunicorn.

Example usage:
    uvicorn asgi:app --host 0.0.0.0 --port 8000
    gunicorn -w 4 -k uvicorn.workers.UvicornWorker asgi:app
"""
from jobmate_agent.app_fastapi import app

# For production deployment
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
