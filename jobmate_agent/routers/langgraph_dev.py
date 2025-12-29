"""FastAPI router for LangGraph dev endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from jobmate_agent.extensions_fastapi import get_db

router = APIRouter()


@router.post("/langgraph-dev/test")
async def langgraph_dev_test(
    db: Session = Depends(get_db),
):
    """LangGraph dev test endpoint."""
    # TODO: Implement LangGraph dev features
    return {"message": "LangGraph dev - to be implemented"}
