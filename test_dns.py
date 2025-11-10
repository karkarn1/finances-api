#!/usr/bin/env python3
"""Test DNS resolution and API connectivity."""

import asyncio
import httpx


async def test_api():
    """Test connection to exchange rate API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "https://api.exchangerate-api.io/v4/latest/USD"
            print(f"Testing URL: {url}")
            response = await client.get(url)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response keys: {list(data.keys())}")
                if "rates" in data:
                    print(f"Number of rates: {len(data['rates'])}")
                    print(f"Sample rates: EUR={data['rates'].get('EUR')}, CAD={data['rates'].get('CAD')}")
                    print("✅ SUCCESS: API is reachable and returning data")
                else:
                    print("❌ FAIL: API response missing 'rates' field")
            else:
                print(f"❌ FAIL: HTTP {response.status_code}")
    except httpx.RequestError as e:
        print(f"❌ FAIL: Request error: {e}")
    except Exception as e:
        print(f"❌ FAIL: Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(test_api())
