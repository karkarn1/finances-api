"""add financial institutions accounts and holdings

Revision ID: 5d03850a6e53
Revises:
Create Date: 2025-11-10 07:21:09.253448+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision = '5d03850a6e53'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reset_token', sa.String(length=255), nullable=True),
        sa.Column('reset_token_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_reset_token'), 'users', ['reset_token'], unique=False)

    # Create securities table
    op.create_table(
        'securities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
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
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_securities_id'), 'securities', ['id'], unique=False)
    op.create_index(op.f('ix_securities_symbol'), 'securities', ['symbol'], unique=True)

    # Create security_prices table
    op.create_table(
        'security_prices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('security_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('high', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('low', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('close', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('interval', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('security_id', 'timestamp', 'interval', name='uq_security_timestamp_interval')
    )
    op.create_index(op.f('ix_security_prices_id'), 'security_prices', ['id'], unique=False)
    op.create_index(op.f('ix_security_prices_security_id'), 'security_prices', ['security_id'], unique=False)
    op.create_index(op.f('ix_security_prices_timestamp'), 'security_prices', ['timestamp'], unique=False)

    # Create financial_institutions table
    op.create_table(
        'financial_institutions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_financial_institutions_id'), 'financial_institutions', ['id'], unique=False)
    op.create_index(op.f('ix_financial_institutions_user_id'), 'financial_institutions', ['user_id'], unique=False)
    op.create_index(op.f('ix_financial_institutions_name'), 'financial_institutions', ['name'], unique=False)

    # Create account_type enum
    op.execute("""
        CREATE TYPE accounttype AS ENUM (
            'checking', 'savings', 'tfsa', 'rrsp', 'fhsa', 'margin',
            'credit_card', 'line_of_credit', 'payment_plan', 'mortgage'
        )
    """)

    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('financial_institution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('account_type', postgresql.ENUM(
            'checking', 'savings', 'tfsa', 'rrsp', 'fhsa', 'margin',
            'credit_card', 'line_of_credit', 'payment_plan', 'mortgage',
            name='accounttype'
        ), nullable=False),
        sa.Column('is_investment_account', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('interest_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['financial_institution_id'], ['financial_institutions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accounts_id'), 'accounts', ['id'], unique=False)
    op.create_index(op.f('ix_accounts_user_id'), 'accounts', ['user_id'], unique=False)

    # Create account_values table
    op.create_table(
        'account_values',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('balance', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('cash_balance', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'timestamp', name='uq_account_timestamp')
    )
    op.create_index(op.f('ix_account_values_id'), 'account_values', ['id'], unique=False)
    op.create_index(op.f('ix_account_values_account_id'), 'account_values', ['account_id'], unique=False)
    op.create_index(op.f('ix_account_values_timestamp'), 'account_values', ['timestamp'], unique=False)

    # Create holdings table
    op.create_table(
        'holdings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('security_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('shares', sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column('average_price_per_share', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'security_id', 'timestamp', name='uq_account_security_timestamp')
    )
    op.create_index(op.f('ix_holdings_id'), 'holdings', ['id'], unique=False)
    op.create_index(op.f('ix_holdings_account_id'), 'holdings', ['account_id'], unique=False)
    op.create_index(op.f('ix_holdings_security_id'), 'holdings', ['security_id'], unique=False)
    op.create_index(op.f('ix_holdings_timestamp'), 'holdings', ['timestamp'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_holdings_timestamp'), table_name='holdings')
    op.drop_index(op.f('ix_holdings_security_id'), table_name='holdings')
    op.drop_index(op.f('ix_holdings_account_id'), table_name='holdings')
    op.drop_index(op.f('ix_holdings_id'), table_name='holdings')
    op.drop_table('holdings')

    op.drop_index(op.f('ix_account_values_timestamp'), table_name='account_values')
    op.drop_index(op.f('ix_account_values_account_id'), table_name='account_values')
    op.drop_index(op.f('ix_account_values_id'), table_name='account_values')
    op.drop_table('account_values')

    op.drop_index(op.f('ix_accounts_user_id'), table_name='accounts')
    op.drop_index(op.f('ix_accounts_id'), table_name='accounts')
    op.drop_table('accounts')

    # Drop account_type enum
    op.execute("DROP TYPE accounttype")

    op.drop_index(op.f('ix_financial_institutions_name'), table_name='financial_institutions')
    op.drop_index(op.f('ix_financial_institutions_user_id'), table_name='financial_institutions')
    op.drop_index(op.f('ix_financial_institutions_id'), table_name='financial_institutions')
    op.drop_table('financial_institutions')

    op.drop_index(op.f('ix_security_prices_timestamp'), table_name='security_prices')
    op.drop_index(op.f('ix_security_prices_security_id'), table_name='security_prices')
    op.drop_index(op.f('ix_security_prices_id'), table_name='security_prices')
    op.drop_table('security_prices')

    op.drop_index(op.f('ix_securities_symbol'), table_name='securities')
    op.drop_index(op.f('ix_securities_id'), table_name='securities')
    op.drop_table('securities')

    op.drop_index(op.f('ix_users_reset_token'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
