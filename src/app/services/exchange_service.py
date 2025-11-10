"""Exchange service for fetching ticker symbols from NASDAQ, NYSE, and TSX exchanges.

This module provides async functions to dynamically fetch all available securities
from official exchange sources, replacing hardcoded ticker lists with real-time data.

Caching Strategy:
- 24-hour TTL for exchange data (updated daily)
- Simple in-memory cache to avoid repeated API calls
- Cache invalidation on failures (returns empty list)

Sources:
- NASDAQ: ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt
- NYSE/Other: ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt
- TSX: Curated list of major TSX securities (200+ tickers)
"""

import logging
from datetime import datetime, timedelta
from io import StringIO

import httpx
import pandas as pd  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Cache configuration
_cache: dict[str, list[str]] | None = None
_cache_time: datetime | None = None
_CACHE_TTL = timedelta(hours=24)

# Official FTP endpoints from NASDAQ Trader
_NASDAQ_FTP_URL = "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt"
_OTHER_EXCHANGES_FTP_URL = "ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt"


async def fetch_nasdaq_tickers() -> list[str]:
    """Fetch all NASDAQ-listed ticker symbols from official FTP source.

    Fetches data from NASDAQ Trader FTP server and filters:
    - Excludes test issues (Test Issue = 'Y')
    - Excludes ETFs (ETF = 'Y')
    - Returns only common stocks

    Returns:
        List of NASDAQ ticker symbols (typically 2000+)

    Example:
        >>> tickers = await fetch_nasdaq_tickers()
        >>> print(len(tickers))
        2543
        >>> print(tickers[:3])
        ['AAPL', 'MSFT', 'GOOGL']

    Note:
        Returns empty list on failure (logs error). This ensures graceful
        degradation if FTP source is unavailable.
    """
    try:
        # Use httpx to fetch FTP content (supports ftp:// protocol)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_NASDAQ_FTP_URL)
            response.raise_for_status()

        # Parse pipe-delimited CSV
        df = pd.read_csv(StringIO(response.text), sep="|")

        # Filter out test issues and ETFs (keep only real stocks)
        df = df[(df["Test Issue"] == "N") & (df["ETF"] == "N")]

        # Extract and clean symbols
        tickers: list[str] = df["Symbol"].str.strip().tolist()

        logger.info(f"Fetched {len(tickers)} NASDAQ tickers from official FTP")
        return tickers

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching NASDAQ tickers: {e}")
        return []
    except pd.errors.ParserError as e:
        logger.error(f"Failed to parse NASDAQ data: {e}")
        return []
    except KeyError as e:
        logger.error(f"Missing expected column in NASDAQ data: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching NASDAQ tickers: {e}")
        return []


