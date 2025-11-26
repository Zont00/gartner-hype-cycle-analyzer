"""
Social media collector using Hacker News Algolia API.
Gathers discussion volume, engagement metrics, and trends for technology keywords.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List
import math
import httpx

from app.collectors.base import BaseCollector


class SocialCollector(BaseCollector):
    """Collects social media signals from Hacker News via Algolia API"""

    API_URL = "https://hn.algolia.com/api/v1/search"
    TIMEOUT = 30.0

    async def collect(self, keyword: str) -> Dict[str, Any]:
        """
        Collect Hacker News data for the given keyword.

        Queries the Hacker News Algolia API across three time periods
        (30 days, 6 months, 1 year) to analyze discussion volume,
        engagement metrics, and trends.

        Args:
            keyword: Technology keyword to analyze

        Returns:
            Dictionary containing:
                - source: Data source identifier
                - collected_at: ISO timestamp
                - keyword: Echo of search term
                - mentions_30d, mentions_6m, mentions_1y: Story counts by period
                - avg_points_30d, avg_comments_30d: Recent engagement metrics
                - sentiment: Normalized sentiment score (-1.0 to 1.0)
                - recency: Activity level ("high", "medium", "low")
                - growth_trend: Trend direction ("increasing", "stable", "decreasing")
                - momentum: Growth acceleration ("accelerating", "steady", "decelerating")
                - top_stories: Sample of recent stories
                - errors: List of non-fatal errors encountered
        """
        now = datetime.now()
        collected_at = now.isoformat()

        # Calculate time period boundaries (Unix timestamps)
        thirty_days_ago = int((now - timedelta(days=30)).timestamp())
        six_months_ago = int((now - timedelta(days=180)).timestamp())
        one_year_ago = int((now - timedelta(days=365)).timestamp())

        errors = []

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                # Fetch data for each time period
                data_30d = await self._fetch_period(
                    client, keyword, thirty_days_ago, None, errors
                )
                data_6m = await self._fetch_period(
                    client, keyword, six_months_ago, thirty_days_ago, errors
                )
                data_1y = await self._fetch_period(
                    client, keyword, one_year_ago, six_months_ago, errors
                )

                # If all requests failed, return error state
                if all(d is None for d in [data_30d, data_6m, data_1y]):
                    return self._error_response(keyword, collected_at, "All API requests failed", errors)

                # Extract metrics from each period
                mentions_30d = data_30d["nbHits"] if data_30d else 0
                mentions_6m = data_6m["nbHits"] if data_6m else 0
                mentions_1y = data_1y["nbHits"] if data_1y else 0

                # Calculate engagement metrics for 30-day period
                avg_points_30d = 0.0
                avg_comments_30d = 0.0
                top_stories = []

                if data_30d and data_30d["hits"]:
                    hits = data_30d["hits"]
                    total_points = sum(h.get("points", 0) or 0 for h in hits)
                    total_comments = sum(h.get("num_comments", 0) or 0 for h in hits)
                    avg_points_30d = total_points / len(hits) if hits else 0.0
                    avg_comments_30d = total_comments / len(hits) if hits else 0.0

                    # Extract top stories for LLM context
                    for hit in hits[:5]:
                        age_days = (now.timestamp() - (hit.get("created_at_i") or now.timestamp())) / 86400
                        top_stories.append({
                            "title": hit.get("title", ""),
                            "points": hit.get("points", 0) or 0,
                            "comments": hit.get("num_comments", 0) or 0,
                            "age_days": int(age_days)
                        })

                # Calculate engagement for 6-month period
                avg_points_6m = 0.0
                avg_comments_6m = 0.0

                if data_6m and data_6m["hits"]:
                    hits = data_6m["hits"]
                    total_points = sum(h.get("points", 0) or 0 for h in hits)
                    total_comments = sum(h.get("num_comments", 0) or 0 for h in hits)
                    avg_points_6m = total_points / len(hits) if hits else 0.0
                    avg_comments_6m = total_comments / len(hits) if hits else 0.0

                # Calculate derived insights
                sentiment = self._calculate_sentiment(avg_points_30d)
                recency = self._calculate_recency(mentions_30d, mentions_6m, mentions_1y)
                growth_trend = self._calculate_growth_trend(mentions_30d, mentions_6m, mentions_1y)
                momentum = self._calculate_momentum(mentions_30d, mentions_6m, mentions_1y)

                return {
                    "source": "hacker_news",
                    "collected_at": collected_at,
                    "keyword": keyword,

                    # Mention counts by time period
                    "mentions_30d": mentions_30d,
                    "mentions_6m": mentions_6m,
                    "mentions_1y": mentions_1y,
                    "mentions_total": mentions_30d + mentions_6m + mentions_1y,

                    # Engagement metrics
                    "avg_points_30d": round(avg_points_30d, 2),
                    "avg_comments_30d": round(avg_comments_30d, 2),
                    "avg_points_6m": round(avg_points_6m, 2),
                    "avg_comments_6m": round(avg_comments_6m, 2),

                    # Derived insights
                    "sentiment": round(sentiment, 3),
                    "recency": recency,
                    "growth_trend": growth_trend,
                    "momentum": momentum,

                    # Context for LLM
                    "top_stories": top_stories,

                    # Error tracking
                    "errors": errors
                }

        except Exception as e:
            return self._error_response(
                keyword,
                collected_at,
                f"Unexpected error: {str(e)}",
                errors
            )

    async def _fetch_period(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        start_ts: int,
        end_ts: int | None,
        errors: List[str]
    ) -> Dict[str, Any] | None:
        """
        Fetch Hacker News data for a specific time period.

        Args:
            client: Async HTTP client
            keyword: Search term
            start_ts: Start timestamp (Unix)
            end_ts: End timestamp (Unix), or None for "until now"
            errors: List to append error messages to

        Returns:
            API response dict or None if request failed
        """
        try:
            # Build numeric filter for time range
            if end_ts is None:
                numeric_filter = f"created_at_i>{start_ts}"
            else:
                numeric_filter = f"created_at_i>{start_ts},created_at_i<{end_ts}"

            response = await client.get(
                self.API_URL,
                params={
                    "query": keyword,
                    "tags": "story",
                    "numericFilters": numeric_filter,
                    "hitsPerPage": 20
                }
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                errors.append("Rate limited")
            else:
                errors.append(f"HTTP {e.response.status_code}")
            return None

        except httpx.TimeoutException:
            errors.append("Request timeout")
            return None

        except httpx.RequestError as e:
            errors.append(f"Network error: {type(e).__name__}")
            return None

        except Exception as e:
            errors.append(f"Unexpected error: {str(e)}")
            return None

    def _calculate_sentiment(self, avg_points: float) -> float:
        """
        Calculate sentiment score from engagement metrics.

        Uses hyperbolic tangent to normalize point scores to [-1, 1] range.
        Higher points indicate more positive community reception.

        Args:
            avg_points: Average story points

        Returns:
            Sentiment score from -1.0 (negative) to 1.0 (positive)
        """
        # Normalize using tanh: 50 points = neutral baseline
        # Result ranges from -1 to 1
        return math.tanh((avg_points - 50) / 100)

    def _calculate_recency(self, mentions_30d: int, mentions_6m: int, mentions_1y: int) -> str:
        """
        Calculate recency level based on mention distribution.

        Args:
            mentions_30d: Mentions in last 30 days
            mentions_6m: Mentions in 6-month period
            mentions_1y: Mentions in 1-year period

        Returns:
            "high", "medium", or "low"
        """
        total = mentions_30d + mentions_6m + mentions_1y
        if total == 0:
            return "low"

        # Calculate what percentage of total mentions are in last 30 days
        recent_ratio = mentions_30d / total

        if recent_ratio > 0.5:  # Over 50% in last month
            return "high"
        elif recent_ratio > 0.2:  # 20-50% in last month
            return "medium"
        else:
            return "low"

    def _calculate_growth_trend(self, mentions_30d: int, mentions_6m: int, mentions_1y: int) -> str:
        """
        Calculate growth trend by comparing recent vs historical mentions.

        Args:
            mentions_30d: Mentions in last 30 days
            mentions_6m: Mentions in 6-month period (excluding last 30d)
            mentions_1y: Mentions in 1-year period (excluding last 6m)

        Returns:
            "increasing", "stable", or "decreasing"
        """
        # Calculate average mentions per 30-day period for historical data
        # 6m period = ~5 months, 1y period = ~6 months
        historical_periods = mentions_6m + mentions_1y
        historical_months = 11  # 5 months + 6 months

        if historical_months == 0:
            # No historical data, can't determine trend
            return "stable" if mentions_30d > 0 else "unknown"

        avg_per_month = historical_periods / historical_months

        # Compare current 30-day period to historical average
        threshold = 0.3  # 30% difference threshold

        if mentions_30d > avg_per_month * (1 + threshold):
            return "increasing"
        elif mentions_30d < avg_per_month * (1 - threshold):
            return "decreasing"
        else:
            return "stable"

    def _calculate_momentum(self, mentions_30d: int, mentions_6m: int, mentions_1y: int) -> str:
        """
        Calculate momentum by comparing growth rates across periods.

        Args:
            mentions_30d: Mentions in last 30 days
            mentions_6m: Mentions in 6-month period
            mentions_1y: Mentions in 1-year period

        Returns:
            "accelerating", "steady", or "decelerating"
        """
        if mentions_30d == 0 and mentions_6m == 0:
            return "steady"

        # Compare 30d to 6m ratio vs 6m to 1y ratio
        # If recent growth is faster than historical, momentum is accelerating

        recent_avg = mentions_30d  # Per month (already 30 days)
        mid_avg = mentions_6m / 5 if mentions_6m > 0 else 0  # Per month (~5 months)
        old_avg = mentions_1y / 6 if mentions_1y > 0 else 0  # Per month (~6 months)

        # Growth from old to mid period
        if old_avg > 0:
            mid_growth = (mid_avg - old_avg) / old_avg
        else:
            mid_growth = 1.0 if mid_avg > 0 else 0.0

        # Growth from mid to recent period
        if mid_avg > 0:
            recent_growth = (recent_avg - mid_avg) / mid_avg
        else:
            recent_growth = 1.0 if recent_avg > 0 else 0.0

        # Compare growth rates
        if recent_growth > mid_growth * 1.2:  # 20% faster growth
            return "accelerating"
        elif recent_growth < mid_growth * 0.8:  # 20% slower growth
            return "decelerating"
        else:
            return "steady"

    def _error_response(
        self,
        keyword: str,
        collected_at: str,
        error_msg: str,
        errors: List[str]
    ) -> Dict[str, Any]:
        """
        Return a fallback response structure when collection fails.

        Args:
            keyword: Search term
            collected_at: ISO timestamp
            error_msg: Primary error message
            errors: List of detailed errors

        Returns:
            Minimal valid response dict with error indicators
        """
        return {
            "source": "hacker_news",
            "collected_at": collected_at,
            "keyword": keyword,
            "mentions_30d": 0,
            "mentions_6m": 0,
            "mentions_1y": 0,
            "mentions_total": 0,
            "avg_points_30d": 0.0,
            "avg_comments_30d": 0.0,
            "avg_points_6m": 0.0,
            "avg_comments_6m": 0.0,
            "sentiment": 0.0,
            "recency": "unknown",
            "growth_trend": "unknown",
            "momentum": "unknown",
            "top_stories": [],
            "errors": errors + [error_msg]
        }
