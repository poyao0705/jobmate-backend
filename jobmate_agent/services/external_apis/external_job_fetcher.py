"""
External Job Fetching Service
Integrates with LinkedIn Job Search API via RapidAPI to fetch job listings
and store them in the PostgreSQL database.
"""

import os
import sys
import requests
import json
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass

# Add parent directory to Python path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobmate_agent.app import create_app
from jobmate_agent.models import JobListing
from jobmate_agent.extensions import db

# Configure to use PostgreSQL for external job fetching
os.environ["DATABASE_MODE"] = "postgres"

logger = logging.getLogger(__name__)


@dataclass
class ExternalJobData:
    """Data structure for jobs fetched from external API"""

    title: str
    company: str
    location: Optional[str] = None
    job_type: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    external_url: Optional[str] = None
    external_id: Optional[str] = None
    company_logo_url: Optional[str] = None
    required_skills: List[str] = None
    preferred_skills: List[str] = None
    is_remote: bool = False


class LinkedInJobFetcher:
    """LinkedIn Job Search API client via RapidAPI"""

    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        self.api_host = os.getenv(
            "RAPIDAPI_HOST", "linkedin-job-search-api.p.rapidapi.com"
        )
        self.base_url = f"https://{self.api_host}"

        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY environment variable is required")

        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }

    def search_jobs(
        self,
        keywords: str = "software developer",
        location: str = "Australia",
        datePosted: str = "pastWeek",  # Changed default to pastWeek for 7-day API
        jobType: str = "fullTime",
        remote: str = "false",
        limit: int = 10,
    ) -> List[Dict]:
        """
        Search for jobs using LinkedIn Job Search API (7-day endpoint)
        Based on RapidAPI documentation: /active-jp-7d endpoint

        Args:
            keywords: Job search keywords (e.g., "Python developer", "Data engineer")
            location: Job location (e.g., "Australia", "Sydney", "Melbourne")
            datePosted: pastWeek (recommended), pastMonth, anyTime, past24Hours
            jobType: fullTime, partTime, contract, temporary, volunteer, internship
            remote: "true" or "false"
            limit: Number of jobs to fetch (max 100 per request)

        Returns:
            List of job dictionaries from the API
        """

        # Use the correct 7-day endpoint: /active-jb-7d (not jp)
        # Based on the RapidAPI documentation showing /active-jb-7d
        endpoint = f"{self.base_url}/active-jb-7d"

        # Parameters based on the RapidAPI documentation
        params = {
            "title_filter": keywords,  # Use title_filter instead of keywords
            "location_filter": location,  # Use location_filter instead of location
            "description_type": "text",  # Required parameter
            "limit": str(min(limit, 100)),  # API max is 100
            "offset": "0",  # Start from beginning
        }

        try:
            logger.info(f"Searching LinkedIn jobs (7-day): '{keywords}' in {location}")
            logger.debug(f"Endpoint: {endpoint}")
            logger.debug(f"Parameters: {params}")

            response = requests.get(
                endpoint, headers=self.headers, params=params, timeout=30
            )

            logger.info(f"Response status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()

                    # Handle different response structures
                    if isinstance(data, list):
                        # Direct list of jobs
                        jobs = data
                    elif isinstance(data, dict):
                        # Check for common wrapper keys
                        jobs = data.get(
                            "jobs", data.get("data", data.get("results", []))
                        )
                    else:
                        jobs = []

                    logger.info(f"Found {len(jobs)} jobs from LinkedIn API (7-day)")
                    if jobs and len(jobs) > 0:
                        logger.debug(
                            f"Sample job keys: {list(jobs[0].keys()) if isinstance(jobs[0], dict) else 'Invalid job format'}"
                        )
                        logger.debug(
                            f"Sample job title: {jobs[0].get('title', 'No title') if isinstance(jobs[0], dict) else 'N/A'}"
                        )

                    return jobs

                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON response: {e}")
                    logger.debug(f"Response text preview: {response.text[:300]}...")
                    return []
            else:
                logger.error(
                    f"API Error {response.status_code}: {response.text[:300]}..."
                )
                return []

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after 30 seconds")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching jobs from LinkedIn API: {e}")
            return []

    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """Get detailed information for a specific job"""
        endpoint = f"{self.base_url}/v2/jobs/{job_id}"

        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching job details for {job_id}: {e}")
            return None


