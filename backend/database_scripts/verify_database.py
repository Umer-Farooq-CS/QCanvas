"""
Verify users table exists in the database.
"""
import sys
import os

# Add backend directory to path
backend_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

from sqlalchemy import inspect, text
from app.config.database import engine
from app.config.settings import settings

def verify_database():
    """Check if all tables exist and show their structure."""
    print("=" * 60)
    print("QCanvas Database Verification")
    print("=" * 60)
    print(f"\nConnecting to: {settings.DATABASE_URL}")
    print()
    
    try:
        # Get database inspector
        inspector = inspect(engine)
        
        # Check if tables exist
        tables = inspector.get_table_names()
        print(f"✅ Found {len(tables)} table(s) in database:")
        for table in tables:
            print(f"   - {table}")
        
        expected_tables = ['users', 'projects', 'files', 'jobs']
        missing_tables = [t for t in expected_tables if t not in tables]
        
        if not missing_tables:
            print("\n✅ All expected tables EXIST!")
            
            for table_name in expected_tables:
                # Get column information
                print(f"\n📋 {table_name.capitalize()} table structure:")
                print("-" * 60)
                columns = inspector.get_columns(table_name)
                for col in columns:
                    null_str = "NULL" if col['nullable'] else "NOT NULL"
                    print(f"  {col['name']:<20} {str(col['type']):<20} {null_str}")
                
                # Get indexes
                indexes = inspector.get_indexes(table_name)
                if indexes:
                    print(f"\n🔍 Indexes for {table_name}:")
                    print("-" * 60)
                    for idx in indexes:
                        unique_str = "UNIQUE" if idx['unique'] else ""
                        cols = ", ".join(idx['column_names'])
                        print(f"  {idx['name']:<30} ({cols}) {unique_str}")
                
                # Count rows
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.scalar()
                    print(f"\n📊 Total rows in {table_name}: {count}")
            
            print("\n" + "=" * 60)
            print("✅ Database verification PASSED!")
            print("=" * 60)
            
        else:
            print(f"\n❌ Missing tables: {', '.join(missing_tables)}")
            print("   Run: python -m alembic upgrade head")
            
    except Exception as e:
        print(f"\n❌ Error connecting to database:")
        print(f"   {str(e)}")
        print("\n   Make sure:")
        print("   1. Docker Postgres is running (docker-compose ps)")
        print("   2. Database credentials are correct")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(verify_database())
