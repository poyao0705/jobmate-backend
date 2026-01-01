"""FastAPI router for user profile endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import Tuple, Dict, Any

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.models_fastapi import UserProfile
from jobmate_agent.schemas import UserProfileResponse, UserProfileUpdate
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile

router = APIRouter()


@router.get("/user-profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get the current user's profile."""
    jwt_payload, user_profile = user_data
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    return user_profile


@router.put("/user-profile", response_model=UserProfileResponse)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Update the current user's profile."""
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Update fields
    for field, value in profile_update.model_dump(exclude_unset=True).items():
        setattr(user_profile, field, value)
    
    db.commit()
    db.refresh(user_profile)
    
    return user_profile


@router.get("/contact-info")
async def get_contact_info(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get the current user's contact information."""
    jwt_payload, user_profile = user_data
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    return {
        "contact_name": user_profile.contact_name,
        "contact_email": user_profile.contact_email,
        "contact_phone_number": user_profile.contact_phone_number,
        "contact_location": user_profile.contact_location,
    }


@router.put("/contact-info")
async def update_contact_info(
    contact_data: Dict[str, Any],
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Update the current user's contact information."""
    jwt_payload, user_profile = user_data
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Update contact fields
    allowed_fields = {"contact_name", "contact_email", "contact_phone_number", "contact_location"}
    for field, value in contact_data.items():
        if field in allowed_fields:
            setattr(user_profile, field, value)
    
    db.commit()
    db.refresh(user_profile)
    
    return {
        "contact_name": user_profile.contact_name,
        "contact_email": user_profile.contact_email,
        "contact_phone_number": user_profile.contact_phone_number,
        "contact_location": user_profile.contact_location,
    }
