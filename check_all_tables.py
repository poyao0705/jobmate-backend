"""
Compare all PostgreSQL tables with FastAPI models to find schema mismatches.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv()

uri = os.getenv("DATABASE_PROD")
engine = create_engine(uri)

# Tables to check
tables_to_check = [
    'user_profiles', 
    'resumes', 
    'job_listings',
    'tasks',
    'goals',
    'skill_gap_reports',
    'skills',
    'chats',
    'messages'
]

print("=" * 80)
print("PostgreSQL Schema Report")
print("=" * 80)

with engine.connect() as conn:
    for table_name in tables_to_check:
        # Check if table exists
        result = conn.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = '{table_name}'
            )
        """))
        exists = result.scalar()
        
        if not exists:
            print(f"\n❌ Table '{table_name}' DOES NOT EXIST")
            continue
            
        print(f"\n✓ Table: {table_name}")
        print("-" * 80)
        
        # Get columns
        result = conn.execute(text(f"""
            SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        
        for row in result:
            nullable = "NULL" if row.is_nullable == "YES" else "NOT NULL"
            max_len = f"({row.character_maximum_length})" if row.character_maximum_length else ""
            default = f" DEFAULT {row.column_default}" if row.column_default else ""
            print(f"  {row.column_name:30} {row.data_type}{max_len:15} {nullable:10}{default}")

print("\n" + "=" * 80)
