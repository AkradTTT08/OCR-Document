from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Connect to the Auth Database running on port 8124
DATABASE_URL = "postgresql://auth_admin:auth_password@127.0.0.1:8124/auth_db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
