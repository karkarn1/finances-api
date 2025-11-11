# API Reference

Complete reference documentation for all Finances API endpoints.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication-endpoints)
- [Users](#user-endpoints)
- [Securities](#securities-endpoints)
- [Currencies](#currency-endpoints)
- [Financial Institutions](#financial-institution-endpoints)
- [Accounts](#account-endpoints)
- [Account Values](#account-value-endpoints)
- [Holdings](#holding-endpoints)
- [Health Checks](#health-check-endpoints)
- [Error Responses](#error-responses)

## Overview

**Base URL:** `http://localhost:8000/api/v1`

**Authentication:** Most endpoints require JWT authentication via Bearer token in the `Authorization` header.

**Content Type:** All requests and responses use `application/json`.

**Interactive Documentation:**
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Authentication Endpoints

### Register User

Create a new user account.

**Endpoint:** `POST /api/v1/auth/register`

**Authentication:** None required

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:** `201 Created`
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request` - Invalid email format or password too weak
- `409 Conflict` - Email already registered

---

### Login

Authenticate and receive JWT tokens.

**Endpoint:** `POST /api/v1/auth/login`

**Authentication:** None required

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid credentials
- `403 Forbidden` - Account disabled

---

### Refresh Token

Get new access token using refresh token.

**Endpoint:** `POST /api/v1/auth/refresh`

**Authentication:** Refresh token required

**Headers:**
```
Authorization: Bearer <refresh_token>
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or expired refresh token

---

### Logout

Invalidate tokens (future implementation).

**Endpoint:** `POST /api/v1/auth/logout`

**Authentication:** Required

**Response:** `200 OK`
```json
{
  "message": "Successfully logged out"
}
```

---

### Forgot Password

Initiate password reset flow.

**Endpoint:** `POST /api/v1/auth/forgot-password`

**Authentication:** None required

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset instructions sent to email"
}
```

---

### Reset Password

Complete password reset with token.

**Endpoint:** `POST /api/v1/auth/reset-password`

**Authentication:** None required

**Request Body:**
```json
{
  "token": "reset-token-from-email",
  "new_password": "NewSecurePass123!"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password successfully reset"
}
```

**Error Responses:**
- `400 Bad Request` - Invalid or expired token

---

### Change Password

Change password for authenticated user.

**Endpoint:** `POST /api/v1/auth/change-password`

**Authentication:** Required

**Request Body:**
```json
{
  "current_password": "OldPass123!",
  "new_password": "NewSecurePass123!"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password successfully changed"
}
```

**Error Responses:**
- `401 Unauthorized` - Current password incorrect

---

### Verify Email

Verify email address (future implementation).

**Endpoint:** `POST /api/v1/auth/verify-email`

**Authentication:** None required

**Request Body:**
```json
{
  "token": "verification-token-from-email"
}
```

**Response:** `200 OK`
```json
{
  "message": "Email successfully verified"
}
```

---

## User Endpoints

### Get Current User

Get authenticated user's information.

**Endpoint:** `GET /api/v1/users/me`

**Authentication:** Required

**Response:** `200 OK`
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:00:00Z"
}
```

---

### Update Current User

Update authenticated user's information.

**Endpoint:** `PATCH /api/v1/users/me`

**Authentication:** Required

**Request Body:**
```json
{
  "email": "newemail@example.com"
}
```

**Response:** `200 OK`
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "newemail@example.com",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:05:00Z"
}
```

---

### Delete Current User

Delete authenticated user's account.

**Endpoint:** `DELETE /api/v1/users/me`

**Authentication:** Required

**Response:** `204 No Content`

---

### List Users (Admin)

List all users (admin only).

**Endpoint:** `GET /api/v1/users`

**Authentication:** Admin required

**Query Parameters:**
- `skip` (int, default: 0) - Number of records to skip
- `limit` (int, default: 100) - Maximum records to return

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "user1@example.com",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2025-11-11T10:00:00Z",
    "updated_at": "2025-11-11T10:00:00Z"
  },
  {
    "id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "email": "user2@example.com",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2025-11-10T10:00:00Z",
    "updated_at": "2025-11-10T10:00:00Z"
  }
]
```

---

### Get User by ID (Admin)

Get specific user by ID (admin only).

**Endpoint:** `GET /api/v1/users/{user_id}`

**Authentication:** Admin required

**Path Parameters:**
- `user_id` (UUID) - User identifier

**Response:** `200 OK`
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:00:00Z"
}
```

**Error Responses:**
- `404 Not Found` - User not found

---

## Securities Endpoints

### Search Securities

Search for securities by symbol or name.

**Endpoint:** `GET /api/v1/securities/search`

**Authentication:** Required

**Query Parameters:**
- `query` (string, required) - Search term (symbol or name)
- `limit` (int, default: 10) - Maximum results to return

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "security_type": "STOCK",
    "exchange": "NASDAQ",
    "currency_code": "USD",
    "created_at": "2025-11-11T10:00:00Z",
    "updated_at": "2025-11-11T10:00:00Z"
  },
  {
    "id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "symbol": "GOOGL",
    "name": "Alphabet Inc.",
    "security_type": "STOCK",
    "exchange": "NASDAQ",
    "currency_code": "USD",
    "created_at": "2025-11-10T10:00:00Z",
    "updated_at": "2025-11-10T10:00:00Z"
  }
]
```

---

### Get Security Details

Get detailed information about a security.

**Endpoint:** `GET /api/v1/securities/{symbol}`

**Authentication:** Required

**Path Parameters:**
- `symbol` (string) - Security ticker symbol (e.g., AAPL)

**Response:** `200 OK`
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "security_type": "STOCK",
  "exchange": "NASDAQ",
  "currency_code": "USD",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "market_cap": 3000000000000,
  "current_price": 180.50,
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:00:00Z"
}
```

**Error Responses:**
- `404 Not Found` - Security not found

---

### Sync Security Data

Fetch latest data from yfinance and update database.

**Endpoint:** `POST /api/v1/securities/{symbol}/sync`

**Authentication:** Required

**Path Parameters:**
- `symbol` (string) - Security ticker symbol

**Response:** `200 OK`
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "security_type": "STOCK",
  "exchange": "NASDAQ",
  "currency_code": "USD",
  "current_price": 180.50,
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T12:00:00Z"
}
```

**Error Responses:**
- `404 Not Found` - Symbol not found on yfinance
- `503 Service Unavailable` - yfinance API unavailable

---

### Get Price History

Get historical OHLCV price data.

**Endpoint:** `GET /api/v1/securities/{symbol}/prices`

**Authentication:** Required

**Path Parameters:**
- `symbol` (string) - Security ticker symbol

**Query Parameters:**
- `interval` (string, default: "1d") - Data interval: "1m", "1h", "1d", "1wk"
- `start_date` (date, optional) - Start date (YYYY-MM-DD)
- `end_date` (date, optional) - End date (YYYY-MM-DD)
- `limit` (int, default: 100) - Maximum records to return

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "security_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "date": "2025-11-11",
    "interval": "1d",
    "open": 178.50,
    "high": 182.00,
    "low": 177.00,
    "close": 180.50,
    "volume": 50000000,
    "created_at": "2025-11-11T22:00:00Z"
  },
  {
    "id": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
    "security_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "date": "2025-11-10",
    "interval": "1d",
    "open": 180.00,
    "high": 181.50,
    "low": 178.00,
    "close": 178.50,
    "volume": 48000000,
    "created_at": "2025-11-10T22:00:00Z"
  }
]
```

---

## Currency Endpoints

### List Currencies

Get list of all currencies.

**Endpoint:** `GET /api/v1/currencies`

**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "code": "USD",
    "name": "US Dollar",
    "symbol": "$",
    "created_at": "2025-11-11T10:00:00Z",
    "updated_at": "2025-11-11T10:00:00Z"
  },
  {
    "code": "EUR",
    "name": "Euro",
    "symbol": "€",
    "created_at": "2025-11-11T10:00:00Z",
    "updated_at": "2025-11-11T10:00:00Z"
  }
]
```

---

### Create Currency

Create a new currency.

**Endpoint:** `POST /api/v1/currencies`

**Authentication:** Required

**Request Body:**
```json
{
  "code": "GBP",
  "name": "British Pound",
  "symbol": "£"
}
```

**Response:** `201 Created`
```json
{
  "code": "GBP",
  "name": "British Pound",
  "symbol": "£",
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:00:00Z"
}
```

---

### Get Currency

Get specific currency details.

**Endpoint:** `GET /api/v1/currencies/{code}`

**Authentication:** Required

**Path Parameters:**
- `code` (string) - Currency code (e.g., USD, EUR)

**Response:** `200 OK`
```json
{
  "code": "USD",
  "name": "US Dollar",
  "symbol": "$",
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T10:00:00Z"
}
```

---

### Update Currency

Update currency details.

**Endpoint:** `PATCH /api/v1/currencies/{code}`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "United States Dollar",
  "symbol": "$"
}
```

**Response:** `200 OK`

---

### Delete Currency

Delete a currency.

**Endpoint:** `DELETE /api/v1/currencies/{code}`

**Authentication:** Required

**Response:** `204 No Content`

---

### Get Exchange Rates

Get exchange rates for a currency.

**Endpoint:** `GET /api/v1/currencies/{code}/rates`

**Authentication:** Required

**Query Parameters:**
- `start_date` (date, optional) - Start date
- `end_date` (date, optional) - End date

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "from_currency": "USD",
    "to_currency": "EUR",
    "rate": 0.92,
    "date": "2025-11-11",
    "created_at": "2025-11-11T10:00:00Z"
  }
]
```

---

## Financial Institution Endpoints

### List Institutions

Get list of all financial institutions.

**Endpoint:** `GET /api/v1/financial-institutions`

**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Vanguard",
    "institution_type": "BROKERAGE",
    "created_at": "2025-11-11T10:00:00Z",
    "updated_at": "2025-11-11T10:00:00Z"
  },
  {
    "id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "name": "Chase Bank",
    "institution_type": "BANK",
    "created_at": "2025-11-10T10:00:00Z",
    "updated_at": "2025-11-10T10:00:00Z"
  }
]
```

---

### Create Institution

Create a new financial institution.

**Endpoint:** `POST /api/v1/financial-institutions`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Fidelity",
  "institution_type": "BROKERAGE"
}
```

