"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


chain_enum = sa.Enum("TRC20", "BEP20", name="chain")

token_enum = sa.Enum("USDT", name="token")

status_enum = sa.Enum(
    "CREATED",
    "AWAITING_DEPOSIT",
    "DEPOSIT_SEEN",
    "FUNDS_LOCKED",
    "RELEASE_REQUESTED",
    "RELEASE_APPROVED",
    "PAYOUT_QUEUED",
    "PAYOUT_SENT",
    "COMPLETED",
    "DISPUTED",
    "REVIEW",
    "CANCELLED",
    "EXPIRED",
    "UNDERPAID",
    "OVERPAID_REVIEW",
    "PAYOUT_FAILED",
    name="escrowstatus",
)

message_role_enum = sa.Enum("buyer", "seller", "system", name="messagerole")
message_type_enum = sa.Enum("text", "image", name="messagetype")
dispute_status_enum = sa.Enum("OPEN", "RESOLVED", name="disputestatus")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("tg_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime()),
        sa.Column("terms_accepted_at", sa.DateTime()),
        sa.Column("broadcast_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_reasons_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("public_hash", sa.String(length=16), nullable=False),
        sa.UniqueConstraint("public_hash", name="uq_users_public_hash"),
    )

    op.create_table(
        "escrows",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("room_code", sa.String(length=12), nullable=False),
        sa.Column("buyer_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("seller_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("chain", chain_enum, nullable=False),
        sa.Column("token", token_enum, nullable=False),
        sa.Column("amount_expected", sa.Float(), nullable=False),
        sa.Column("amount_received", sa.Float()),
        sa.Column("fee_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("fee_amount", sa.Float(), nullable=False),
        sa.Column("net_amount", sa.Float(), nullable=False),
        sa.Column("deposit_address", sa.String(length=128), nullable=False),
        sa.Column("deposit_tx_hash", sa.String(length=128)),
        sa.Column("deposit_confirmations", sa.Integer()),
        sa.Column("payout_address", sa.String(length=128)),
        sa.Column("payout_tx_hash", sa.String(length=128)),
        sa.Column("payout_confirmations", sa.Integer()),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("chat_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("room_code", name="uq_escrows_room_code"),
        sa.UniqueConstraint("chain", "deposit_tx_hash", name="uq_chain_deposit_tx"),
    )
    op.create_index("ix_escrows_buyer_tg_id", "escrows", ["buyer_tg_id"])
    op.create_index("ix_escrows_seller_tg_id", "escrows", ["seller_tg_id"])
    op.create_index("ix_escrows_room_code", "escrows", ["room_code"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escrow_id", sa.UUID(), sa.ForeignKey("escrows.id"), nullable=False),
        sa.Column("sender_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("role", message_role_enum, nullable=False),
        sa.Column("type", message_type_enum, nullable=False),
        sa.Column("body_or_file_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "disputes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escrow_id", sa.UUID(), sa.ForeignKey("escrows.id"), nullable=False),
        sa.Column("opened_by_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", dispute_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escrow_id", sa.UUID(), sa.ForeignKey("escrows.id"), nullable=False),
        sa.Column("reviewer_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("counterparty_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("posted_channel_msg_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "revenue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escrow_id", sa.UUID(), sa.ForeignKey("escrows.id"), nullable=False),
        sa.Column("chain", chain_enum, nullable=False),
        sa.Column("fee_amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escrow_id", sa.UUID(), nullable=True),
        sa.Column("actor_tg_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("json", sa.JSON(), nullable=False),
    )

    op.create_table(
        "config_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("changed_by", sa.BigInteger(), nullable=True),
        sa.Column("old_json", sa.JSON(), nullable=False),
        sa.Column("new_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("config_history")
    op.drop_table("config")
    op.drop_table("audit_log")
    op.drop_table("revenue")
    op.drop_table("reviews")
    op.drop_table("disputes")
    op.drop_table("messages")
    op.drop_index("ix_escrows_room_code", table_name="escrows")
    op.drop_index("ix_escrows_seller_tg_id", table_name="escrows")
    op.drop_index("ix_escrows_buyer_tg_id", table_name="escrows")
    op.drop_table("escrows")
    op.drop_table("users")
    status_enum.drop(op.get_bind())
    message_role_enum.drop(op.get_bind())
    message_type_enum.drop(op.get_bind())
    dispute_status_enum.drop(op.get_bind())
    chain_enum.drop(op.get_bind())
    token_enum.drop(op.get_bind())
