# PostgreSQL to SQLite Sync Script

**Status: ✅ IMPLEMENTED** - This script syncs data from your production PostgreSQL database to your local SQLite database.

## Current Implementation Status

- **Vector Database**: ChromaDB with O*NET skills (32,681 skills) - fully populated
- **Gap Analyzer**: Level-aware skill gap analysis with O*NET integration
- **Career Engine**: Complete implementation with skill extraction, mapping, and reporting
- **Database Sync**: PostgreSQL ↔ SQLite synchronization for development workflow

## Features

- **Incremental syncing**: Only syncs new/updated records since last sync
- **Duplicate detection**: Uses INSERT OR REPLACE to handle duplicates
- **Selective syncing**: Configure which tables to sync and which to skip
- **Privacy protection**: Skips user-sensitive data by default
- **Job-focused**: Optimized for syncing job listings from external API

## Quick Usage

### Sync only job listings (recommended):
```bash
python sync_postgres_to_sqlite.py --jobs-only
```

### Sync all allowed tables:
```bash
python sync_postgres_to_sqlite.py
```

### Sync specific tables:
```bash
python sync_postgres_to_sqlite.py --tables job_listings skills
```

### Check sync status:
```bash
python sync_postgres_to_sqlite.py --status
```

## Configuration

The script automatically:
- Connects to PostgreSQL using your RDS credentials from `.env`
- Connects to SQLite using your `DATABASE_DEV` path
- Skips sensitive tables (users, user_profiles, etc.) for privacy
- Only syncs job_listings incrementally (new jobs since last sync)

## Tables Synced

| Table | Strategy | Notes |
|-------|----------|-------|
| job_listings | Incremental | Main focus - only new/updated jobs |
| skills | Full | O*NET skills reference data (32,681 skills) |
| skill_aliases | Full | O*NET skill aliases reference data |
| process_runs | Incremental | AI processing history |
| skill_gap_reports | Incremental | Career engine analysis results |
| learning_items | Incremental | Learning recommendations |
| report_learning_items | Incremental | Report-learning associations |
| users | Skip | Privacy protection |
| user_profiles | Skip | Privacy protection |
| chats | Skip | Privacy protection |

## Workflow Integration

**Typical workflow:**
1. Run external job fetcher to add jobs to PostgreSQL:
   ```bash
   $env:DATABASE_MODE="postgres"; python services/external_job_fetcher.py
   ```

2. Sync new jobs to local SQLite:
   ```bash
   python sync_postgres_to_sqlite.py --jobs-only
   ```

3. Use local SQLite for development/testing

**Career Engine Integration:**
- O*NET skills database is already populated in both PostgreSQL and SQLite
- Vector database (ChromaDB) contains O*NET skill embeddings
- Gap analysis can be run on either database with consistent results
- Skill gap reports are synced between databases for development workflow

## Error Handling

- Creates SQLite tables automatically if they don't exist
- Handles data type conversions (PostgreSQL → SQLite)
- Converts JSON fields to strings for SQLite compatibility
- Tracks sync timestamps to avoid re-syncing same data
- Gracefully handles connection failures

## Dependencies

Make sure you have these packages installed:
```bash
pip install psycopg2-binary python-dotenv
```