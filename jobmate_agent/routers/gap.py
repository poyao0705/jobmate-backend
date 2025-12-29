"""FastAPI router for skill gap analysis endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Tuple, Dict, Any

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile

router = APIRouter()


@router.post("/skill-gap-report")
async def create_skill_gap_report(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Create a skill gap report."""
    # TODO: Implement skill gap analysis
    return {"message": "Skill gap report - to be implemented"}