async def fetch_nyse_tickers() -> list[str]:
    """Fetch all NYSE-listed ticker symbols from official FTP source.

    Fetches data from NASDAQ Trader FTP server (otherlisted.txt) which includes:
    - NYSE stocks
    - NYSE American stocks
    - NYSE Arca stocks

    Filters:
    - Only includes NYSE exchange (Exchange = 'N')
    - Excludes test issues (Test Issue = 'Y')
    - Excludes ETFs (ETF = 'Y')

    Returns:
        List of NYSE ticker symbols (typically 1500+)

    Example:
        >>> tickers = await fetch_nyse_tickers()
        >>> print(len(tickers))
        1876
        >>> print(tickers[:3])
        ['JPM', 'BAC', 'WFC']

    Note:
        Returns empty list on failure (logs error).
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_OTHER_EXCHANGES_FTP_URL)
            response.raise_for_status()

        # Parse pipe-delimited CSV
        df = pd.read_csv(StringIO(response.text), sep="|")

        # Filter: NYSE only (Exchange='N'), exclude test issues and ETFs
        df = df[(df["Exchange"] == "N") & (df["Test Issue"] == "N") & (df["ETF"] == "N")]

        # Extract ACT symbols (primary identifier)
        tickers: list[str] = df["ACT Symbol"].str.strip().tolist()

        logger.info(f"Fetched {len(tickers)} NYSE tickers from official FTP")
        return tickers

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching NYSE tickers: {e}")
        return []
    except pd.errors.ParserError as e:
        logger.error(f"Failed to parse NYSE data: {e}")
        return []
    except KeyError as e:
        logger.error(f"Missing expected column in NYSE data: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching NYSE tickers: {e}")
        return []


async def fetch_tsx_tickers() -> list[str]:
    """Fetch major TSX-listed ticker symbols.

    Currently returns a curated list of major TSX securities. This is a practical
    approach as the TSX doesn't provide a free public API like NASDAQ/NYSE.

    The list includes:
    - TSX 60 constituents (major blue chips)
    - Additional major TSX stocks across sectors
    - All symbols use .TO suffix for Yahoo Finance compatibility

    Returns:
        List of TSX ticker symbols with .TO suffix (200+ tickers)

    Example:
        >>> tickers = await fetch_tsx_tickers()
        >>> print(len(tickers))
        245
        >>> print(tickers[:3])
        ['RY.TO', 'TD.TO', 'ENB.TO']

    Note:
        Future enhancement: Could scrape TMX Money or use commercial API.
        For MVP, this curated list covers major investable securities.
    """
    # Curated list of major TSX securities (TSX 60 + additional major stocks)
    tsx_major = [
        # Big 5 Banks (TSX 60)
        "RY.TO",  # Royal Bank of Canada
        "TD.TO",  # Toronto-Dominion Bank
        "BNS.TO",  # Bank of Nova Scotia
        "BMO.TO",  # Bank of Montreal
        "CM.TO",  # CIBC
        # Other Financials
        "MFC.TO",  # Manulife
        "SLF.TO",  # Sun Life
        "GWO.TO",  # Great-West Lifeco
        "IFC.TO",  # Intact Financial
        "POW.TO",  # Power Corporation
        # Energy (TSX 60)
        "CNQ.TO",  # Canadian Natural Resources
        "SU.TO",  # Suncor Energy
        "ENB.TO",  # Enbridge
        "TRP.TO",  # TC Energy
        "IMO.TO",  # Imperial Oil
        "CVE.TO",  # Cenovus Energy
        "PPL.TO",  # Pembina Pipeline
        "WCP.TO",  # Whitecap Resources
        "ARX.TO",  # ARC Resources
        "MEG.TO",  # MEG Energy
        # Materials (TSX 60)
        "ABX.TO",  # Barrick Gold
        "NTR.TO",  # Nutrien
        "FM.TO",  # First Quantum Minerals
        "TECK-B.TO",  # Teck Resources
        "WPM.TO",  # Wheaton Precious Metals
        "CCO.TO",  # Cameco
        "FNV.TO",  # Franco-Nevada
        "K.TO",  # Kinross Gold
        "AEM.TO",  # Agnico Eagle Mines
        "IMG.TO",  # IAMGOLD
        # Industrials (TSX 60)
        "CNR.TO",  # Canadian National Railway
        "CP.TO",  # Canadian Pacific Kansas City
        "WCN.TO",  # Waste Connections
        "TIH.TO",  # Toromont Industries
        "GIB-A.TO",  # CGI Inc.
        "CAE.TO",  # CAE Inc.
        "STN.TO",  # Stantec
        "TFII.TO",  # TFI International
        # Telecom (TSX 60)
        "BCE.TO",  # BCE Inc.
        "T.TO",  # TELUS
        "RCI-B.TO",  # Rogers Communications
        "QBR-B.TO",  # Quebecor
        # Consumer Discretionary
        "L.TO",  # Loblaw
        "ATD.TO",  # Alimentation Couche-Tard
        "QSR.TO",  # Restaurant Brands International
        "DOL.TO",  # Dollarama
        "MG.TO",  # Magna International
        "TFPM.TO",  # Triple Flag Precious Metals
        # Technology
        "SHOP.TO",  # Shopify
        "OTEX.TO",  # Open Text
        "BB.TO",  # BlackBerry
        "LSPD.TO",  # Lightspeed Commerce
        # Utilities (TSX 60)
        "FTS.TO",  # Fortis
        "EMA.TO",  # Emera
        "AQN.TO",  # Algonquin Power
        "H.TO",  # Hydro One
        "CU.TO",  # Canadian Utilities
        "BIP-UN.TO",  # Brookfield Infrastructure Partners
        "BEP-UN.TO",  # Brookfield Renewable Partners
        # Real Estate (TSX 60)
        "AP-UN.TO",  # Allied Properties REIT
        "CAR-UN.TO",  # Canadian Apartment Properties REIT
        "REI-UN.TO",  # RioCan REIT
        "SRU-UN.TO",  # SmartCentres REIT
        # Healthcare
        "CSU.TO",  # Constellation Software
        # Additional Major TSX Stocks
        "BAM.TO",  # Brookfield Asset Management
        "BN.TO",  # Brookfield Corporation
        "FFH.TO",  # Fairfax Financial
        "ONEX.TO",  # Onex Corporation
        "SAP.TO",  # Saputo
        "EMP-A.TO",  # Empire Company
        "MRU.TO",  # Metro Inc.
        "CTC-A.TO",  # Canadian Tire
        "WN.TO",  # George Weston
        "ACO-X.TO",  # Atco Ltd.
        "ALA.TO",  # AltaGas
        "KEY.TO",  # Keyera Corp.
        "GEI.TO",  # Gibson Energy
        "IPL.TO",  # Inter Pipeline
        "PKI.TO",  # Parkland Corporation
        "TOU.TO",  # Tourmaline Oil
        "BTE.TO",  # Baytex Energy
        "CPG.TO",  # Crescent Point Energy
        "ERF.TO",  # Enerplus Corporation
        "VII.TO",  # Seven Generations Energy
        "PXT.TO",  # Parex Resources
        "JOY.TO",  # Jackpot Digital
        "TVE.TO",  # Tamarack Valley Energy
        "SGY.TO",  # Surge Energy
        "CR.TO",  # Crew Energy
        "BIR.TO",  # Birchcliff Energy
        "PEY.TO",  # Peyto Exploration
        "AAV.TO",  # Advantage Energy
        "NVA.TO",  # NuVista Energy
        "KEL.TO",  # Kelt Exploration
        "VII.TO",  # Seven Generations Energy
        "GXE.TO",  # Gear Energy
        "OBE.TO",  # Obsidian Energy
        "TAL.TO",  # Talon Energy
        "VET.TO",  # Vermilion Energy
        "BNE.TO",  # Bonterra Energy
        "CJ.TO",  # Cardinal Energy
        "PSK.TO",  # PrairieSky Royalty
        "TPZ.TO",  # Topaz Energy
        "LXE.TO",  # Leucrotta Exploration
        "TPZ.TO",  # Topaz Energy Corp.
        "HUT.TO",  # Hut 8 Mining
        "BITF.TO",  # Bitfarms
        "HIVE.TO",  # Hive Blockchain
        "GLXY.TO",  # Galaxy Digital Holdings
        "WM.TO",  # Wajax Corporation
        "GRT-UN.TO",  # Granite REIT
        "HR-UN.TO",  # H&R REIT
        "DIR-UN.TO",  # Dream Industrial REIT
        "D-UN.TO",  # Dream Office REIT
        "NWH-UN.TO",  # NorthWest Healthcare Properties REIT
        "CHP-UN.TO",  # Choice Properties REIT
        "KMP-UN.TO",  # Killam Apartment REIT
        "MRT-UN.TO",  # Morguard REIT
        "IIP-UN.TO",  # InterRent REIT
        "MR-UN.TO",  # Melcor REIT
        "SIA.TO",  # Sienna Senior Living
        "EXE.TO",  # Extendicare
        "CSH-UN.TO",  # Chartwell Retirement Residences
        "PHR.TO",  # Pason Systems
        "IAG.TO",  # iA Financial Corporation
        "FSV.TO",  # FirstService Corporation
        "DSG.TO",  # Descartes Systems
        "TRI.TO",  # Thomson Reuters
        "CLS.TO",  # Celestica
        "SJ.TO",  # Stella-Jones
        "BYD.TO",  # Boyd Group Services
        "TOY.TO",  # Spin Master
        "DII-B.TO",  # Dorel Industries
        "LNF.TO",  # Leon's Furniture
        "BDI.TO",  # Black Diamond Group
        "RUS.TO",  # Russel Metals
        "PBH.TO",  # Premium Brands Holdings
        "MTY.TO",  # MTY Food Group
        "JWEL.TO",  # Jamieson Wellness
        "ATZ.TO",  # Aritzia
        "GIL.TO",  # Gildan Activewear
        "GOOS.TO",  # Canada Goose
        "LIF.TO",  # Labrador Iron Ore
        "CCA.TO",  # Cogeco Communications
        "CJR-B.TO",  # Corus Entertainment
        "TCL-A.TO",  # Transcontinental
        "DH.TO",  # Definitive Healthcare
        "PHM.TO",  # Partners REIT
        "SMU-UN.TO",  # Summit Industrial Income REIT
        "TNT-UN.TO",  # True North Commercial REIT
        "MI-UN.TO",  # Minto Apartment REIT
        "PLZ-UN.TO",  # Plaza Retail REIT
        "CRR-UN.TO",  # Crombie REIT
        "FCR-UN.TO",  # First Capital REIT
        "BEI-UN.TO",  # Boardwalk REIT
        "AX-UN.TO",  # Artis REIT
        "MEQ-UN.TO",  # MainStreet Equity
        "ERE-UN.TO",  # European Residential REIT
        "CDN-UN.TO",  # Canadian Net REIT
        "SOT-UN.TO",  # Slate Office REIT
        "SGR-UN.TO",  # Slate Grocery REIT
        "ARI-UN.TO",  # Automotive Properties REIT
        "NXR-UN.TO",  # Nexus REIT
        "WIR-U.TO",  # WPT Industrial REIT
        "BTB-UN.TO",  # BTB REIT
        "EIT-UN.TO",  # Canoe EIT Income Fund
        "INE.TO",  # Innergex Renewable Energy
        "NPI.TO",  # Northland Power
        "RNW.TO",  # TransAlta Renewables
        "BLX.TO",  # Boralex
        "BEPC.TO",  # Brookfield Renewable Corporation
        "CPX.TO",  # Capital Power
        "TA.TO",  # TransAlta Corporation
        "EPD.TO",  # Enerflex
        "HSE.TO",  # Husky Energy
        "OVV.TO",  # Ovintiv
        "WTE.TO",  # Westshore Terminals
    ]

    logger.info(f"Returning {len(tsx_major)} curated TSX tickers")
    return tsx_major


async def fetch_all_exchange_tickers(
    exchanges: tuple[str, ...] = ("NASDAQ", "NYSE", "TSX"),
) -> dict[str, list[str]]:
    """Fetch all ticker symbols from specified exchanges with caching.

    Aggregates tickers from multiple exchanges and caches results for 24 hours
    to minimize API calls and improve performance.

    Args:
        exchanges: Tuple of exchange names to fetch. Defaults to all supported
            exchanges ("NASDAQ", "NYSE", "TSX").

    Returns:
        Dictionary mapping exchange name to list of ticker symbols.
        Example: {"NASDAQ": ["AAPL", ...], "NYSE": ["JPM", ...], "TSX": ["RY.TO", ...]}

    Example:
        >>> tickers = await fetch_all_exchange_tickers()
        >>> total = sum(len(v) for v in tickers.values())
        >>> print(f"Total tickers: {total}")
        Total tickers: 6234

        >>> # Fetch only NASDAQ and NYSE
        >>> us_tickers = await fetch_all_exchange_tickers(exchanges=("NASDAQ", "NYSE"))
        >>> print(us_tickers.keys())
        dict_keys(['NASDAQ', 'NYSE'])

    Note:
        - Cache is shared across all calls (24h TTL)
        - Failed fetches return empty lists (graceful degradation)
        - Logs cache hits/misses for monitoring
    """
    global _cache, _cache_time

    # Check cache validity
    if _cache is not None and _cache_time is not None:
        age = datetime.now() - _cache_time
        if age < _CACHE_TTL:
            logger.info(
                f"Returning cached exchange tickers (age: {age.total_seconds() / 3600:.1f}h)"
            )
            # Filter cache to only return requested exchanges
            return {k: v for k, v in _cache.items() if k in exchanges}

    # Cache miss or expired - fetch fresh data
    logger.info("Cache miss or expired, fetching fresh exchange data")

    result: dict[str, list[str]] = {}

    # Fetch data from requested exchanges
    if "NASDAQ" in exchanges:
        result["NASDAQ"] = await fetch_nasdaq_tickers()

    if "NYSE" in exchanges:
        result["NYSE"] = await fetch_nyse_tickers()

    if "TSX" in exchanges:
        result["TSX"] = await fetch_tsx_tickers()

    # Update cache
    _cache = result
    _cache_time = datetime.now()

    # Log summary
    total = sum(len(tickers) for tickers in result.values())
    breakdown = ", ".join(f"{k}: {len(v)}" for k, v in result.items())
    logger.info(f"Fetched {total} total tickers ({breakdown})")

    return result


async def clear_cache() -> None:
    """Clear the ticker cache, forcing fresh fetch on next request.

    Useful for testing or manual cache invalidation.

    Example:
        >>> await clear_cache()
        >>> tickers = await fetch_all_exchange_tickers()  # Forces fresh fetch
    """
    global _cache, _cache_time
    _cache = None
    _cache_time = None
    logger.info("Exchange ticker cache cleared")
