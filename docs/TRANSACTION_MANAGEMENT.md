# Database Transaction Management Guide

This guide explains how to use the database transaction context managers in the finances-api project.

## Overview

The application provides three transaction context managers for explicit transaction control:

1. **`transactional(db)`** - Automatic commit/rollback for write operations
2. **`read_only_transaction(db)`** - Read-only operations that never commit
3. **`with_savepoint(db, name)`** - Nested transaction savepoints

All are located in `src/app/db/session.py`.

## Standard Dependency Injection (Recommended for Routes)

For most FastAPI routes, use the standard dependency injection approach:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

router = APIRouter()

@router.post("/users")
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Create a new user.

    The get_db dependency automatically manages the transaction lifecycle:
    - Commits on successful completion
    - Rolls back on any exception
    - Closes the session in finally block
    """
    new_user = User(**user_data.dict())
    db.add(new_user)
    # Auto-commits when route exits successfully
    return UserResponse.from_orm(new_user)
```

**When to use:** Routes that create or update a single resource. The dependency injection handles all transaction lifecycle automatically.

## Explicit Transaction Control (Services)

Use explicit `transactional()` context manager when you need clear transaction boundaries or multiple independent transactions within a single function:

### Basic Usage

```python
from app.db.session import transactional

async def create_or_update_security(
    db: AsyncSession,
    symbol: str,
    data: dict,
) -> Security:
    """Create or update security with automatic commit/rollback."""

    symbol = symbol.upper()

    async with transactional(db):
        security = await repo.get_by_symbol(symbol)

        if security:
            # Update existing
            for key, value in data.items():
                setattr(security, key, value)
        else:
            # Create new
            security = Security(symbol=symbol, **data)
            db.add(security)
        # Auto-commits on successful exit

    # Safe to refresh outside transaction context
    await db.refresh(security)
    return security
```

**Benefits:**
- ✅ Automatic commit on success
- ✅ Automatic rollback on exception
- ✅ Clear transaction boundaries
- ✅ Logging of transaction lifecycle

### Multiple Independent Transactions

Use separate `transactional()` contexts when operations can succeed or fail independently:

```python
async def sync_price_history(
    db: AsyncSession,
    security: Security,
) -> int:
    """Fetch price data with independent transaction per price type."""

    total_synced = 0

    # Daily prices in separate transaction
    try:
        async with transactional(db):
            daily_prices = fetch_daily_prices(security.symbol)
            if daily_prices:
                await repo.bulk_create(daily_prices)
                total_synced += len(daily_prices)
    except PriceError as e:
        logger.warning(f"Daily prices failed: {e}")

    # Intraday prices in separate transaction
    # If daily fails, intraday can still succeed
    try:
        async with transactional(db):
            intraday_prices = fetch_intraday_prices(security.symbol)
            if intraday_prices:
                await repo.bulk_create(intraday_prices)
                total_synced += len(intraday_prices)
    except PriceError as e:
        logger.warning(f"Intraday prices failed: {e}")

    return total_synced
```

**Benefits:**
- ✅ Partial success: daily prices commit even if intraday fails
- ✅ Independent error handling per operation
- ✅ Better logging and observability

### Controlling Commits

Use `commit=False` to prevent automatic commits:

```python
async def validate_user_data(db: AsyncSession, user_id: int) -> UserValidation:
    """Validate user data without modifying database."""

    async with transactional(db, commit=False):
        user = await repo.get_by_id(user_id)

        if not user:
            raise ValueError("User not found")

        # Read user and related data
        accounts = await repo.get_accounts(user_id)

        # Perform validation (no modifications)
        validation = validate_user(user, accounts)

        # Never commits, even on success

    return validation
```

## Read-Only Transactions

Use `read_only_transaction()` for queries that explicitly should never modify the database:

```python
from app.db.session import read_only_transaction

async def get_security_with_details(db: AsyncSession, symbol: str) -> dict:
    """Fetch security details in read-only transaction."""

    async with read_only_transaction(db):
        # Multiple reads are safe
        security = await repo.get_by_symbol(symbol)

        if not security:
            raise ValueError(f"Security {symbol} not found")

        # Read related data
        prices = await price_repo.get_latest(security.id, limit=10)
        holdings = await holding_repo.get_by_security(security.id)

        # All queries succeed or all fail together

    return {
        "security": security,
        "prices": prices,
        "holdings": holdings,
    }
```

**Benefits:**
- ✅ Prevents accidental modifications
- ✅ Clear intent in code
- ✅ Logical grouping of reads

## Nested Transactions with Savepoints

Use `with_savepoint()` for nested transaction control within an outer transaction:

```python
from app.db.session import transactional, with_savepoint

async def sync_security_with_error_recovery(
    db: AsyncSession,
    symbol: str,
) -> tuple[Security, int]:
    """Sync security with error recovery using savepoints."""

    async with transactional(db):
        # Create/update security (outer transaction)
        security = await create_or_update_security(db, symbol)

        # Try to sync prices, but don't fail entire sync
        prices_synced = 0

        try:
            async with with_savepoint(db, "daily_prices"):
                daily = fetch_daily_prices(symbol)
                await repo.bulk_create(daily)
                prices_synced += len(daily)
        except PriceError:
            logger.warning(f"Daily prices failed for {symbol}")
            # Savepoint rolled back, but security creation succeeded

        # If daily fails, we still update last_synced_at
        security.last_synced_at = datetime.now(UTC)
        # Security and intraday prices committed on outer exit

    return security, prices_synced
```

**When to use:**
- ✅ Partial failure recovery within larger operations
- ✅ Optional operations that shouldn't fail entire sync
- ✅ Complex nested transaction logic

## Error Handling Patterns

### Pattern 1: Transaction-Aware Error Handling

```python
async def create_user(db: AsyncSession, email: str, username: str) -> User:
    """Create user with proper error handling."""

    try:
        async with transactional(db):
            # Validation happens before transaction
            if await repo.exists_by_email(email):
                raise ValueError("Email already registered")

            user = User(email=email, username=username)
            db.add(user)
            # Auto-commits on success

        await db.refresh(user)
        return user

    except ValueError as e:
        # Transaction already rolled back
        logger.warning(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected error, transaction rolled back
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### Pattern 2: Partial Success with Independent Transactions

```python
async def bulk_sync_securities(db: AsyncSession, symbols: list[str]) -> SyncResult:
    """Sync multiple securities, tracking success/failure independently."""

    result = SyncResult(total=len(symbols))

    for symbol in symbols:
        try:
            async with transactional(db):
                security = await get_or_create_security(db, symbol)
                await sync_prices(db, security)
                result.succeeded.append(symbol)
        except InvalidSymbolError as e:
            logger.warning(f"Invalid symbol {symbol}: {e}")
            result.failed[symbol] = "invalid_symbol"
        except APIError as e:
            logger.warning(f"API error for {symbol}: {e}")
            result.failed[symbol] = "api_error"
        except Exception as e:
            logger.error(f"Unexpected error for {symbol}: {e}")
            result.failed[symbol] = "unexpected_error"

    return result
```

## Transaction Lifecycle Logging

All transaction context managers log their lifecycle:

```
# Successful transaction
DEBUG - Transaction committed successfully

# Failed transaction
ERROR - Transaction rolled back due to error: ValueError: Duplicate email

# Read-only transaction error
ERROR - Read-only transaction error: DatabaseError: Connection lost

# Savepoint rollback
WARNING - Savepoint 'daily_prices' rolled back due to error: APIError: Rate limit exceeded
```

Monitor logs to debug transaction issues.

## Best Practices

### DO ✅

- **Use dependency injection for routes** - Let `get_db` manage transactions
- **Use `transactional()` in services** - Clear boundaries for business logic
- **Use `read_only_transaction()` for queries** - Prevents accidental modifications
- **Use `with_savepoint()` for error recovery** - Partial success in complex operations
- **Log transaction lifecycle** - Helps debug issues
- **Refresh objects outside transaction** - Ensures they reflect committed state
- **Handle exceptions after rollback** - Log and return meaningful errors

### DON'T ❌

- **Don't use manual `await db.commit()`** - Let context managers handle it
- **Don't nest `transactional()` contexts** - Use `with_savepoint()` instead
- **Don't mix different transaction managers** - Stick to one pattern per function
- **Don't refresh objects inside transaction** - Refresh after transaction exits
- **Don't catch and suppress exceptions** - Log and re-raise or handle appropriately
- **Don't create long-running transactions** - Keep them focused and short

## Performance Considerations

### Connection Pooling

The session factory is configured with:
- `pool_size=10` - Keep 10 connections ready
- `max_overflow=20` - Allow up to 20 additional overflow connections
- `pool_pre_ping=True` - Verify connections before use

### Transaction Duration

Keep transactions short:

```python
# GOOD: Fetch external data outside transaction
async def create_security(db: AsyncSession, symbol: str) -> Security:
    # Fetch from external API (slow, outside transaction)
    data = await fetch_yfinance_data(symbol)

    # Quick database operation inside transaction
    async with transactional(db):
        security = Security(symbol=symbol, **data)
        db.add(security)

    return security

# BAD: Long-running API call inside transaction
async def create_security_slow(db: AsyncSession, symbol: str) -> Security:
    async with transactional(db):
        # Locks database while fetching from API (slow!)
        data = await fetch_yfinance_data(symbol)
        security = Security(symbol=symbol, **data)
        db.add(security)

    return security
```

### Bulk Operations

Use bulk operations with `bulk_create()` for performance:

```python
async def sync_prices(db: AsyncSession, security: Security) -> int:
    """Efficiently sync many price records."""

    async with transactional(db):
        # Fetch all prices at once
        prices = fetch_historical_prices(security.symbol, period="max")

        # Bulk insert (one query for all records)
        await repo.bulk_create(prices)  # Fast

    return len(prices)
```

## Common Patterns

### Update with Conditions

```python
async def update_security_if_not_syncing(
    db: AsyncSession,
    symbol: str,
    data: dict,
) -> Security | None:
    """Update security only if not currently syncing."""

    async with transactional(db):
        security = await repo.get_by_symbol(symbol)

        if not security or security.is_syncing:
            # Rollback on condition failure
            await db.rollback()
            return None

        for key, value in data.items():
            setattr(security, key, value)

    await db.refresh(security)
    return security
```

### Create with Default Values

```python
async def create_account(
    db: AsyncSession,
    user_id: int,
    name: str,
) -> Account:
    """Create account with default values."""

    async with transactional(db):
        account = Account(
            user_id=user_id,
            name=name,
            currency="USD",  # Default
            account_type="CHECKING",  # Default
            is_active=True,  # Default
        )
        db.add(account)

    await db.refresh(account)
    return account
```

## Testing

Transaction context managers are fully tested in `tests/db/test_transactions.py`:

- ✅ Commits on success
- ✅ Rolls back on exception
- ✅ Atomicity of multiple operations
- ✅ Read-only transaction prevents commits
- ✅ Savepoint partial rollback
- ✅ Exception re-raising
- ✅ Nested savepoints

Run tests with:

```bash
make test  # Run all tests
docker-compose exec app pytest tests/db/test_transactions.py -v
```

## Migration Guide

If you're updating existing code to use transaction context managers:

### Before (Manual Commits)

```python
async def create_user(db: AsyncSession, email: str) -> User:
    user = User(email=email)
    db.add(user)
    await db.commit()  # Manual
    await db.refresh(user)  # Manual
    return user
```

### After (Transactional Context)

```python
async def create_user(db: AsyncSession, email: str) -> User:
    async with transactional(db):
        user = User(email=email)
        db.add(user)
    # Auto-commits on exit
    await db.refresh(user)
    return user
```

## Troubleshooting

### Issue: "Transaction rolled back due to error"

Check the logs for the actual error:
```
ERROR - Transaction rolled back due to error: IntegrityError: Duplicate key
```

Fix the underlying error (validation, unique constraint, etc.).

### Issue: Object not found after transaction

Always refresh objects outside the transaction:

```python
async with transactional(db):
    user = User(email="test@example.com")
    db.add(user)

# Refresh OUTSIDE transaction
await db.refresh(user)
print(user.id)  # Now has ID from database
```

### Issue: Multiple transactions in route

For routes, use the standard `get_db` dependency instead of manual context managers. The dependency injection handles all transactions automatically.

---

For more information, see `src/app/db/session.py` and the transaction tests in `tests/db/test_transactions.py`.
