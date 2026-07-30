from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
import uuid
from auth_db import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(64), nullable=False)
    role = Column(String(20), default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
