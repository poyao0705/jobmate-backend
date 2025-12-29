"""Check PostgreSQL job_listings table schema."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

uri = os.getenv("DATABASE_PROD")
engine = create_engine(uri)

with engine.connect() as conn:
    # Get column info for job_listings
    result = conn.execute(text("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'job_listings'
        ORDER BY ordinal_position
    """))
    
    print("PostgreSQL job_listings columns:")
    print("=" * 80)
    for row in result:
        print(f"{row.column_name:30} {row.data_type:20} {str(row.character_maximum_length or ''):10} {'NULL' if row.is_nullable == 'YES' else 'NOT NULL'}")
