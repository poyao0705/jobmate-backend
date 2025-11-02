from typing import Dict, Any

from jobmate_agent.models import UserProfile


def upsert_user_profile(session, profile: Dict[str, Any]) -> UserProfile:
    """Upsert an Auth0 user profile keyed by sub into UserProfile."""
    sub = profile.get("sub")
    if not sub:
        raise ValueError("profile must include 'sub'")

    user_profile: UserProfile = session.get(UserProfile, sub)
    is_new = user_profile is None
    if is_new:
        user_profile = UserProfile(id=sub)
    user_profile.email = profile.get("email")
    user_profile.email_verified = bool(profile.get("email_verified", False))
    user_profile.name = profile.get("name")
    user_profile.picture = profile.get("picture")

    # For new profiles, duplicate name and email to contact fields
    if is_new:
        user_profile.contact_name = profile.get("name")
        user_profile.contact_email = profile.get("email")
        user_profile.contact_phone_number = None
        user_profile.contact_location = None

    session.add(user_profile)
    session.commit()
    return user_profile
