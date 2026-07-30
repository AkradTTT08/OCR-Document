import hashlib
import time
from auth_db import engine, Base, SessionLocal
from auth_models import User

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    print("Waiting for database connection...")
    retries = 5
    while retries > 0:
        try:
            # Drop old tables to apply schema change for UUID
            Base.metadata.drop_all(bind=engine)
            
            # Create all tables defined in Base
            Base.metadata.create_all(bind=engine)
            
            db = SessionLocal()
            
            # Create default admin user
            admin_email = "o.akrad.ttt08@gmail.com"
            admin_user = db.query(User).filter(User.username == admin_email).first()
            if not admin_user:
                print("Creating default admin user...")
                new_admin = User(
                    username=admin_email,
                    password_hash=hash_password("123123Zx!"),
                    role="admin"
                )
                db.add(new_admin)
                db.commit()
                print("✅ Admin created successfully.")
                
            db.close()
            print("✅ Auth DB initialized with SQLAlchemy ORM!")
            break
        except Exception as e:
            print(f"Database not ready yet... {e}")
            retries -= 1
            time.sleep(2)

if __name__ == "__main__":
    init_db()
