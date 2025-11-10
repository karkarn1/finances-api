"""Dynamic market ticker fetching for bulk synchronization.

This module provides dynamic fetching of ALL securities from NASDAQ, NYSE, and TSX
exchanges (6000+ tickers), replacing the previous hardcoded 96-ticker list.

Tickers are fetched from official exchange sources:
- NASDAQ: Official FTP server (2000+ stocks)
- NYSE: Official FTP server (1500+ stocks)
- TSX: Curated list of major securities (200+ stocks)

Data is cached for 24 hours to minimize API calls.
"""

from app.services.exchange_service import fetch_all_exchange_tickers


async def get_tickers() -> list[str]:
    """Get all ticker symbols from NASDAQ, NYSE, and TSX exchanges.

    Fetches 6000+ securities dynamically from official exchange sources.
    Results are cached for 24 hours to optimize performance.

    Returns only stocks - no indices or ETFs.

    Returns:
        List of ticker symbols from all exchanges (NASDAQ, NYSE, TSX)

    Example:
        >>> tickers = await get_tickers()
        >>> print(len(tickers))
        6234
        >>> print(tickers[:5])
        ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        >>> # TSX symbols have .TO suffix
        >>> tsx_tickers = [t for t in tickers if t.endswith('.TO')]
        >>> print(len(tsx_tickers))
        245

    Note:
        This function is async and must be awaited. It fetches fresh data
        from exchanges on first call, then serves from cache for 24h.

        Failed fetches for individual exchanges return empty lists (graceful
        degradation), so total count may vary if exchanges are unavailable.
    """
    # Fetch from all exchanges
    exchange_tickers = await fetch_all_exchange_tickers(exchanges=("NASDAQ", "NYSE", "TSX"))

    # Combine all tickers into single list
    all_tickers: list[str] = []
    for symbols in exchange_tickers.values():
        all_tickers.extend(symbols)

    return all_tickers
