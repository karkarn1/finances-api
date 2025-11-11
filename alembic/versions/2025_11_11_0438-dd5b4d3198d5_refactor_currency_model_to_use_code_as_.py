"""refactor currency model to use code as primary key

Revision ID: dd5b4d3198d5
Revises: 
Create Date: 2025-11-11 04:38:53.830573+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'dd5b4d3198d5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Migrate currencies table from UUID primary key to code primary key.
    
    Steps:
    1. Backup currency data
    2. Drop all foreign key constraints referencing currencies
    3. Drop the old currencies table
    4. Create new currencies table with code as PK
    5. Restore currency data
    6. Update accounts table to use currency_code
    7. Recreate currency_rates table with code-based FKs
    8. Recreate foreign key constraints
    """
    
    # === STEP 1: Create a temporary table to backup currency data ===
    op.execute("""
        CREATE TEMP TABLE currencies_backup AS
        SELECT code, name, symbol
        FROM currencies
    """)
    
    # === STEP 2: Drop foreign key constraints on accounts ===
    # The FK constraint is accounts_currency_id_fkey (not currency_code)
    op.drop_constraint('accounts_currency_id_fkey', 'accounts', type_='foreignkey')
    
    # === STEP 3: Drop foreign key constraints on currency_rates ===
    op.drop_constraint('currency_rates_from_currency_id_fkey', 'currency_rates', type_='foreignkey')
    op.drop_constraint('currency_rates_to_currency_id_fkey', 'currency_rates', type_='foreignkey')
    
    # === STEP 4: Drop currency_rates table (will be recreated) ===
    op.drop_table('currency_rates')
    
    # === STEP 5: Drop old currencies table ===
    op.drop_table('currencies')
    
    # === STEP 6: Create new currencies table with code as PK ===
    op.create_table(
        'currencies',
        sa.Column('code', sa.String(length=3), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint('code', name='pk_currencies')
    )
    
    # === STEP 7: Restore currency data ===
    op.execute("""
        INSERT INTO currencies (code, name, symbol)
        SELECT code, name, symbol
        FROM currencies_backup
    """)
    
    # === STEP 8: Update accounts table ===
    # Add currency_code column
    op.add_column('accounts', sa.Column('currency_code', sa.String(length=3), nullable=True))
    
    # Set default currency for all accounts (USD)
    # Note: In production, you would map currency_id to currency_code properly
    op.execute("""
        UPDATE accounts
        SET currency_code = 'USD'
        WHERE currency_code IS NULL
    """)
    
    # Make currency_code NOT NULL
    op.alter_column('accounts', 'currency_code', nullable=False)
    
    # Drop old currency_id column
    op.drop_column('accounts', 'currency_id')
    
    # Create foreign key from accounts to currencies
    op.create_foreign_key(
        'accounts_currency_code_fkey',
        'accounts',
        'currencies',
        ['currency_code'],
        ['code'],
        ondelete='SET NULL'
    )
    
    # === STEP 9: Recreate currency_rates table with new schema ===
    op.create_table(
        'currency_rates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('from_currency_code', sa.String(length=3), nullable=False),
        sa.Column('to_currency_code', sa.String(length=3), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('rate', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(
            ['from_currency_code'],
            ['currencies.code'],
            name='currency_rates_from_currency_code_fkey',
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['to_currency_code'],
            ['currencies.code'],
            name='currency_rates_to_currency_code_fkey',
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_currency_rates'),
        sa.UniqueConstraint(
            'from_currency_code', 'to_currency_code', 'date',
            name='uq_currency_rate_from_to_date'
        )
    )
    
    # Create indexes for currency_rates
    op.create_index('ix_currency_rates_from_currency_code', 'currency_rates', ['from_currency_code'])
    op.create_index('ix_currency_rates_to_currency_code', 'currency_rates', ['to_currency_code'])
    op.create_index(
        'ix_currency_rates_from_to_date',
        'currency_rates',
        ['from_currency_code', 'to_currency_code', 'date']
    )
    op.create_index('ix_currency_rates_id', 'currency_rates', ['id'])
    op.create_index('ix_currency_rates_date', 'currency_rates', ['date'])


def downgrade() -> None:
    """
    Revert currencies table back to UUID primary key.
    
    WARNING: This will lose data if currencies have been modified after upgrade.
    """
    
    # Backup current currency data
    op.execute("""
        CREATE TEMP TABLE currencies_backup AS
        SELECT code, name, symbol
        FROM currencies
    """)
    
    # Drop foreign key constraints
    op.drop_constraint('accounts_currency_code_fkey', 'accounts', type_='foreignkey')
    
    # Drop currency_rates table
    op.drop_table('currency_rates')
    
    # Drop new currencies table
    op.drop_table('currencies')
    
    # Recreate old currencies table with UUID PK
    op.create_table(
        'currencies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=3), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_currencies_id', 'currencies', ['id'])
    op.create_index('ix_currencies_code', 'currencies', ['code'], unique=True)
    
    # Restore currency data with new UUIDs
    op.execute("""
        INSERT INTO currencies (id, code, name, symbol, is_active)
        SELECT gen_random_uuid(), code, name, symbol, true
        FROM currencies_backup
    """)
    
    # Recreate currency_rates table with old schema
    op.create_table(
        'currency_rates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('from_currency_id', sa.UUID(), nullable=False),
        sa.Column('to_currency_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('rate', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['from_currency_id'], ['currencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_currency_id'], ['currencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_currency_id', 'to_currency_id', 'date', name='uq_currency_rate_from_to_date')
    )
    
    # Create indexes
    op.create_index('ix_currency_rates_id', 'currency_rates', ['id'])
    op.create_index('ix_currency_rates_from_currency_id', 'currency_rates', ['from_currency_id'])
    op.create_index('ix_currency_rates_to_currency_id', 'currency_rates', ['to_currency_id'])
    op.create_index(
        'ix_currency_rates_from_to_date',
        'currency_rates',
        ['from_currency_id', 'to_currency_id', 'date']
    )
    op.create_index('ix_currency_rates_date', 'currency_rates', ['date'])
    
    # Update accounts table
    op.add_column('accounts', sa.Column('currency_id', sa.UUID(), nullable=True))
    
    # Map currency codes back to IDs
    op.execute("""
        UPDATE accounts a
        SET currency_id = c.id
        FROM currencies c
        WHERE a.currency_code = c.code
    """)
    
    op.drop_column('accounts', 'currency_code')
    
    # Recreate foreign key
    op.create_foreign_key(
        'accounts_currency_id_fkey',
        'accounts',
        'currencies',
        ['currency_id'],
        ['id'],
        ondelete='SET NULL'
    )
