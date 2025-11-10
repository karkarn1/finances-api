"""Currency API routes for managing currencies and exchange rates."""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.currency import Currency
from app.models.currency_rate import CurrencyRate
from app.schemas.currency import CurrencyCreate, CurrencyResponse, CurrencyUpdate
from app.schemas.currency_rate import (
    CurrencyRatesResponse,
    SyncRatesResponse,
)
from app.services.currency_service import sync_currency_rates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[CurrencyResponse])
async def list_currencies(
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(True, description="Only return active currencies"),
) -> list[Currency]:
    """List all currencies in the system.

    Args:
        db: Database session
        active_only: Filter to only active currencies (default: True)

    Returns:
        List of currencies

    Example:
        GET /api/v1/currencies
        GET /api/v1/currencies?active_only=false
    """
    logger.info(f"Listing currencies (active_only={active_only})")

    query = select(Currency)
    if active_only:
        query = query.where(Currency.is_active == True)  # noqa: E712

    query = query.order_by(Currency.code)

    result = await db.execute(query)
    currencies = result.scalars().all()

    logger.info(f"Found {len(currencies)} currencies")
    return list(currencies)


@router.get("/{code}", response_model=CurrencyResponse)
async def get_currency(
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Currency:
    """Get a specific currency by code.

    Args:
        code: ISO 4217 currency code (e.g., "USD", "EUR")
        db: Database session

    Returns:
        Currency details

    Raises:
        HTTPException: 404 if currency not found

    Example:
        GET /api/v1/currencies/USD
    """
    code_upper = code.upper()
    logger.info(f"Getting currency: {code_upper}")

    result = await db.execute(select(Currency).where(Currency.code == code_upper))
    currency = result.scalar_one_or_none()

    if currency is None:
        logger.warning(f"Currency not found: {code_upper}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Currency {code_upper} not found",
        )

    return currency


@router.post("/", response_model=CurrencyResponse, status_code=status.HTTP_201_CREATED)
async def create_currency(
    currency_data: CurrencyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Currency:
    """Create a new currency.

    Args:
        currency_data: Currency creation data
        db: Database session

    Returns:
        Created currency

    Raises:
        HTTPException: 400 if currency code already exists

    Example:
        POST /api/v1/currencies
        {
            "code": "GBP",
            "name": "British Pound",
            "symbol": "£",
            "is_active": true
        }
    """
    code_upper = currency_data.code.upper()
    logger.info(f"Creating currency: {code_upper}")

    # Check if currency already exists
    result = await db.execute(select(Currency).where(Currency.code == code_upper))
    existing = result.scalar_one_or_none()

    if existing is not None:
        logger.warning(f"Currency already exists: {code_upper}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Currency {code_upper} already exists",
        )

    # Create currency
    currency = Currency(
        code=code_upper,
        name=currency_data.name,
        symbol=currency_data.symbol,
        is_active=currency_data.is_active,
    )

    db.add(currency)
    await db.commit()
    await db.refresh(currency)

    logger.info(f"Created currency: {code_upper}")
    return currency


@router.put("/{code}", response_model=CurrencyResponse)
async def update_currency(
    code: str,
    currency_data: CurrencyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Currency:
    """Update an existing currency.

    Args:
        code: Currency code to update
        currency_data: Currency update data
        db: Database session

    Returns:
        Updated currency

    Raises:
        HTTPException: 404 if currency not found

    Example:
        PUT /api/v1/currencies/USD
        {
            "name": "United States Dollar",
            "symbol": "$",
            "is_active": true
        }
    """
    code_upper = code.upper()
    logger.info(f"Updating currency: {code_upper}")

    result = await db.execute(select(Currency).where(Currency.code == code_upper))
    currency = result.scalar_one_or_none()

    if currency is None:
        logger.warning(f"Currency not found: {code_upper}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Currency {code_upper} not found",
        )

    # Update fields
    if currency_data.name is not None:
        currency.name = currency_data.name
    if currency_data.symbol is not None:
        currency.symbol = currency_data.symbol
    if currency_data.is_active is not None:
        currency.is_active = currency_data.is_active

    await db.commit()
    await db.refresh(currency)

    logger.info(f"Updated currency: {code_upper}")
    return currency


@router.get("/{code}/rates", response_model=CurrencyRatesResponse)
async def get_currency_rates(
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    rate_date: date = Query(default_factory=date.today, description="Date for exchange rates"),
) -> CurrencyRatesResponse:
    """Get exchange rates for a currency on a specific date.

    Args:
        code: Base currency code
        db: Database session
        rate_date: Date for rates (default: today)

    Returns:
        Exchange rates for all currencies relative to base currency

    Raises:
        HTTPException: 404 if currency not found or no rates available

    Example:
        GET /api/v1/currencies/USD/rates
        GET /api/v1/currencies/USD/rates?rate_date=2024-01-15
    """
    code_upper = code.upper()
    logger.info(f"Getting rates for {code_upper} on {rate_date}")

    # Get base currency
    result = await db.execute(select(Currency).where(Currency.code == code_upper))
    currency = result.scalar_one_or_none()

    if currency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Currency {code_upper} not found",
        )

    # Get all rates from this currency
    result = await db.execute(
        select(CurrencyRate, Currency)
        .join(Currency, CurrencyRate.to_currency_id == Currency.id)
        .where(CurrencyRate.from_currency_id == currency.id, CurrencyRate.date == rate_date)
    )

    rates_data = {}
    for rate, to_currency in result:
        rates_data[to_currency.code] = rate.rate

    if not rates_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rates found for {code_upper} on {rate_date}",
        )

    return CurrencyRatesResponse(
        base_currency=code_upper,
        date=rate_date,
        rates=rates_data,
        count=len(rates_data),
    )


@router.post("/sync-rates", response_model=SyncRatesResponse)
async def sync_rates(
    db: Annotated[AsyncSession, Depends(get_db)],
    base_currency: str = Query("USD", description="Base currency for sync"),
    sync_date: date = Query(default_factory=date.today, description="Date to sync rates for"),
) -> SyncRatesResponse:
    """Sync exchange rates from external API.

    Fetches current exchange rates from exchangerate-api.io and stores them
    in the database for the specified date.

    Args:
        db: Database session
        base_currency: Base currency code (default: "USD")
        sync_date: Date to sync rates for (default: today)

    Returns:
        Sync operation results

    Example:
        POST /api/v1/currencies/sync-rates
        POST /api/v1/currencies/sync-rates?base_currency=EUR
        POST /api/v1/currencies/sync-rates?base_currency=USD&sync_date=2024-01-15
    """
    base_upper = base_currency.upper()
    logger.info(f"Syncing rates for {base_upper} on {sync_date}")

    synced_count, failed_count = await sync_currency_rates(db, base_upper, sync_date)

    message = (
        f"Synced {synced_count} rates for {base_upper} on {sync_date} ({failed_count} failures)"
    )

    return SyncRatesResponse(
        base_currency=base_upper,
        synced_count=synced_count,
        failed_count=failed_count,
        date=sync_date,
        message=message,
    )
