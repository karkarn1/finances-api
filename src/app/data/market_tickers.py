"""Predefined lists of market tickers for bulk synchronization.

This module contains curated lists of major stock securities from NASDAQ,
NYSE, and TSX exchanges that are used for bulk sync operations.
"""

# NASDAQ stocks (Technology-heavy exchange)
NASDAQ_STOCKS = [
    # Technology
    "AAPL",  # Apple Inc.
    "MSFT",  # Microsoft Corporation
    "GOOGL",  # Alphabet Inc. Class A
    "GOOG",  # Alphabet Inc. Class C
    "AMZN",  # Amazon.com Inc.
    "NVDA",  # NVIDIA Corporation
    "META",  # Meta Platforms Inc.
    "TSLA",  # Tesla Inc.
    "AVGO",  # Broadcom Inc.
    "ORCL",  # Oracle Corporation
    "CSCO",  # Cisco Systems Inc.
    "ADBE",  # Adobe Inc.
    "CRM",  # Salesforce Inc.
    "INTC",  # Intel Corporation
    "AMD",  # Advanced Micro Devices Inc.
    "QCOM",  # QUALCOMM Incorporated
    "TXN",  # Texas Instruments Incorporated
    "IBM",  # International Business Machines
    "NFLX",  # Netflix Inc.
    # Consumer
    "COST",  # Costco Wholesale Corporation
    "SBUX",  # Starbucks Corporation
    # Telecom
    "TMUS",  # T-Mobile US Inc.
]

# NYSE stocks (Diverse exchange)
NYSE_STOCKS = [
    # Financial
    "BRK-B",  # Berkshire Hathaway Inc. Class B
    "JPM",  # JPMorgan Chase & Co.
    "V",  # Visa Inc.
    "MA",  # Mastercard Incorporated
    "BAC",  # Bank of America Corporation
    "WFC",  # Wells Fargo & Company
    "GS",  # The Goldman Sachs Group Inc.
    "MS",  # Morgan Stanley
    "AXP",  # American Express Company
    "BLK",  # BlackRock Inc.
    "C",  # Citigroup Inc.
    "SCHW",  # The Charles Schwab Corporation
    # Healthcare
    "UNH",  # UnitedHealth Group Incorporated
    "JNJ",  # Johnson & Johnson
    "LLY",  # Eli Lilly and Company
    "PFE",  # Pfizer Inc.
    "ABBV",  # AbbVie Inc.
    "TMO",  # Thermo Fisher Scientific Inc.
    "MRK",  # Merck & Co. Inc.
    "ABT",  # Abbott Laboratories
    "DHR",  # Danaher Corporation
    "BMY",  # Bristol-Myers Squibb Company
    "AMGN",  # Amgen Inc.
    "CVS",  # CVS Health Corporation
    # Consumer
    "WMT",  # Walmart Inc.
    "HD",  # The Home Depot Inc.
    "PG",  # The Procter & Gamble Company
    "KO",  # The Coca-Cola Company
    "PEP",  # PepsiCo Inc.
    "MCD",  # McDonald's Corporation
    "NKE",  # NIKE Inc.
    "DIS",  # The Walt Disney Company
    # Energy
    "XOM",  # Exxon Mobil Corporation
    "CVX",  # Chevron Corporation
    "COP",  # ConocoPhillips
    "SLB",  # Schlumberger Limited
    # Industrial
    "BA",  # The Boeing Company
    "CAT",  # Caterpillar Inc.
    "GE",  # General Electric Company
    "HON",  # Honeywell International Inc.
    "UPS",  # United Parcel Service Inc.
    "LMT",  # Lockheed Martin Corporation
    "RTX",  # Raytheon Technologies Corporation
    # Telecom
    "T",  # AT&T Inc.
    "VZ",  # Verizon Communications Inc.
]

# TSX stocks (Toronto Stock Exchange)
TSX_STOCKS = [
    # Financial
    "RY.TO",  # Royal Bank of Canada
    "TD.TO",  # The Toronto-Dominion Bank
    "BNS.TO",  # The Bank of Nova Scotia
    "BMO.TO",  # Bank of Montreal
    "CM.TO",  # Canadian Imperial Bank of Commerce
    "MFC.TO",  # Manulife Financial Corporation
    "SLF.TO",  # Sun Life Financial Inc.
    "GWO.TO",  # Great-West Lifeco Inc.
    # Energy
    "CNQ.TO",  # Canadian Natural Resources Limited
    "SU.TO",  # Suncor Energy Inc.
    "ENB.TO",  # Enbridge Inc.
    "TRP.TO",  # TC Energy Corporation
    "IMO.TO",  # Imperial Oil Limited
    "CVE.TO",  # Cenovus Energy Inc.
    # Telecom
    "BCE.TO",  # BCE Inc.
    "T.TO",  # TELUS Corporation
    "RCI-B.TO",  # Rogers Communications Inc.
    # Materials
    "ABX.TO",  # Barrick Gold Corporation
    "NTR.TO",  # Nutrien Ltd.
    "FM.TO",  # First Quantum Minerals Ltd.
    # Industrials
    "CNR.TO",  # Canadian National Railway Company
    "CP.TO",  # Canadian Pacific Kansas City Limited
    "WCN.TO",  # Waste Connections Inc.
    # Consumer
    "L.TO",  # Loblaw Companies Limited
    "ATD.TO",  # Alimentation Couche-Tard Inc.
    "QSR.TO",  # Restaurant Brands International Inc.
    # Technology
    "SHOP.TO",  # Shopify Inc.
    # Utilities
    "FTS.TO",  # Fortis Inc.
    "EMA.TO",  # Emera Incorporated
]

# Combined list of all stocks from NASDAQ, NYSE, and TSX
ALL_STOCKS = NASDAQ_STOCKS + NYSE_STOCKS + TSX_STOCKS


def get_tickers() -> list[str]:
    """
    Get list of all stock tickers from NASDAQ, NYSE, and TSX exchanges.

    Returns only stocks - no indices or ETFs.

    Returns:
        List of ticker symbols

    Example:
        >>> get_tickers()
        ['AAPL', 'MSFT', 'GOOGL', ..., 'RY.TO', 'TD.TO', ...]
    """
    return ALL_STOCKS
