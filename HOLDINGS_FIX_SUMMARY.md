# Holdings API Security Serialization Fix

## Problem

The holdings API endpoint was correctly loading security relationships from the database using `selectinload(Holding.security)`, but the frontend was receiving holdings with `security` as `null` or displaying "Unknown" for security names.

**Root Cause**: The `HoldingResponse` Pydantic schema did not include a `security` field to serialize the loaded SQLAlchemy relationship. While the database query was correct, Pydantic couldn't serialize the nested security object because it wasn't defined in the response schema.

## Solution

Added a `security` field to the `HoldingResponse` schema with type `SecurityResponse` to properly serialize the nested security relationship.

### Files Modified

#### 1. `/src/app/schemas/holding.py`

**Changes:**
- Added import for `SecurityResponse` from `app.schemas.security`
- Added `security: SecurityResponse` field to `HoldingResponse` class

**Before:**
```python
class HoldingResponse(HoldingBase):
    """Schema for holding response."""

    id: UUID
    account_id: UUID
    timestamp: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

**After:**
```python
from app.schemas.security import SecurityResponse

class HoldingResponse(HoldingBase):
    """Schema for holding response."""

    id: UUID
    account_id: UUID
    security: SecurityResponse  # Nested security details
    timestamp: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

## How It Works

1. **Database Layer** (`/src/app/api/routes/holdings.py`):
   - Already correctly using `selectinload(Holding.security)` to eagerly load the relationship
   - No changes needed to the endpoint logic

2. **Model Layer** (`/src/app/models/holding.py`):
   - Already has correct relationship: `security: Mapped["Security"] = relationship("Security")`
   - No changes needed

3. **Schema Layer** (`/src/app/schemas/holding.py`):
   - **FIXED**: Now includes `security: SecurityResponse` field
   - Pydantic can now properly serialize the nested security object using `from_attributes=True`

## Response Format

The holdings endpoint now returns complete security details:

```json
{
  "id": "uuid",
  "account_id": "uuid",
  "security_id": "uuid",
  "security": {
    "id": "uuid",
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "currency": "USD",
    "security_type": "EQUITY",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "market_cap": 3000000000000,
    "last_synced_at": "2024-01-15T10:30:00Z",
    "is_syncing": false,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "in_database": true
  },
  "shares": "10.500000",
  "average_price_per_share": "150.25",
  "timestamp": "2024-01-15T10:00:00Z",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

## Testing

Added comprehensive tests to verify the fix:

1. **`test_get_holdings`** - Enhanced to verify:
   - Security object is present in response
   - All security fields are included (id, symbol, name, exchange, currency, security_type)
   - Security details match the database records

2. **`test_get_single_holding_with_security_details`** - New test to verify:
   - Single holding endpoint returns complete security details
   - All security fields are properly serialized (including sector, industry)
   - Security data matches exactly what's in the database

### Test Results

```bash
127 passed in 14.65s
```

All tests pass, including the new comprehensive security serialization tests.

## Affected Endpoints

This fix applies to all holdings endpoints that return `HoldingResponse`:

1. `GET /api/v1/accounts/{account_id}/holdings/` - List all holdings
2. `GET /api/v1/accounts/{account_id}/holdings/{holding_id}` - Get single holding
3. `POST /api/v1/accounts/{account_id}/holdings/` - Create holding (returns created holding)
4. `PUT /api/v1/accounts/{account_id}/holdings/{holding_id}` - Update holding (returns updated holding)

All endpoints now properly include nested security details in their responses.

## Frontend Impact

The frontend can now reliably access security details from holdings:

```typescript
// Before: security was null
holding.security // null or undefined

// After: security is fully populated
holding.security.name        // "Apple Inc."
holding.security.symbol      // "AAPL"
holding.security.exchange    // "NASDAQ"
holding.security.currency    // "USD"
holding.security.sector      // "Technology"
```

## Additional Notes

- No database migration required (schema was already correct)
- No changes to API endpoint logic required (query was already correct)
- Only schema serialization layer was updated
- The existing `HoldingWithSecurity` schema (which had flat fields like `security_symbol`, `security_name`) can still be used for specialized views if needed, but `HoldingResponse` is now the standard response with full nested security details
