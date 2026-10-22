import os
import sys

# Ensure src is on pythonpath
sys.path.insert(0, os.path.abspath("."))

def test_phase1_components():
    print("🧪 Running Phase 1 Foundation Verification Tests...")
    
    # 1. Config Test
    from src.core.config import settings
    print(f"  [1/6] Config loaded successfully. Project: {settings.PROJECT_NAME}, API Prefix: {settings.API_V1_STR}")
    assert settings.PROJECT_NAME == "Conceptly Studio"
    
    # 2. Security Test
    from src.core.security import get_password_hash, verify_password, create_access_token
    test_pwd = "testpassword123"
    hashed = get_password_hash(test_pwd)
    assert verify_password(test_pwd, hashed)
    assert not verify_password("wrongpassword", hashed)
    token = create_access_token("test-user-id")
    assert token is not None and len(token) > 20
    print("  [2/6] Security & JWT Token generation verified.")
    
    # 3. Database & Session Test
    from src.database.session import engine, Base, SessionLocal
    from src.models.entities import User, ReelJob, JobStage, ReelArtifact
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    print("  [3/6] SQLite Database schema & tables created.")
    
    # 4. Admin User Seeding Test
    existing_admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if not existing_admin:
        admin = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            role="admin"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        existing_admin = admin
    assert existing_admin.email == settings.ADMIN_EMAIL
    print(f"  [4/6] Admin user seed verified: {existing_admin.email} (ID: {existing_admin.id})")
    
    # 5. Storage Service Test
    from src.engines.storage.storage_service import get_storage_service
    storage = get_storage_service()
    dummy_file = "dummy_test.txt"
    with open(dummy_file, "w") as f:
        f.write("Conceptly Studio Phase 1 Test")
    uploaded_url = storage.upload_file(dummy_file, "tests/dummy_test.txt")
    assert uploaded_url.startswith("/media/")
    if os.path.exists(dummy_file):
        os.remove(dummy_file)
    print(f"  [5/6] Storage Service verified. Uploaded test asset URL: {uploaded_url}")
    
    # 6. ReelJob Entity & Gating Lifecycle Test
    test_job = ReelJob(
        user_id=existing_admin.id,
        generation_tier="DEFAULT",
        exam_type="SCHOOL",
        class_level=9,
        subject="Physics",
        topic_title="Newton's Third Law",
        status="PENDING"
    )
    db.add(test_job)
    db.commit()
    db.refresh(test_job)
    
    # Add stages
    stage1 = JobStage(job_id=test_job.id, stage_name="CONCEPT_EXTRACTION", status="COMPLETED", progress_percent=100)
    db.add(stage1)
    db.commit()
    db.refresh(test_job)
    
    assert len(test_job.stages) >= 1
    assert test_job.stages[0].stage_name == "CONCEPT_EXTRACTION"
    print(f"  [6/6] ReelJob lifecycle & Stage tracking verified. Job ID: {test_job.id}")
    
    db.close()
    print("\n🎉 Phase 1 Platform Foundation & Infrastructure Tests PASSED 100%!")

if __name__ == "__main__":
    test_phase1_components()
