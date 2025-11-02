from jobmate_agent.jwt_auth import require_jwt
from flask import request, jsonify, g
from jobmate_agent.models import UserProfile
from jobmate_agent.extensions import db
from jobmate_agent.blueprints.api import api_bp
import phonenumbers
from phonenumbers import NumberParseException
import re


def validate_email(email):
    """
    Validate email address format.

    Args:
        email (str): Email address to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not email or email.strip() == "":
        return False, "Email is required"

    # Basic email regex pattern
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_regex, email):
        return False, "Invalid email format"

    # Additional checks
    if len(email) > 254:
        return False, "Email address is too long"

    if ".." in email:
        return False, "Email cannot contain consecutive dots"

    if email.startswith(".") or email.endswith("."):
        return False, "Email cannot start or end with a dot"

    return True, ""


def validate_phone_number(phone_number):
    """
    Validate and format phone number using international standards.

    Args:
        phone_number (str): Phone number to validate

    Returns:
        tuple: (is_valid: bool, formatted_number: str, error_message: str)
    """
    if not phone_number or phone_number.strip() == "":
        return True, "", ""

    try:
        # Parse the phone number (assume it's in international format)
        parsed_number = phonenumbers.parse(phone_number, None)

        # Check if it's a valid number
        if not phonenumbers.is_valid_number(parsed_number):
            return False, "", "Invalid phone number format"

        # Format the number in international format
        formatted = phonenumbers.format_number(
            parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        return True, formatted, ""

    except NumberParseException as e:
        return False, "", f"Invalid phone number: {e}"
    except Exception as e:
        return False, "", f"Error validating phone number: {e}"


@api_bp.route("/contact-info", methods=["GET"])
@require_jwt(hydrate=True)
def get_user_profile():
    profile = db.session.get(UserProfile, g.user_sub)
    if not profile:
        return jsonify({"error": "User profile not found"}), 404

    return jsonify(
        {
            "name": profile.contact_name or "",
            "email": profile.contact_email or "",
            "phone_number": profile.contact_phone_number or "",
            "location": profile.contact_location or "",
        }
    )


@api_bp.route("/contact-info", methods=["PUT"])
@require_jwt(hydrate=True)
def update_user_profile():
    profile = db.session.get(UserProfile, g.user_sub)
    if not profile:
        return jsonify({"error": "User profile not found"}), 404

    if not request.json:
        return jsonify({"error": "Request body is required"}), 400

    try:
        # Validate email
        email = request.json.get("email", "")
        is_valid_email, email_error_msg = validate_email(email)
        if not is_valid_email:
            return (
                jsonify(
                    {
                        "error": "Email validation failed",
                        "details": email_error_msg,
                        "field": "email",
                    }
                ),
                400,
            )

        # Validate phone number if provided
        phone_number = request.json.get("phone_number", "")
        if phone_number:
            is_valid, formatted_phone, error_msg = validate_phone_number(phone_number)
            if not is_valid:
                return (
                    jsonify(
                        {
                            "error": "Phone number validation failed",
                            "details": error_msg,
                            "field": "phone_number",
                        }
                    ),
                    400,
                )
            phone_number = formatted_phone

        # Update contact information
        profile.contact_name = request.json.get("name", "")
        profile.contact_email = email
        profile.contact_phone_number = phone_number
        profile.contact_location = request.json.get("location", "")

        db.session.commit()

        # Return updated profile data
        return jsonify(
            {
                "name": profile.contact_name or "",
                "email": profile.contact_email or "",
                "phone_number": profile.contact_phone_number or "",
                "location": profile.contact_location or "",
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update profile", "details": str(e)}), 500