**Response:** `201 Created`

---

### Get Institution

Get specific institution details.

**Endpoint:** `GET /api/v1/financial-institutions/{id}`

**Authentication:** Required

**Response:** `200 OK`

---

### Update Institution

Update institution details.

**Endpoint:** `PATCH /api/v1/financial-institutions/{id}`

**Authentication:** Required

**Response:** `200 OK`

---

### Delete Institution

Delete an institution.

**Endpoint:** `DELETE /api/v1/financial-institutions/{id}`

**Authentication:** Required

**Response:** `204 No Content`

---

## Account Endpoints

### List Accounts

Get user's accounts.

**Endpoint:** `GET /api/v1/accounts`

**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "name": "Retirement Account",
    "account_type": "INVESTMENT",
    "financial_institution_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
    "currency_code": "USD",
    "is_active": true,
    "created_at": "2025-11-11T10:00:00Z",
    "updated_at": "2025-11-11T10:00:00Z"
  }
]
```

---

### Create Account

Create a new account.

**Endpoint:** `POST /api/v1/accounts`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Savings Account",
  "account_type": "CASH",
  "financial_institution_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
  "currency_code": "USD"
}
```

**Response:** `201 Created`

---

### Get Account

Get specific account details.

**Endpoint:** `GET /api/v1/accounts/{id}`

