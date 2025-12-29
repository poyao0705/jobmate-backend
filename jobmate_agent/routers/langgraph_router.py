"""FastAPI router for LangGraph endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Tuple, Dict, Any

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile

router = APIRouter()


@router.post("/langgraph/chat")
async def langgraph_chat(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """LangGraph chat endpoint."""
    # TODO: Implement LangGraph integration
    return {"message": "LangGraph chat - to be implemented"}
