
import os
import sys

# Add backend directory to path so imports work
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)

from app.config.database import engine, Base
# Import ALL models to ensure they are registered with Base.metadata
from app.models import database_models 
from app.models import gamification
from alembic.config import Config
from alembic import command

def reset_database():
    try:
        print("⚠️  WARNING: This will DROP ALL TABLES and recreate them from scratch!")
        print("   All data (users, projects, files, shared snippets, gamification, etc.) will be lost.\n")
        
        confirm = input("Are you sure? Type 'yes' to confirm: ").strip().lower()
        if confirm != 'yes':
            print("Aborted.")
            return
        
        # Drop all tables
        print("\n🗑️  Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("   ✅ All tables dropped.")
        
        # Create all tables from current models
        print("🔨 Creating all tables from current models...")
        Base.metadata.create_all(bind=engine)
        
        # List created tables
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(engine)
        tables = sorted(inspector.get_table_names())
        print(f"   ✅ Created {len(tables)} tables:")
        for t in tables:
            cols = [c['name'] for c in inspector.get_columns(t)]
            print(f"      - {t} ({len(cols)} columns)")
        
        # Stamp alembic head
        print("\n📌 Stamping alembic to latest head...")
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        command.stamp(alembic_cfg, "head")
        print("   ✅ Alembic stamped to head.")
        
        # Recreate demo account
        try:
            import create_demo_account
            print("\n👤 Recreating demo account...")
            create_demo_account.main()
            print("   ✅ Demo account created.")
        except Exception as e:
            print(f"   ⚠️  Could not create demo account: {e}")
        
        print("\n🎉 Database reset complete!")
        
    except Exception as e:
        print(f"\n❌ Error resetting database: {e}")
        import traceback
        traceback.print_exc()
        print("\nPlease ensure the database server is running.")


if __name__ == "__main__":
    reset_database()
