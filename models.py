# models.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text, Enum, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base
import enum


# ──────────────────────────────────────────────
# 1. TENANTS — The Business
# ──────────────────────────────────────────────
class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    vertical = Column(String(50))  # clinic, real_estate, restaurant
    status = Column(String(20), default="draft")  # draft, published, suspended
    api_key = Column(String(64), unique=True, index=True)
    phone_number = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    knowledge_sources = relationship("KnowledgeSource", back_populates="tenant", cascade="all, delete-orphan")
    configs = relationship("Configs", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="tenant", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="tenant", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# 2. KNOWLEDGE SOURCES — What They Uploaded
# ──────────────────────────────────────────────
class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    type = Column(String(20))  # doc, url, faq
    name = Column(String(255))
    status = Column(String(20), default="pending")  # pending, processing, completed, failed, deleted
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="knowledge_sources")
    documents = relationship("Document", back_populates="source", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# 3. DOCUMENTS — The Chunks Inside Sources
# ──────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("knowledge_sources.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    meta = Column(JSON, default={})
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    source = relationship("KnowledgeSource", back_populates="documents")
    tenant = relationship("Tenant")


# ──────────────────────────────────────────────
# 4. CONFIGS — AI Behavior Settings
# ──────────────────────────────────────────────
class Configs(Base):
    __tablename__ = "configs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True)
    hours = Column(JSON, default={})
    services = Column(JSON, default=[])
    booking_rules = Column(JSON, default={})
    persona = Column(Text, nullable=True)
    voice = Column(String(50), nullable=True)
    escalation_contact = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="configs")


# ──────────────────────────────────────────────
# 5. CONVERSATIONS — Each Call/Chat Session
# ──────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    channel = Column(String(20))  # voice, chat
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    transcript = Column(Text, nullable=True)
    recording_url = Column(String(500), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="conversation", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="conversation", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# 6. MESSAGES — Each Message Inside a Conversation
# ──────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # ← Added
    conversation_id = Column(Integer, ForeignKey("conversations.id"))  # ← MUST BE Integer, NOT String
   
    role = Column(String(20))
    content = Column(Text)
    tool_calls = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    conversation = relationship("Conversation", back_populates="messages")  # ← Check this

# ──────────────────────────────────────────────
# 7. BOOKINGS — Appointments Made
# ──────────────────────────────────────────────
class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    contact_name = Column(String(255))
    contact_phone = Column(String(20))
    service = Column(String(255))
    date = Column(String(20))  # ← ADD THIS
    time = Column(String(20))  # ← ADD THIS
    datetime = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())  # ← FIXED
    # Relationships
    tenant = relationship("Tenant", back_populates="bookings")
    conversation = relationship("Conversation", back_populates="bookings")


# ──────────────────────────────────────────────
# 8. LEADS — Captured Customer Info
# ──────────────────────────────────────────────
class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    name = Column(String(255))
    phone = Column(String(20))
    email = Column(String(255), nullable=True)
    intent = Column(Text)
    status = Column(String(20), default="new")
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="leads")
    conversation = relationship("Conversation", back_populates="leads")