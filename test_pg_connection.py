"""Test PostgreSQL connection"""
from jobmate_agent.extensions_fastapi import engine, SQLALCHEMY_DATABASE_URI
from sqlmodel import Session, text

print("Database URI:", SQLALCHEMY_DATABASE_URI)
print("Engine:", engine)

if 'postgresql' in str(engine.url):
    print("✅ PostgreSQL connection configured!")
    
    # Test actual connection
    try:
        with Session(engine) as session:
            result = session.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Successfully connected to PostgreSQL!")
            print(f"   Version: {version[:80]}...")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
else:
    print("❌ Still using SQLite - check environment variables")
