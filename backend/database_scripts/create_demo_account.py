"""
Create demo account for QCanvas.
This script creates the special demo user account with proper role and password.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config.database import SessionLocal
from app.models.database_models import User, UserRole

def main():
    """Create the demo account."""
    db = SessionLocal()
    try:
        # Check if demo account already exists
        existing = db.query(User).filter(User.email == "demo@qcanvas.dev").first()
        if existing:
            print("✅ Demo account already exists!")
            print(f"   Email: {existing.email}")
            print(f"   Username: {existing.username}")
            print(f"   Role: {existing.role.value}")
            return 0
            
        # Create demo user
        demo = User(
            email="demo@qcanvas.dev",
            username="demo",
            full_name="Demo User",
            role=UserRole.DEMO,
            is_verified=True
        )
        demo.set_password("demo123")
        
        db.add(demo)
        db.commit()
        db.refresh(demo)
        
        print("✅ Demo account created successfully!")
        print(f"   Email: {demo.email}")
        print(f"   Username: {demo.username}")
        print(f"   Password: demo123")
        print(f"   Role: {demo.role.value}")
        print("\n⚠️  Remember: Demo account data will be cleared on logout!")
        return 0
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating demo account: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    sys.exit(main())
