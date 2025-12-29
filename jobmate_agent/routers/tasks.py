"""FastAPI router for task management endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Tuple, Dict, Any

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile

router = APIRouter()


@router.get("/tasks")
async def get_tasks(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get all tasks for the current user."""
    # TODO: Implement task listing
    return {"tasks": []}


@router.post("/tasks")
async def create_task(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Create a new task."""
    # TODO: Implement task creation
    return {"message": "Task creation - to be implemented"}
