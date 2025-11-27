"""
Financial data collector using Yahoo Finance API via yfinance library.
Gathers market signals, stock performance, and investment trends for technology keywords.
Uses DeepSeek LLM to intelligently map keywords to relevant stock tickers.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import re
import httpx
import yfinance as yf

from app.collectors.base import BaseCollector
from app.config import get_settings


class FinanceCollector(BaseCollector):
    """Collects financial market signals from Yahoo Finance using LLM-based ticker discovery"""

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    TIMEOUT = 60.0  # Longer timeout for yfinance operations

    # Fallback ETFs for tech sector when no specific tickers found
    FALLBACK_ETFS = ["QQQ", "XLK"]

    def __init__(self):
        """Initialize collector with instance-level ticker cache"""
        # Instance-level cache prevents race conditions across concurrent requests
        self._ticker_cache: Dict[str, List[str]] = {}

    async def collect(self, keyword: str) -> Dict[str, Any]:
        """
        Collect Yahoo Finance market data for the given keyword.

        Uses DeepSeek LLM to identify relevant stock tickers, then queries
        Yahoo Finance for each ticker across multiple time periods
        (1 month, 6 months, 2 years) to analyze market performance,
        investment trends, and investor sentiment.

        Args:
            keyword: Technology keyword to analyze

        Returns:
            Dictionary containing:
                - source: Data source identifier
                - collected_at: ISO timestamp
                - keyword: Echo of search term
                - companies_found: Number of valid tickers
                - tickers: List of ticker symbols analyzed
                - total_market_cap: Sum of market caps
                - avg_price_change_1m, avg_price_change_6m, avg_price_change_2y: Price performance
                - avg_volume_1m, avg_volume_6m: Trading volume metrics
                - avg_volatility_1m, avg_volatility_6m: Volatility metrics
                - market_maturity: Maturity level ("emerging", "developing", "mature")
                - investor_sentiment: Sentiment indicator ("positive", "neutral", "negative")
                - investment_momentum: Growth pattern ("accelerating", "steady", "decelerating")
                - volume_trend: Volume direction ("increasing", "stable", "decreasing")
                - top_companies: Sample of companies with metrics
                - errors: List of non-fatal errors encountered
        """
        now = datetime.now()
        collected_at = now.isoformat()

        errors = []

        try:
            # Step 1: Get relevant tickers using DeepSeek LLM
            tickers = await self._get_relevant_tickers(keyword, errors)

            if not tickers:
                return self._error_response(keyword, collected_at, "No tickers found", errors)

            # Step 2: Fetch data for each ticker
            ticker_data = await self._fetch_all_tickers(tickers, errors)

            # Filter out failed tickers
            valid_ticker_data = [td for td in ticker_data if td is not None]

            if not valid_ticker_data:
                return self._error_response(keyword, collected_at, "All ticker fetches failed", errors)

            # Step 3: Aggregate metrics across all companies
            total_market_cap = sum(td["market_cap"] for td in valid_ticker_data)
            avg_market_cap = total_market_cap / len(valid_ticker_data) if valid_ticker_data else 0.0

            # Price changes
            avg_price_change_1m = sum(td["price_change_1m"] for td in valid_ticker_data) / len(valid_ticker_data)
            avg_price_change_6m = sum(td["price_change_6m"] for td in valid_ticker_data) / len(valid_ticker_data)
            avg_price_change_2y = sum(td["price_change_2y"] for td in valid_ticker_data) / len(valid_ticker_data)

            # Volume
            avg_volume_1m = sum(td["avg_volume_1m"] for td in valid_ticker_data) / len(valid_ticker_data)
            avg_volume_6m = sum(td["avg_volume_6m"] for td in valid_ticker_data) / len(valid_ticker_data)

            # Volatility
            avg_volatility_1m = sum(td["volatility_1m"] for td in valid_ticker_data) / len(valid_ticker_data)
            avg_volatility_6m = sum(td["volatility_6m"] for td in valid_ticker_data) / len(valid_ticker_data)

            # Calculate derived insights
            market_maturity = self._calculate_market_maturity(total_market_cap, avg_volatility_6m)
            investor_sentiment = self._calculate_investor_sentiment(avg_price_change_1m, avg_price_change_6m)
            investment_momentum = self._calculate_investment_momentum(
                avg_price_change_1m, avg_price_change_6m, avg_price_change_2y
            )
            volume_trend = self._calculate_volume_trend(avg_volume_1m, avg_volume_6m)

            # Prepare top companies for LLM context (sort by market cap)
            sorted_companies = sorted(valid_ticker_data, key=lambda x: x["market_cap"], reverse=True)
            top_companies = [
                {
                    "ticker": td["ticker"],
                    "name": td["name"],
                    "market_cap": td["market_cap"],
                    "price_change_1m": td["price_change_1m"],
                    "sector": td["sector"],
                    "industry": td["industry"]
                }
                for td in sorted_companies[:5]
            ]

            return {
                "source": "yahoo_finance",
                "collected_at": collected_at,
                "keyword": keyword,

                # Discovery metrics
                "companies_found": len(valid_ticker_data),
                "tickers": [td["ticker"] for td in valid_ticker_data],

                # Aggregate market metrics
                "total_market_cap": total_market_cap,
                "avg_market_cap": avg_market_cap,

                # Price performance by period
                "avg_price_change_1m": avg_price_change_1m,
                "avg_price_change_6m": avg_price_change_6m,
                "avg_price_change_2y": avg_price_change_2y,

                # Volume metrics
                "avg_volume_1m": avg_volume_1m,
                "avg_volume_6m": avg_volume_6m,
                "volume_trend": volume_trend,

                # Volatility metrics
                "avg_volatility_1m": avg_volatility_1m,
                "avg_volatility_6m": avg_volatility_6m,

                # Derived insights
                "market_maturity": market_maturity,
                "investor_sentiment": investor_sentiment,
                "investment_momentum": investment_momentum,

                # Top companies for LLM context
                "top_companies": top_companies,

                # Error tracking
                "errors": errors
            }

        except Exception as e:
            errors.append(f"Unexpected error in collect: {str(e)}")
            return self._error_response(keyword, collected_at, f"Collection failed: {str(e)}", errors)

    async def _get_relevant_tickers(self, keyword: str, errors: List[str]) -> List[str]:
        """
        Use DeepSeek LLM to identify relevant stock tickers for the keyword.

        Args:
            keyword: Technology keyword
            errors: List to append errors to

        Returns:
            List of ticker symbols (5-10 companies)
        """
        # Check cache first
        if keyword in self._ticker_cache:
            return self._ticker_cache[keyword]

        try:
            settings = get_settings()

            if not settings.deepseek_api_key:
                errors.append("DeepSeek API key not configured, using fallback ETFs")
                return self.FALLBACK_ETFS

            prompt = f"""List stock ticker symbols (5-10) of publicly traded companies most actively investing in or developing "{keyword}" technology.

