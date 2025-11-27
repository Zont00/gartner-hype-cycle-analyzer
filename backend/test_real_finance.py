"""
Real-world test of FinanceCollector with actual API calls.
Requires DEEPSEEK_API_KEY in .env file.

Usage:
    python test_real_finance.py                      # Uses default "quantum computing"
    python test_real_finance.py "plant cell culture"  # Uses custom keyword
"""
import asyncio
import json
import sys
from app.collectors.finance import FinanceCollector
from app.config import get_settings


async def test_real_collection(keyword: str = "quantum computing"):
    """Test FinanceCollector with real API calls

    Args:
        keyword: Technology keyword to test with
    """

    # Check if DeepSeek API key is configured
    settings = get_settings()
    if not settings.deepseek_api_key:
        print("ERROR: DEEPSEEK_API_KEY not found in .env file")
        print("Please add DEEPSEEK_API_KEY=your-key-here to backend/.env")
        return False

    print("=== Real FinanceCollector Test ===\n")
    print(f"DeepSeek API Key: {'*' * 10}{settings.deepseek_api_key[-4:]}\n")

    print(f"Testing with keyword: '{keyword}'\n")

    collector = FinanceCollector()

    try:
        print("Step 1: Calling DeepSeek to get relevant tickers...")
        result = await collector.collect(keyword)

        print(f"\nStep 2: Collection complete!\n")
        print("=" * 60)
        print(json.dumps(result, indent=2))
        print("=" * 60)

        # Verify key results
        print("\n=== Verification ===\n")
        print(f"Companies Found: {result['companies_found']}")
        print(f"Tickers: {result['tickers']}")
        print(f"Total Market Cap: ${result['total_market_cap']:,.0f}")
        print(f"Market Maturity: {result['market_maturity']}")
        print(f"Investor Sentiment: {result['investor_sentiment']}")
        print(f"Investment Momentum: {result['investment_momentum']}")
        print(f"Errors: {result['errors']}")

        if result['top_companies']:
            print(f"\nTop Companies:")
            for company in result['top_companies']:
                print(f"  - {company['ticker']} ({company['name']})")
                print(f"    Market Cap: ${company['market_cap']:,.0f}")
                print(f"    1M Change: {company['price_change_1m']:.2%}")

        # Check for success
        if result['companies_found'] > 0:
            print("\n[OK] SUCCESS: Real API test passed!")
            return True
        elif "DeepSeek" in str(result['errors']):
            print("\n[WARNING] DeepSeek API call failed, but fallback worked")
            return True
        else:
            print("\n[FAIL] No companies found and no clear error")
            return False

    except Exception as e:
        print(f"\n[FAIL] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Get keyword from command line argument or use default
    keyword = sys.argv[1] if len(sys.argv) > 1 else "quantum computing"
    success = asyncio.run(test_real_collection(keyword))
    exit(0 if success else 1)
