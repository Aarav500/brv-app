# models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Enum, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
import enum

class RoleEnum(str, enum.Enum):
    ceo = "ceo"
    admin = "admin"
    hr = "hr"
    receptionist = "receptionist"
    interviewer = "interviewer"
    candidate = "candidate"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.candidate)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    force_password_reset = Column(Boolean, default=False)

    # relationships
    candidates = relationship("Candidate", back_populates="created_by_user")

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(100), nullable=True)
    form_data = Column(JSON, nullable=True)
    resume_url = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by_user = relationship("User", back_populates="candidates")

class Interview(Base):
    __tablename__ = "interviews"
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    interviewer = Column(Integer, ForeignKey("users.id"), nullable=True)
    result = Column(String(50), nullable=True)  # pass/fail/on_hold
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
