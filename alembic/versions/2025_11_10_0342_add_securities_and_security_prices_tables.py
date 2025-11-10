"""add securities and security_prices tables

Revision ID: adc49e6a8603
Revises:
Create Date: 2025-11-10 03:42:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'adc49e6a8603'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create securities table
    op.create_table(
        'securities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('exchange', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('security_type', sa.String(length=50), nullable=True),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_syncing', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_securities_id', 'securities', ['id'])
    op.create_index('ix_securities_symbol', 'securities', ['symbol'], unique=True)

    # Create security_prices table
    op.create_table(
        'security_prices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('security_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=False),
        sa.Column('interval_type', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_security_prices_id', 'security_prices', ['id'])
    op.create_index('ix_security_prices_security_id', 'security_prices', ['security_id'])
    op.create_index('ix_security_prices_timestamp', 'security_prices', ['timestamp'])
    op.create_index('idx_security_time', 'security_prices', ['security_id', 'timestamp'])
    op.create_index('idx_security_interval_time', 'security_prices', ['security_id', 'interval_type', 'timestamp'])


def downgrade() -> None:
    # Drop security_prices table
    op.drop_index('idx_security_interval_time', 'security_prices')
    op.drop_index('idx_security_time', 'security_prices')
    op.drop_index('ix_security_prices_timestamp', 'security_prices')
    op.drop_index('ix_security_prices_security_id', 'security_prices')
    op.drop_index('ix_security_prices_id', 'security_prices')
    op.drop_table('security_prices')

    # Drop securities table
    op.drop_index('ix_securities_symbol', 'securities')
    op.drop_index('ix_securities_id', 'securities')
    op.drop_table('securities')
