"""add currency and currency rate models

Revision ID: f81d6c130a3b
Revises: 5d03850a6e53
Create Date: 2025-11-10 08:47:54.123456+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision = 'f81d6c130a3b'
down_revision = '5d03850a6e53'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create currencies table
    op.create_table(
        'currencies',
        sa.Column('id', sa.Uuid(), nullable=False, default=uuid.uuid4),
        sa.Column('code', sa.String(length=3), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_currencies_id'), 'currencies', ['id'], unique=False)
    op.create_index(op.f('ix_currencies_code'), 'currencies', ['code'], unique=True)

    # Create currency_rates table
    op.create_table(
        'currency_rates',
        sa.Column('id', sa.Uuid(), nullable=False, default=uuid.uuid4),
        sa.Column('from_currency_id', sa.Uuid(), nullable=False),
        sa.Column('to_currency_id', sa.Uuid(), nullable=False),
        sa.Column('rate', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['from_currency_id'], ['currencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_currency_id'], ['currencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_currency_id', 'to_currency_id', 'date', name='uq_currency_rate_from_to_date')
    )
    op.create_index(op.f('ix_currency_rates_id'), 'currency_rates', ['id'], unique=False)
    op.create_index(op.f('ix_currency_rates_from_currency_id'), 'currency_rates', ['from_currency_id'], unique=False)
    op.create_index(op.f('ix_currency_rates_to_currency_id'), 'currency_rates', ['to_currency_id'], unique=False)
    op.create_index(op.f('ix_currency_rates_date'), 'currency_rates', ['date'], unique=False)
    op.create_index('ix_currency_rates_from_to_date', 'currency_rates', ['from_currency_id', 'to_currency_id', 'date'], unique=False)

    # Add currency_id column to accounts table
    op.add_column('accounts', sa.Column('currency_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_accounts_currency_id', 'accounts', 'currencies', ['currency_id'], ['id'], ondelete='SET NULL')

    # Insert seed currencies
    op.execute("""
        INSERT INTO currencies (id, code, name, symbol, is_active, created_at, updated_at) VALUES
        (gen_random_uuid(), 'USD', 'US Dollar', '$', true, now(), now()),
        (gen_random_uuid(), 'EUR', 'Euro', '€', true, now(), now()),
        (gen_random_uuid(), 'GBP', 'British Pound', '£', true, now(), now()),
        (gen_random_uuid(), 'CAD', 'Canadian Dollar', 'C$', true, now(), now()),
        (gen_random_uuid(), 'JPY', 'Japanese Yen', '¥', true, now(), now()),
        (gen_random_uuid(), 'AUD', 'Australian Dollar', 'A$', true, now(), now()),
        (gen_random_uuid(), 'CHF', 'Swiss Franc', 'CHF', true, now(), now()),
        (gen_random_uuid(), 'CNY', 'Chinese Yuan', '¥', true, now(), now())
    """)


def downgrade() -> None:
    # Remove foreign key and column from accounts
    op.drop_constraint('fk_accounts_currency_id', 'accounts', type_='foreignkey')
    op.drop_column('accounts', 'currency_id')

    # Drop currency_rates table
    op.drop_index('ix_currency_rates_from_to_date', table_name='currency_rates')
    op.drop_index(op.f('ix_currency_rates_date'), table_name='currency_rates')
    op.drop_index(op.f('ix_currency_rates_to_currency_id'), table_name='currency_rates')
    op.drop_index(op.f('ix_currency_rates_from_currency_id'), table_name='currency_rates')
    op.drop_index(op.f('ix_currency_rates_id'), table_name='currency_rates')
    op.drop_table('currency_rates')

    # Drop currencies table
    op.drop_index(op.f('ix_currencies_code'), table_name='currencies')
    op.drop_index(op.f('ix_currencies_id'), table_name='currencies')
    op.drop_table('currencies')