def parse_linkedin_job(job_data: Dict) -> ExternalJobData:
    """
    Parse LinkedIn API job data into our ExternalJobData format
    Based on the API response fields from RapidAPI documentation

    Args:
        job_data: Raw job data from LinkedIn API

    Returns:
        ExternalJobData object
    """

    # Extract skills from description/requirements if available
    skills = []
    description = job_data.get("description_text", job_data.get("description", ""))

    # Simple skill extraction (can be enhanced with NLP)
    common_skills = [
        "Python",
        "JavaScript",
        "Java",
        "React",
        "Node.js",
        "SQL",
        "AWS",
        "Azure",
        "Docker",
        "Kubernetes",
        "Git",
        "MongoDB",
        "PostgreSQL",
        "Redis",
        "TypeScript",
        "Angular",
        "Vue.js",
        "HTML",
        "CSS",
        "REST API",
        "GraphQL",
        "Machine Learning",
        "AI",
        "Data Science",
        "DevOps",
        "Agile",
        "Scrum",
        "Django",
        "Flask",
        "Spring",
    ]

    if description:
        description_lower = description.lower()
        for skill in common_skills:
            if skill.lower() in description_lower:
                skills.append(skill)

    # Parse salary if available
    salary_min = None
    salary_max = None

    # Check for salary_raw field from API response
    salary_info = job_data.get("salary_raw", {})
    if isinstance(salary_info, dict):
        salary_min = salary_info.get("min")
        salary_max = salary_info.get("max")
    elif isinstance(salary_info, str) and salary_info:
        # Try to extract numbers from salary string
        import re

        numbers = re.findall(r"\d+", salary_info.replace(",", ""))
        if len(numbers) >= 2:
            salary_min = (
                int(numbers[0]) * 1000 if len(numbers[0]) <= 3 else int(numbers[0])
            )
            salary_max = (
                int(numbers[1]) * 1000 if len(numbers[1]) <= 3 else int(numbers[1])
            )
        elif len(numbers) == 1:
            salary_min = (
                int(numbers[0]) * 1000 if len(numbers[0]) <= 3 else int(numbers[0])
            )

    # Determine if remote based on API fields
    is_remote = False
    try:
        location_type = job_data.get("location_type", "")
        title = job_data.get("title", "")
        locations_raw = job_data.get("locations_raw", "")
        locations_derived = job_data.get("locations_derived", [])

        # Check location_type
        if location_type == "TELECOMMUTE":
            is_remote = True

        # Check title
        if isinstance(title, str) and "remote" in title.lower():
            is_remote = True

        # Check locations_raw
        if isinstance(locations_raw, str) and "remote" in locations_raw.lower():
            is_remote = True

        # Check locations_derived (handle list safely)
        if isinstance(locations_derived, list):
            for loc in locations_derived:
                if isinstance(loc, str) and "remote" in loc.lower():
                    is_remote = True
                    break
    except Exception as e:
        logger.warning(f"Error checking remote status: {e}")
        is_remote = False

    # Get employment type
    employment_type = job_data.get("employment_type", "FULL_TIME")

    # Build the location string safely
    location = None
    try:
        locations_derived = job_data.get("locations_derived", [])
        locations_raw = job_data.get("locations_raw", "")

        if isinstance(locations_derived, list) and len(locations_derived) > 0:
            # Filter out None values and convert to strings
            valid_locations = [
                str(loc) for loc in locations_derived[:2] if loc is not None
            ]
            if valid_locations:
                location = ", ".join(valid_locations)
        elif isinstance(locations_raw, str) and locations_raw:
            location = locations_raw
    except Exception as e:
        logger.warning(f"Error building location: {e}")
        location = "Unknown Location"

    return ExternalJobData(
        title=job_data.get("title", "Untitled Position"),
        company=job_data.get(
            "organization", job_data.get("company", "Unknown Company")
        ),
        location=location,
        job_type=employment_type,
        description=description,
        requirements=job_data.get("requirements", ""),
        salary_min=salary_min,
        salary_max=salary_max,
        external_url=job_data.get("url", job_data.get("job_url")),
        external_id=str(job_data.get("id", job_data.get("job_id", ""))),
        company_logo_url=job_data.get(
            "organization_logo", job_data.get("company_logo")
        ),
        required_skills=skills[:10],  # Limit to 10 skills
        preferred_skills=[],
        is_remote=is_remote,
    )