**Authentication:** Required

**Response:** `200 OK`

---

### Update Account

Update account details.

**Endpoint:** `PATCH /api/v1/accounts/{id}`

**Authentication:** Required

**Response:** `200 OK`

---

### Delete Account

Delete an account.

**Endpoint:** `DELETE /api/v1/accounts/{id}`

**Authentication:** Required

**Response:** `204 No Content`

---

## Account Value Endpoints

### Get Account Value History

Get historical values for an account.

**Endpoint:** `GET /api/v1/accounts/{id}/values`

**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "account_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "value": 50000.00,
    "value_date": "2025-11-11",
    "created_at": "2025-11-11T10:00:00Z"
  }
]
```

---

### Record Account Value

Record a new account value.

**Endpoint:** `POST /api/v1/accounts/{id}/values`

**Authentication:** Required

**Request Body:**
```json
{
  "value": 51000.00,
  "value_date": "2025-11-12"
}
```

**Response:** `201 Created`

---

### Get Latest Account Values

Get latest values for all user accounts.

**Endpoint:** `GET /api/v1/account-values/latest`

**Authentication:** Required

**Response:** `200 OK`

---

## Holding Endpoints

### List Holdings

Get user's holdings.

**Endpoint:** `GET /api/v1/holdings`

**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "account_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
    "security_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
    "quantity": 100.0,
    "average_cost": 150.00,
    "created_at": "2025-11-11T10:00:00Z",
    "updated_at": "2025-11-11T10:00:00Z"
  }
]
```

---

### Create Holding

Create a new holding.

**Endpoint:** `POST /api/v1/holdings`

**Authentication:** Required

**Request Body:**
```json
{
  "account_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
  "security_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
  "quantity": 50.0,
  "average_cost": 175.00
}
```

**Response:** `201 Created`

---

### Get Holding

Get specific holding details.

**Endpoint:** `GET /api/v1/holdings/{id}`

**Authentication:** Required

**Response:** `200 OK`

---

### Update Holding

Update holding details.

**Endpoint:** `PATCH /api/v1/holdings/{id}`

**Authentication:** Required

**Response:** `200 OK`

---

### Delete Holding

Delete a holding.

**Endpoint:** `DELETE /api/v1/holdings/{id}`

**Authentication:** Required

**Response:** `204 No Content`

---

## Health Check Endpoints

### Application Health

Check application health status.

**Endpoint:** `GET /health`

**Authentication:** None

**Response:** `200 OK`
```json
{
  "status": "healthy"
}
```

---

### Database Health

Check database connectivity.

**Endpoint:** `GET /health/db`

**Authentication:** None

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

### Redis Health

Check Redis connectivity.

**Endpoint:** `GET /health/redis`

**Authentication:** None

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "redis": "connected"
}
```

---

## Error Responses

### Standard Error Format

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

- `200 OK` - Request succeeded
- `201 Created` - Resource created successfully
- `204 No Content` - Request succeeded with no response body
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required or failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource already exists
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - External service unavailable

### Validation Error Format

Pydantic validation errors (422 status) include field-level details:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    },
    {
      "loc": ["body", "password"],
      "msg": "ensure this value has at least 8 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

---

**Last Updated:** November 11, 2025
