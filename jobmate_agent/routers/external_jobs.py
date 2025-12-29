"""FastAPI router for external job fetching endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from jobmate_agent.extensions_fastapi import get_db

router = APIRouter()


@router.post("/external-jobs/fetch")
async def fetch_external_jobs(
    db: Session = Depends(get_db),
):
    """Fetch jobs from external APIs."""
    # TODO: Implement external job fetching
    return {"message": "External job fetching - to be implemented"}