def save_job_to_database(job_data: ExternalJobData) -> Optional[JobListing]:
    """
    Save an external job to the PostgreSQL database

    Args:
        job_data: ExternalJobData object

    Returns:
        JobListing object if successful, None if failed
    """

    try:
        # Check if job already exists (by external_id)
        if job_data.external_id:
            existing_job = JobListing.query.filter_by(
                external_id=job_data.external_id, source="LinkedIn"
            ).first()

            if existing_job:
                logger.info(
                    f"Job already exists: {job_data.title} at {job_data.company}"
                )
                return existing_job

        # Create new job listing
        new_job = JobListing(
            title=job_data.title,
            company=job_data.company,
            location=job_data.location,
            job_type=job_data.job_type,
            description=job_data.description,
            requirements=job_data.requirements,
            salary_min=job_data.salary_min,
            salary_max=job_data.salary_max,
            salary_currency="USD",
            external_url=job_data.external_url,
            external_id=job_data.external_id,
            source="LinkedIn",
            company_logo_url=job_data.company_logo_url,
            company_website=None,
            required_skills=job_data.required_skills or [],
            preferred_skills=job_data.preferred_skills or [],
            is_active=True,
            is_remote=job_data.is_remote,
            date_posted=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.session.add(new_job)
        db.session.commit()

        logger.info(f"Saved job: {job_data.title} at {job_data.company}")
        return new_job

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving job {job_data.title}: {e}")
        return None


def fetchJobFromExternal(
    keywords: List[str] = None,
    locations: List[str] = None,
    job_types: List[str] = None,
    max_jobs_per_search: int = 50,  # Increased since we have fewer calls
    delay_between_requests: float = 2.0,  # Increased delay to be respectful
) -> Dict[str, int]:
    """
    OPTIMIZED for 25 API calls/month limit - Weekly execution strategy

    Main function to fetch jobs from external LinkedIn API and store in PostgreSQL

    Args:
        keywords: List of search keywords (recommended: 3-5 high-value terms)
        locations: List of locations (recommended: 2-3 main cities)
        job_types: List of job types (recommended: 1-2 types)
        max_jobs_per_search: Jobs per API call (50 recommended for efficiency)
        delay_between_requests: Delay between calls (2+ seconds recommended)

    Returns:
        Dictionary with statistics: {"fetched": X, "saved": Y, "duplicates": Z, "api_calls_used": Z}
    """

    # OPTIMIZED defaults for 25 API calls/month (more job types = fewer keywords)
    if keywords is None:
        keywords = [
            "Software engineer Australia",  # Combined for efficiency - broader search
            "Data engineer Sydney Melbourne",
            "Software developer full stack",
            "DevOps engineer cloud",  # 4 strategic searches
        ]

    if locations is None:
        locations = ["Australia"]  # Use broader location, specify in keywords

    if job_types is None:
        job_types = [
            "fullTime",
            "partTime",
            "internship",
            "contract",
        ]  # Include all job types

    # Initialize the fetcher
    try:
        fetcher = LinkedInJobFetcher()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return {"fetched": 0, "saved": 0, "duplicates": 0, "api_calls_used": 0}

    # Initialize Flask app context
    app = create_app()

    stats = {"fetched": 0, "saved": 0, "duplicates": 0, "api_calls_used": 0}

    with app.app_context():
        logger.info(
            "Starting OPTIMIZED external job fetching (25 calls/month limit)..."
        )
        logger.info(
            f"Strategy: {len(keywords)} keywords × {len(locations)} locations × {len(job_types)} job types"
        )
        logger.info(
            f"Max API calls this run: {len(keywords) * len(locations) * len(job_types)}"
        )

        # Search for jobs with optimized combinations
        for keyword in keywords:
            for location in locations:
                for job_type in job_types:
                    try:
                        logger.info(
                            f"API Call {stats['api_calls_used'] + 1}: '{keyword}' in {location} ({job_type})"
                        )

                        # Fetch jobs from API (7-day endpoint)
                        jobs = fetcher.search_jobs(
                            keywords=keyword,
                            location=location,
                            jobType=job_type,  # Now using the job_type parameter
                            limit=max_jobs_per_search,
                            datePosted="pastWeek",  # 7-day data
                        )

                        stats["fetched"] += len(jobs)
                        stats["api_calls_used"] += 1

                        # Process each job
                        for job_raw in jobs:
                            # Parse job data
                            job_data = parse_linkedin_job(job_raw)

                            # Save to database
                            saved_job = save_job_to_database(job_data)

                            if saved_job:
                                if saved_job.created_at.date() == datetime.now().date():
                                    stats["saved"] += 1
                                else:
                                    stats["duplicates"] += 1

                        # Rate limiting delay - be respectful to API
                        logger.debug(
                            f"Waiting {delay_between_requests}s before next call..."
                        )
                        time.sleep(delay_between_requests)

                    except Exception as e:
                        logger.error(
                            f"Error processing search '{keyword}' in {location} ({job_type}): {e}"
                        )
                        stats["api_calls_used"] += 1  # Count failed calls too
                        continue

        logger.info("Optimized job fetching completed!")
        logger.info("Statistics:")
        logger.info(f"   • API calls used: {stats['api_calls_used']}/25 monthly limit")
        logger.info(f"   • Fetched from API: {stats['fetched']} jobs")
        logger.info(f"   • Saved to database: {stats['saved']} new jobs")
        logger.info(f"   • Duplicates skipped: {stats['duplicates']} jobs")
        logger.info(f"   • Remaining calls this month: {25 - stats['api_calls_used']}")

        return stats


if __name__ == "__main__":
    # Example usage
    logger.info("Testing external job fetching...")

    # Test with a small search first
    result = fetchJobFromExternal(
        keywords=["Software engineer"],
        locations=["Sydney"],
        job_types=["fullTime", "partTime"],
        max_jobs_per_search=5,
    )

    logger.info(f"Test completed: {result}")
