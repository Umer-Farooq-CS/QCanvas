import sys
import os
import uuid
import traceback

# Setup directory references relative to this file
_self_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

# Add the backend directory to sys.path to allow imports from app
if _self_dir not in sys.path:
    sys.path.append(_self_dir)

# Setup logging to file
log_file = os.path.join(_self_dir, "test_db_output.txt")

def log(message):
    with open(log_file, "a") as f:
        f.write(message + "\n")
    print(message)

# Clear log file
with open(log_file, "w") as f:
    f.write("--- Starting Database Interaction Test ---\n")

try:
    from app.config.database import SessionLocal
    from app.models.database_models import User, Project, File, Job, UserRole, JobStatus
except Exception as e:
    log(f"[CRITICAL ERROR] Import failed: {e}")
    log(traceback.format_exc())
    sys.exit(1)

def test_database_interaction():
    db = SessionLocal()
    try:
        # 1. Create a Test User
        test_email = f"test_user_{uuid.uuid4()}@example.com"
        user = User(
            email=test_email,
            username=f"test_user_{uuid.uuid4()}",
            full_name="Test User",
            role=UserRole.USER
        )
        user.set_password("securepassword")
        db.add(user)
        db.commit()
        db.refresh(user)
        log(f"[SUCCESS] Created User: {user.email} (ID: {user.id})")

        # 2. Create a Project
        project = Project(
            user_id=user.id,
            name="Test Project",
            description="A project for testing database relationships",
            is_public=False
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        log(f"[SUCCESS] Created Project: {project.name} (ID: {project.id})")

        # 3. Add a File to the Project
        file = File(
            project_id=project.id,
            filename="main.py",
            content="print('Hello, Quantum World!')",
            is_main=True
        )
        db.add(file)
        db.commit()
        db.refresh(file)
        log(f"[SUCCESS] Created File: {file.filename} (ID: {file.id})")

        # 4. Create a Job
        job = Job(
            user_id=user.id,
            project_id=project.id,
            status=JobStatus.PENDING,
            backend="qasm_simulator",
            shots=1024
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        log(f"[SUCCESS] Created Job: {job.id} (Status: {job.status.value})")

        # 5. Verify Relationships
        log("\n--- Verifying Relationships ---")
        
        # Refresh user to load relationships
        db.refresh(user)
        
        # Check User -> Projects
        if len(user.projects) > 0 and user.projects[0].id == project.id:
            log(f"[PASS] User.projects relationship works. Found {len(user.projects)} project(s).")
        else:
            log(f"[FAIL] User.projects relationship failed.")

        # Check User -> Jobs
        if len(user.jobs) > 0 and user.jobs[0].id == job.id:
            log(f"[PASS] User.jobs relationship works. Found {len(user.jobs)} job(s).")
        else:
            log(f"[FAIL] User.jobs relationship failed.")

        # Check Project -> Files
        # Refresh project to load relationships
        db.refresh(project)
        if len(project.files) > 0 and project.files[0].id == file.id:
            log(f"[PASS] Project.files relationship works. Found {len(project.files)} file(s).")
        else:
            log(f"[FAIL] Project.files relationship failed.")

        # 6. Clean Up (Cascade Delete)
        log("\n--- Testing Cascade Delete ---")
        db.delete(user)
        db.commit()
        
        # Verify deletion
        deleted_user = db.query(User).filter(User.id == user.id).first()
        deleted_project = db.query(Project).filter(Project.id == project.id).first()
        deleted_file = db.query(File).filter(File.id == file.id).first()
        deleted_job = db.query(Job).filter(Job.id == job.id).first()

        if not deleted_user:
            log("[PASS] User deleted.")
        else:
            log("[FAIL] User not deleted.")

        if not deleted_project:
            log("[PASS] Project cascade deleted.")
        else:
            log("[FAIL] Project not deleted.")
            
        if not deleted_file:
            log("[PASS] File cascade deleted.")
        else:
            log("[FAIL] File not deleted.")

        if not deleted_job:
            log("[PASS] Job cascade deleted.")
        else:
            log("[FAIL] Job not deleted.")

    except Exception as e:
        log(f"[ERROR] An error occurred: {e}")
        log(traceback.format_exc())
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_database_interaction()
