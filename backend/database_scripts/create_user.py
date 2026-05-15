"""
Create a new user in the QCanvas database.
Interactive script with validation and confirmation.
"""
import sys
import os

# Add backend directory to path
backend_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

from app.config.database import SessionLocal
from app.models.database_models import User, UserRole

def create_user():
    """Create a new user interactively."""
    print("=" * 60)
    print("QCanvas - Create New User")
    print("=" * 60)
    print()
    
    # Get user input
    email = input("Email: ").strip()
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    full_name = input("Full Name: ").strip()
    
    # Role selection
    print("\nSelect Role:")
    print("  1. User (default)")
    print("  2. Admin")
    print("  3. Researcher")
    role_choice = input("Choice [1]: ").strip() or "1"
    
    role_map = {
        "1": UserRole.USER,
        "2": UserRole.ADMIN,
        "3": UserRole.RESEARCHER
    }
    role = role_map.get(role_choice, UserRole.USER)
    
    # API key option
    generate_api = input("\nGenerate API key? (y/n) [n]: ").strip().lower() == 'y'
    
    # Validate input
    if not all([email, username, password, full_name]):
        print("\n❌ Error: All fields are required!")
        return 1
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Check if email or username already exists
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"\n❌ Error: Email '{email}' already exists!")
            return 1
        
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            print(f"\n❌ Error: Username '{username}' already exists!")
            return 1
        
        # Create user
        print("\n⏳ Creating user...")
        user = User(
            email=email,
            username=username,
            full_name=full_name,
            role=role
        )
        
        # Set password (hashed automatically)
        user.set_password(password)
        
        # Generate API key if requested
        api_key_plaintext = None
        if generate_api:
            api_key_plaintext = user.generate_and_set_api_key()
        
        # Save to database
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Success message
        print("\n" + "=" * 60)
        print("✅ User created successfully!")
        print("=" * 60)
        print(f"\nUser ID:       {user.id}")
        print(f"Email:         {user.email}")
        print(f"Username:      {user.username}")
        print(f"Full Name:     {user.full_name}")
        print(f"Role:          {user.role.value}")
        print(f"Active:        {user.is_active}")
        print(f"Verified:      {user.is_verified}")
        print(f"Created At:    {user.created_at}")
        
        if api_key_plaintext:
            print("\n" + "⚠" * 30)
            print("⚠  IMPORTANT: Save this API key now!  ⚠")
            print("⚠  It will NOT be shown again!        ⚠")
            print("⚠" * 30)
            print(f"\nAPI Key: {api_key_plaintext}")
            print()
        
        print("\n✅ You can now log in with:")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print()
        
        return 0
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error creating user: {str(e)}")
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    try:
        sys.exit(create_user())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