Requirements:
- Only valid US stock market ticker symbols
- Companies where this technology is a significant part of their business
- Include both large cap and emerging players if available

Return ONLY a JSON array of ticker symbols, for example: ["IBM", "GOOGL", "NVDA"]
No explanations, just the JSON array."""

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.DEEPSEEK_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.deepseek_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3  # Lower temperature for more deterministic results
                    }
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()

                # Parse JSON array from response
                # Remove markdown code blocks if present
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                content = content.strip()

                tickers = json.loads(content)

                if not isinstance(tickers, list) or not tickers:
                    errors.append("DeepSeek returned invalid ticker format")
                    return self.FALLBACK_ETFS

                # Validate ticker format (US tickers are 1-5 uppercase letters)
                ticker_pattern = re.compile(r'^[A-Z]{1,5}$')
                validated_tickers = []
                for t in tickers:
                    if t:
                        ticker_str = str(t).upper().strip()
                        if ticker_pattern.match(ticker_str):
                            validated_tickers.append(ticker_str)
                        else:
                            errors.append(f"Invalid ticker format: {ticker_str}")

                if not validated_tickers:
                    errors.append("No valid tickers after validation")
                    return self.FALLBACK_ETFS

                # Cache the result
                self._ticker_cache[keyword] = validated_tickers

                return validated_tickers

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                errors.append("DeepSeek rate limited")
            elif e.response.status_code == 401:
                errors.append("DeepSeek authentication failed")
            else:
                errors.append(f"DeepSeek HTTP {e.response.status_code}")
            return self.FALLBACK_ETFS

        except httpx.TimeoutException:
            errors.append("DeepSeek request timeout")
            return self.FALLBACK_ETFS

        except json.JSONDecodeError:
            errors.append("Failed to parse DeepSeek response")
            return self.FALLBACK_ETFS

        except Exception as e:
            errors.append(f"DeepSeek error: {type(e).__name__}")
            return self.FALLBACK_ETFS

    async def _fetch_all_tickers(self, tickers: List[str], errors: List[str]) -> List[Optional[Dict[str, Any]]]:
        """
        Fetch data for all tickers in parallel using thread executor.

        Args:
            tickers: List of ticker symbols
            errors: List to collect errors into (thread-safe single-threaded collection)

        Returns:
            List of ticker data dictionaries (None for failed tickers)
        """
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=5)

        try:
            # Submit all ticker fetch tasks (no errors list passed - thread-safe)
            tasks = [
                loop.run_in_executor(executor, self._fetch_ticker_data_sync, ticker)
                for ticker in tickers
            ]

            # Wait for all to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect ticker data and errors in single-threaded context (thread-safe)
            ticker_data_list = []
            for result in results:
                if isinstance(result, Exception):
                    # Task raised an exception
                    ticker_data_list.append(None)
                elif isinstance(result, tuple) and len(result) == 2:
                    # Normal return: (data, local_errors)
                    data, local_errors = result
                    ticker_data_list.append(data)
                    errors.extend(local_errors)  # Thread-safe: single-threaded context
                else:
                    # Unexpected return format
                    ticker_data_list.append(None)

            return ticker_data_list
        finally:
            # Ensure executor shuts down cleanly even on errors
            executor.shutdown(wait=True, cancel_futures=True)

    def _fetch_ticker_data_sync(self, ticker: str) -> tuple[Optional[Dict[str, Any]], List[str]]:
        """
        Synchronous function to fetch data for a single ticker.
        Called via run_in_executor to maintain async compatibility.

        Args:
            ticker: Ticker symbol

        Returns:
            Tuple of (ticker data dictionary or None, list of errors)
        """
        local_errors = []

        try:
            ticker_obj = yf.Ticker(ticker)

            # Validate ticker exists by checking info
            info = ticker_obj.info
            if not info or "symbol" not in info:
                local_errors.append(f"Ticker {ticker} not found")
                return None, local_errors

            # Fetch historical data for different periods
            hist_1m = ticker_obj.history(period="1mo")
            hist_6m = ticker_obj.history(period="6mo")
            hist_2y = ticker_obj.history(period="2y")

            # Check if we have data
            if hist_1m.empty:
                local_errors.append(f"No data for {ticker}")
                return None, local_errors

            # Extract market cap (handle missing values)
            market_cap = info.get("marketCap", 0) or 0

            # Calculate price changes
            price_change_1m = self._calculate_price_change(hist_1m)
            price_change_6m = self._calculate_price_change(hist_6m)
            price_change_2y = self._calculate_price_change(hist_2y)

            # Calculate average volumes
            avg_volume_1m = hist_1m["Volume"].mean() if not hist_1m.empty else 0.0
            avg_volume_6m = hist_6m["Volume"].mean() if not hist_6m.empty else 0.0

            # Calculate volatility (annualized standard deviation of returns)
            volatility_1m = self._calculate_volatility(hist_1m)
            volatility_6m = self._calculate_volatility(hist_6m)

            ticker_data = {
                "ticker": ticker,
                "name": info.get("longName", ticker),
                "market_cap": float(market_cap),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "price_change_1m": price_change_1m,
                "price_change_6m": price_change_6m,
                "price_change_2y": price_change_2y,
                "avg_volume_1m": float(avg_volume_1m),
                "avg_volume_6m": float(avg_volume_6m),
                "volatility_1m": volatility_1m,
                "volatility_6m": volatility_6m
            }

            return ticker_data, local_errors

        except Exception as e:
            local_errors.append(f"{ticker}: {type(e).__name__}")
            return None, local_errors

    def _calculate_price_change(self, hist_df) -> float:
        """
        Calculate percentage price change from historical data.

        Args:
            hist_df: Pandas DataFrame with historical prices

        Returns:
            Percentage change (e.g., 0.15 for 15% increase)
        """
        if hist_df.empty or len(hist_df) < 2:
            return 0.0

        start_price = hist_df["Close"].iloc[0]
        end_price = hist_df["Close"].iloc[-1]

        if start_price == 0:
            return 0.0

        return float((end_price - start_price) / start_price)

    def _calculate_volatility(self, hist_df) -> float:
        """
        Calculate annualized volatility (standard deviation of returns).

        Args:
            hist_df: Pandas DataFrame with historical prices

        Returns:
            Annualized volatility as decimal (e.g., 0.25 for 25%)
        """
        if hist_df.empty or len(hist_df) < 2:
            return 0.0

        # Calculate daily returns
        returns = hist_df["Close"].pct_change().dropna()

        if returns.empty:
            return 0.0

        # Annualized volatility (252 trading days per year)
        daily_std = returns.std()
        annualized_vol = daily_std * (252 ** 0.5)

        return float(annualized_vol)

    def _calculate_market_maturity(self, total_market_cap: float, avg_volatility: float) -> str:
        """
        Calculate market maturity level based on market cap and volatility.

        High market cap + low volatility = mature
        Low market cap + high volatility = emerging

        Args:
            total_market_cap: Total market cap across all companies
            avg_volatility: Average annualized volatility

        Returns:
            "emerging", "developing", or "mature"
        """
        if total_market_cap > 100_000_000_000 and avg_volatility < 0.3:  # >$100B, <30% vol
            return "mature"
        elif total_market_cap < 10_000_000_000 or avg_volatility > 0.6:  # <$10B or >60% vol
            return "emerging"
        else:
            return "developing"

    def _calculate_investor_sentiment(self, price_change_1m: float, price_change_6m: float) -> str:
        """
        Calculate investor sentiment from recent price trends.

        Args:
            price_change_1m: 1-month price change
            price_change_6m: 6-month price change

        Returns:
            "positive", "neutral", or "negative"
        """
        # Weighted more toward recent performance
        weighted_change = (price_change_1m * 0.6) + (price_change_6m * 0.4)

        if weighted_change > 0.05:  # >5% positive
            return "positive"
        elif weighted_change < -0.05:  # >5% negative
            return "negative"
        else:
            return "neutral"

    def _calculate_investment_momentum(
        self,
        price_change_1m: float,
        price_change_6m: float,
        price_change_2y: float
    ) -> str:
        """
        Calculate investment momentum from period-over-period comparison.

        Args:
            price_change_1m: 1-month price change
            price_change_6m: 6-month price change
            price_change_2y: 2-year price change

        Returns:
            "accelerating", "steady", or "decelerating"
        """
        # Compare recent vs. historical growth
        if price_change_1m > price_change_6m and price_change_6m > price_change_2y / 4:
            return "accelerating"
        elif price_change_1m < price_change_6m / 2 or price_change_1m < 0 < price_change_6m:
            return "decelerating"
        else:
            return "steady"

    def _calculate_volume_trend(self, avg_volume_1m: float, avg_volume_6m: float) -> str:
        """
        Calculate volume trend from period comparison.

        Args:
            avg_volume_1m: Average 1-month volume
            avg_volume_6m: Average 6-month volume

        Returns:
            "increasing", "stable", or "decreasing"
        """
        if avg_volume_6m == 0:
            return "stable"

        volume_change = (avg_volume_1m - avg_volume_6m) / avg_volume_6m

        if volume_change > 0.15:  # >15% increase
            return "increasing"
        elif volume_change < -0.15:  # >15% decrease
            return "decreasing"
        else:
            return "stable"

    def _error_response(
        self,
        keyword: str,
        collected_at: str,
        error_msg: str,
        errors: List[str]
    ) -> Dict[str, Any]:
        """
        Return fallback response when collection fails.

        Args:
            keyword: Technology keyword
            collected_at: ISO timestamp
            error_msg: Main error message
            errors: List of error messages

        Returns:
            Valid response dictionary with zero/unknown values
        """
        return {
            "source": "yahoo_finance",
            "collected_at": collected_at,
            "keyword": keyword,

            # Discovery metrics
            "companies_found": 0,
            "tickers": [],

            # Aggregate market metrics
            "total_market_cap": 0.0,
            "avg_market_cap": 0.0,

            # Price performance by period
            "avg_price_change_1m": 0.0,
            "avg_price_change_6m": 0.0,
            "avg_price_change_2y": 0.0,

            # Volume metrics
            "avg_volume_1m": 0.0,
            "avg_volume_6m": 0.0,
            "volume_trend": "unknown",

            # Volatility metrics
            "avg_volatility_1m": 0.0,
            "avg_volatility_6m": 0.0,

            # Derived insights
            "market_maturity": "unknown",
            "investor_sentiment": "unknown",
            "investment_momentum": "unknown",

            # Top companies for LLM context
            "top_companies": [],

            # Error tracking
            "errors": errors + [error_msg]
        }
