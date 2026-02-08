"""SQLAlchemy ORM 模型定义。"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    ForeignKey, LargeBinary, Enum as SAEnum,
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ── 枚举定义 ──────────────────────────────────────────────

class TicketStatus(str, enum.Enum):
    """工单状态。"""
    CHATTING = "chatting"                # AI 对话中
    PENDING = "pending"                  # 待人工接入
    HANDLING = "handling"                # 坐席处理中
    RESOLVED = "resolved"               # AI 已解决
    CLOSED = "closed"                    # 坐席完结
    REVIEWED = "reviewed"               # 已质检


class MessageRole(str, enum.Enum):
    """消息角色。"""
    USER = "user"
    AI = "ai"
    AGENT = "agent"


class DocStatus(str, enum.Enum):
    """知识文档状态。"""
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# ── ORM 模型 ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    tickets = relationship("Ticket", back_populates="user", foreign_keys="Ticket.user_id")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, default="新对话")
    status = Column(String(20), nullable=False, default=TicketStatus.CHATTING.value)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    category = Column(String(50), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # 关系
    user = relationship("User", back_populates="tickets", foreign_keys=[user_id])
    agent = relationship("User", foreign_keys=[agent_id])
    messages = relationship("Message", back_populates="ticket", order_by="Message.created_at")
    qc_result = relationship("QCResult", back_populates="ticket", uselist=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    role = Column(String(10), nullable=False)  # user / ai / agent
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    ticket = relationship("Ticket", back_populates="messages")


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=DocStatus.PROCESSING.value)
    chunk_count = Column(Integer, default=0)
    qa_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    chunks = relationship("VectorChunk", back_populates="doc", cascade="all, delete-orphan")
    qa_pairs = relationship("QAPair", back_populates="doc", cascade="all, delete-orphan")


class VectorChunk(Base):
    __tablename__ = "vector_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("knowledge_docs.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=True)  # numpy array 序列化存储
    chunk_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    doc = relationship("KnowledgeDoc", back_populates="chunks")


class QAPair(Base):
    __tablename__ = "qa_pairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("knowledge_docs.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=True)  # question 的向量
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    doc = relationship("KnowledgeDoc", back_populates="qa_pairs")


class QCResult(Base):
    __tablename__ = "qc_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True, nullable=False)
    accuracy_score = Column(Integer, nullable=False)      # 知识准确性 1-5
    compliance_score = Column(Integer, nullable=False)     # 服务态度/规范 1-5
    resolution_score = Column(Integer, nullable=False)     # 问题解决度 1-5
    total_score = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    ticket = relationship("Ticket", back_populates="qc_result")
