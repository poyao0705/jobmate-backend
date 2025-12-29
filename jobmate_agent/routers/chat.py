"""FastAPI router for chat endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Tuple, Dict, Any

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile

router = APIRouter()


@router.get("/chats")
async def get_chats(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get all chats for the current user."""
    # TODO: Implement chat listing
    return {"chats": []}


@router.post("/chats")
async def create_chat(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Create a new chat."""
    # TODO: Implement chat creation
    return {"message": "Chat endpoint - to be implemented"}
