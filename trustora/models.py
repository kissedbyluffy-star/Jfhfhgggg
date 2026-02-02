from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from trustora.enums import Chain, DisputeStatus, EscrowStatus, MessageRole, MessageType, Token


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    broadcast_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_reasons_json: Mapped[dict] = mapped_column(JSON, default=dict)
    public_hash: Mapped[str] = mapped_column(String(16), unique=True)


class Escrow(Base):
    __tablename__ = "escrows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    buyer_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    seller_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chain: Mapped[Chain] = mapped_column(Enum(Chain))
    token: Mapped[Token] = mapped_column(Enum(Token))
    amount_expected: Mapped[float] = mapped_column(Float)
    amount_received: Mapped[float | None] = mapped_column(Float)
    fee_snapshot_json: Mapped[dict] = mapped_column(JSON)
    fee_amount: Mapped[float] = mapped_column(Float)
    net_amount: Mapped[float] = mapped_column(Float)
    deposit_address: Mapped[str] = mapped_column(String(128))
    deposit_tx_hash: Mapped[str | None] = mapped_column(String(128))
    deposit_confirmations: Mapped[int | None] = mapped_column(Integer)
    payout_address: Mapped[str | None] = mapped_column(String(128))
    payout_tx_hash: Mapped[str | None] = mapped_column(String(128))
    payout_confirmations: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[EscrowStatus] = mapped_column(Enum(EscrowStatus))
    chat_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("chain", "deposit_tx_hash", name="uq_chain_deposit_tx"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escrow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("escrows.id"))
    sender_tg_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole))
    type: Mapped[MessageType] = mapped_column(Enum(MessageType))
    body_or_file_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escrow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("escrows.id"))
    opened_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escrow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("escrows.id"))
    reviewer_tg_id: Mapped[int] = mapped_column(BigInteger)
    counterparty_tg_id: Mapped[int] = mapped_column(BigInteger)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text)
    posted_channel_msg_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Revenue(Base):
    __tablename__ = "revenue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escrow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("escrows.id"))
    chain: Mapped[Chain] = mapped_column(Enum(Chain))
    fee_amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escrow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Config(Base):
    __tablename__ = "config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    json: Mapped[dict] = mapped_column(JSON)


class ConfigHistory(Base):
    __tablename__ = "config_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    changed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    old_json: Mapped[dict] = mapped_column(JSON)
    new_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
