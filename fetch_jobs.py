"""
Simple script to fetch external jobs from LinkedIn API
Run this script to populate your database with job listings
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from jobmate_agent.services.external_apis.external_job_fetcher import fetchJobFromExternal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("   External Job Fetcher - LinkedIn API")
    print("="*60 + "\n")
    
    # Fetch jobs with optimized parameters
    logger.info("Starting job fetch from LinkedIn API...")
    
    result = fetchJobFromExternal(
        keywords=[
            "Python developer",
            "Software engineer",
            "Data engineer"
        ],
        locations=[
            "Sydney",
            "Melbourne",
            "Australia"
        ],
        job_types=[
            "fullTime"
        ],
        max_jobs_per_search=20,  # Get 20 jobs per search
        delay_between_requests=2.0  # Wait 2 seconds between API calls
    )
    
    print("\n" + "="*60)
    print("   RESULTS")
    print("="*60)
    print(f"✓ Fetched from API:     {result['fetched']} jobs")
    print(f"✓ Saved to database:    {result['saved']} new jobs")
    print(f"✓ Duplicates skipped:   {result['duplicates']} jobs")
    print(f"✓ API calls used:       {result['api_calls_used']}/25 monthly")
    print("="*60 + "\n")
    
    logger.info("Job fetching completed successfully!")
