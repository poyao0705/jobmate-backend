# External Job Fetching Integration

**Status: ✅ IMPLEMENTED** - This document explains how to set up and use the external job fetching functionality that integrates with LinkedIn Job Search API via RapidAPI.

## Current Implementation Status

- **Vector Database**: ChromaDB with O*NET skills (32,681 skills) - fully populated
- **Gap Analyzer**: Level-aware skill gap analysis with O*NET integration
- **Career Engine**: Complete implementation with skill extraction, mapping, and reporting
- **External Job Fetching**: LinkedIn Job Search API integration via RapidAPI
- **Database Sync**: PostgreSQL ↔ SQLite synchronization for development workflow

## 📋 Overview

The external job fetching system automatically:
1. Searches for jobs using LinkedIn Job Search API
2. Parses and normalizes the job data
3. Stores jobs in your PostgreSQL database
4. Avoids duplicates by checking external IDs
5. Extracts skills from job descriptions using O*NET mapping
6. Integrates with the Career Engine for skill gap analysis
7. Syncs data between PostgreSQL and SQLite for development

## 🔧 Setup

### 1. Get RapidAPI Access

1. Go to [RapidAPI LinkedIn Job Search API](https://rapidapi.com/fantastic-jobs-fantastic-jobs-default/api/linkedin-job-search-api)
2. Subscribe to a plan (they have free tiers)
3. Get your API key from the dashboard

### 2. Configure Environment Variables

Update your `.env` file:

```bash
# RapidAPI Configuration for LinkedIn Job Search
RAPIDAPI_KEY=your_actual_rapidapi_key_here
RAPIDAPI_HOST=linkedin-job-search-api.p.rapidapi.com
```

### 3. Test the Setup

Run the test script:

```bash
python test_external_jobs.py
```

## 🚀 Usage

### API Endpoints

#### 1. Test API Connection
```http
POST /api/jobs/fetch-external/test
Content-Type: application/json
Authorization: Bearer YOUR_JWT_TOKEN

{
    "keywords": "Python developer",
    "location": "Sydney",
    "limit": 3
}
```

#### 2. Fetch Jobs (Async)
```http
POST /api/jobs/fetch-external
Content-Type: application/json
Authorization: Bearer YOUR_JWT_TOKEN

{
    "keywords": ["Python developer", "Data engineer"],
    "locations": ["Australia", "Sydney", "Melbourne"],
    "job_types": ["fullTime", "contract"],
    "max_jobs_per_search": 20,
    "run_async": true
}
```

#### 3. Check Fetch Status
```http
GET /api/jobs/fetch-status/{task_id}
Authorization: Bearer YOUR_JWT_TOKEN
```

#### 4. List All Fetch Tasks
```http
GET /api/jobs/fetch-tasks
Authorization: Bearer YOUR_JWT_TOKEN
```

### Python Function Usage

```python
from services.external_job_fetcher import fetchJobFromExternal

# Fetch jobs with custom parameters
result = fetchJobFromExternal(
    keywords=["Python developer", "Data scientist"],
    locations=["Sydney", "Melbourne", "Brisbane"],
    job_types=["fullTime", "contract"],
    max_jobs_per_search=25
)

print(f"Fetched: {result['fetched']}, Saved: {result['saved']}")
```

## 🔗 Career Engine Integration

The external job fetching system integrates seamlessly with the Career Engine:

### Skill Extraction & Mapping
- Jobs are automatically processed through the Career Engine's skill extraction pipeline
- O*NET skills are mapped to job descriptions using vector similarity search
- Skill levels are estimated for both required and preferred skills
- Gap analysis can be performed immediately after job ingestion

### Database Integration
- Jobs are stored in both PostgreSQL (production) and SQLite (development)
- O*NET skills database is shared across all components
- Vector database (ChromaDB) contains O*NET skill embeddings
- Skill gap reports are generated and stored for analysis

### API Endpoints
- `/api/backend/job/analyze-gap` - Analyze skills gap between resume and job
- `/api/backend/job/<id>/skills` - Get O*NET skill mappings for a job
- `/api/backend/job/<id>/gap-report` - Get detailed gap analysis report

## 📊 Data Mapping

| LinkedIn API Field | Database Field | Notes |
|-------------------|---------------|-------|
| `title` | `title` | Job title |
| `company` | `company` | Company name |
| `location` | `location` | Job location |
| `description` | `description` | Full job description |
| `salary.min/max` | `salary_min/max` | Salary range |
| `url` | `external_url` | Link to original posting |
| `id` | `external_id` | LinkedIn job ID |
| Auto-extracted | `required_skills` | Skills found in description using O*NET mapping |
| O*NET mapped | `job_skills` | O*NET skill mappings via Career Engine |

## 🎯 Search Parameters

### Keywords
Common effective search terms:
- "Python developer"
- "Data engineer"
- "Full stack developer"
- "Machine learning engineer"
- "DevOps engineer"
- "Software architect"

### Locations
- Country: "Australia", "United States"
- City: "Sydney", "Melbourne", "New York"
- State: "New South Wales", "Victoria"

### Job Types
- `fullTime` - Full-time positions
- `partTime` - Part-time positions
- `contract` - Contract/freelance
- `temporary` - Temporary positions
- `volunteer` - Volunteer work
- `internship` - Internship positions

### Date Posted Options
- `anyTime` - All time
- `pastWeek` - Last 7 days
- `pastMonth` - Last 30 days
- `past24Hours` - Last 24 hours

## 🔄 Automation Options

### 1. Scheduled Fetching (Recommended)

Create a cron job or scheduled task:

```bash
# Fetch jobs every 6 hours
0 */6 * * * cd /path/to/jobmate && python -c "from services.external_job_fetcher import fetchJobFromExternal; fetchJobFromExternal()"
```

### 2. AWS Lambda Function

Deploy the fetcher as a Lambda function for serverless automation:

```python
import json
from services.external_job_fetcher import fetchJobFromExternal

def lambda_handler(event, context):
    result = fetchJobFromExternal(
        keywords=event.get('keywords', ["Python developer"]),
        locations=event.get('locations', ["Australia"]),
        max_jobs_per_search=20
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
```

### 3. GitHub Actions

Create `.github/workflows/fetch-jobs.yml`:

```yaml
name: Fetch External Jobs
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:  # Manual trigger

jobs:
  fetch-jobs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Fetch jobs
        env:
          RAPIDAPI_KEY: ${{ secrets.RAPIDAPI_KEY }}
          DATABASE_PROD: ${{ secrets.DATABASE_PROD }}
        run: python -c "from services.external_job_fetcher import fetchJobFromExternal; fetchJobFromExternal()"
```

## 📈 Performance & Limits

### API Limits
- Free tier: Usually 100-1000 requests/month
- Check your RapidAPI dashboard for exact limits
- The script includes rate limiting delays

### Database Performance
- Uses bulk inserts for efficiency
- Checks for duplicates before inserting
- Indexes on `external_id` and `source` recommended

### Recommended Fetching Strategy
1. **Initial Load**: Fetch 200-500 jobs across multiple searches
2. **Regular Updates**: Fetch 50-100 new jobs daily
3. **Targeted Searches**: Use specific keywords for better quality

## 🛠️ Troubleshooting

### Common Issues

1. **"RAPIDAPI_KEY not configured"**
   - Check your `.env` file
   - Ensure the key is valid in RapidAPI dashboard

2. **"No jobs returned"**
   - Try different keywords or locations
   - Check if your API subscription is active

3. **"Database connection failed"**
   - Verify PostgreSQL is running
   - Check DATABASE_MODE=postgres in environment

4. **Rate limiting errors**
   - Increase delay_between_requests parameter
   - Reduce max_jobs_per_search

### Debug Mode

Run with debug output:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from services.external_job_fetcher import fetchJobFromExternal
result = fetchJobFromExternal(max_jobs_per_search=5)
```

## 📝 Next Steps

1. **Set up your RapidAPI key**
2. **Run the test script**
3. **Try a small fetch via API**
4. **Set up automated fetching**
5. **Monitor job quality and adjust keywords**

For more advanced customization, you can modify the skill extraction logic in `parse_linkedin_job()` or add custom job filtering rules.