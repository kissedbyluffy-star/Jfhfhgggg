"""escrow precision and fee tx

Revision ID: 0002_escrow_precision_and_fee_tx
Revises: 0001_initial
Create Date: 2024-01-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_escrow_precision_and_fee_tx"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("escrows", sa.Column("fee_tx_hash", sa.String(length=128), nullable=True))
    op.create_unique_constraint("uq_chain_deposit_address", "escrows", ["chain", "deposit_address"])
    op.alter_column("escrows", "amount_expected", type_=sa.Numeric(18, 6))
    op.alter_column("escrows", "amount_received", type_=sa.Numeric(18, 6))
    op.alter_column("escrows", "fee_amount", type_=sa.Numeric(18, 6))
    op.alter_column("escrows", "net_amount", type_=sa.Numeric(18, 6))


def downgrade() -> None:
    op.alter_column("escrows", "net_amount", type_=sa.Float())
    op.alter_column("escrows", "fee_amount", type_=sa.Float())
    op.alter_column("escrows", "amount_received", type_=sa.Float())
    op.alter_column("escrows", "amount_expected", type_=sa.Float())
    op.drop_constraint("uq_chain_deposit_address", "escrows", type_="unique")
    op.drop_column("escrows", "fee_tx_hash")
