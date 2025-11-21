from langchain_core.tools import tool

@tool
def get_job_details(job_id: int):
    """
    Retrieves the details of a job posting by its ID.
    Returns the job title, description, and requirements.
    """
    # Mock implementation for now
    return f"Job Details for ID {job_id}: Title: Python Developer. Description: We need a Python expert."
