"""
News coverage collector using GDELT API.
Gathers news media signals, sentiment/tone, and coverage trends for technology keywords.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx

from app.collectors.base import BaseCollector


class NewsCollector(BaseCollector):
    """Collects news media signals from GDELT API"""

    API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    TIMEOUT = 30.0

    async def collect(self, keyword: str, expanded_terms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Collect GDELT news data for the given keyword, optionally with expanded search terms.

        Queries the GDELT API across three time periods
        (30 days, 3 months, 1 year) to analyze news volume,
        sentiment/tone, geographic distribution, and media attention trends.

        When expanded_terms is provided, uses OR operator in GDELT query.

        Args:
            keyword: Technology keyword to analyze

        Returns:
            Dictionary containing:
                - source: Data source identifier
                - collected_at: ISO timestamp
                - keyword: Echo of search term
                - articles_30d, articles_3m, articles_1y: Article counts by period
                - articles_total: Sum of all articles
                - source_countries: Dict of country -> article count
                - geographic_diversity: Count of unique countries
                - unique_domains: Count of unique news domains
                - top_domains: Top 5 domains by article count
                - avg_tone: Average sentiment score
                - tone_distribution: Dict with positive/neutral/negative counts
                - volume_intensity_30d, volume_intensity_3m: Average intensity
                - media_attention: "high", "medium", or "low"
                - coverage_trend: "increasing", "stable", or "decreasing"
                - sentiment_trend: "positive", "neutral", or "negative"
                - mainstream_adoption: "mainstream", "emerging", or "niche"
                - top_articles: Sample of recent articles
                - errors: List of non-fatal errors encountered
        """
        now = datetime.now()
        collected_at = now.isoformat()

        # Calculate time period boundaries (GDELT format: YYYYMMDDHHMMSS)
        # 30-day period (most recent)
        start_30d = (now - timedelta(days=30)).strftime("%Y%m%d%H%M%S")
        end_30d = now.strftime("%Y%m%d%H%M%S")

        # 3-month period (excluding last 30 days)
        start_3m = (now - timedelta(days=90)).strftime("%Y%m%d%H%M%S")
        end_3m = (now - timedelta(days=30)).strftime("%Y%m%d%H%M%S")

        # 1-year period (excluding last 90 days)
        start_1y = (now - timedelta(days=365)).strftime("%Y%m%d%H%M%S")
        end_1y = (now - timedelta(days=90)).strftime("%Y%m%d%H%M%S")

        errors = []

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                # Fetch data for each time period
                data_30d = await self._fetch_period(
                    client, keyword, start_30d, end_30d, errors, expanded_terms
                )
                data_3m = await self._fetch_period(
                    client, keyword, start_3m, end_3m, errors, expanded_terms
                )
                data_1y = await self._fetch_period(
                    client, keyword, start_1y, end_1y, errors, expanded_terms
                )

                # If all requests failed, return error state
                if all(d is None for d in [data_30d, data_3m, data_1y]):
                    return self._error_response(keyword, collected_at, "All API requests failed", errors)

                # Extract article counts from each period
                articles_30d = data_30d.get("article_count", 0) if data_30d else 0
                articles_3m = data_3m.get("article_count", 0) if data_3m else 0
                articles_1y = data_1y.get("article_count", 0) if data_1y else 0

                # Aggregate geographic data
                source_countries = {}
                unique_domains_set = set()
                domain_counts = {}
                all_articles = []

                for data in [data_30d, data_3m, data_1y]:
                    if data and data.get("articles"):
                        for article in data.get("articles", []):
                            # Aggregate countries
                            country = article.get("sourcecountry", "Unknown")
                            source_countries[country] = source_countries.get(country, 0) + 1

                            # Aggregate domains
                            domain = article.get("domain", "")
                            if domain:
                                unique_domains_set.add(domain)
                                domain_counts[domain] = domain_counts.get(domain, 0) + 1

                            all_articles.append(article)

                # Calculate top domains
                top_domains = []
                if domain_counts:
                    sorted_domains = sorted(
                        domain_counts.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )
                    top_domains = [
                        {"domain": domain, "count": count}
                        for domain, count in sorted_domains[:5]
                    ]

                # Calculate tone metrics from 30-day data
                avg_tone = 0.0
                tone_distribution = {"positive": 0, "neutral": 0, "negative": 0}

                if data_30d and data_30d.get("tone_data"):
                    tone_result = self._calculate_tone_metrics(data_30d.get("tone_data", {}))
                    avg_tone = tone_result["avg_tone"]
                    tone_distribution = tone_result["distribution"]

                # Calculate volume intensity metrics
                volume_intensity_30d = data_30d.get("volume_intensity", 0.0) if data_30d else 0.0
                volume_intensity_3m = data_3m.get("volume_intensity", 0.0) if data_3m else 0.0
                volume_intensity_1y = data_1y.get("volume_intensity", 0.0) if data_1y else 0.0

                # Extract top articles from most recent period
                top_articles = []
                if data_30d and data_30d.get("articles"):
                    for article in data_30d.get("articles", [])[:5]:
                        top_articles.append({
                            "url": article.get("url", ""),
                            "title": article.get("title", ""),
                            "domain": article.get("domain", ""),
                            "country": article.get("sourcecountry", "Unknown"),
                            "date": article.get("seendate", "")
                        })

                # Calculate derived insights
                media_attention = self._calculate_media_attention(
                    articles_30d, articles_3m, articles_1y
                )
                coverage_trend = self._calculate_coverage_trend(
                    volume_intensity_30d, volume_intensity_3m, volume_intensity_1y
                )
                sentiment_trend = self._calculate_sentiment_trend(avg_tone)
                mainstream_adoption = self._calculate_mainstream_adoption(
                    len(unique_domains_set), articles_30d + articles_3m + articles_1y
                )

                return {
                    "source": "gdelt",
                    "collected_at": collected_at,
                    "keyword": keyword,

                    # Article counts by time period
                    "articles_30d": articles_30d,
                    "articles_3m": articles_3m,
                    "articles_1y": articles_1y,
                    "articles_total": articles_30d + articles_3m + articles_1y,

                    # Geographic distribution
                    "source_countries": source_countries,
                    "geographic_diversity": len(source_countries),

                    # Media diversity
                    "unique_domains": len(unique_domains_set),
                    "top_domains": top_domains,

                    # Sentiment/tone
                    "avg_tone": round(avg_tone, 3),
                    "tone_distribution": tone_distribution,

                    # Volume metrics
                    "volume_intensity_30d": round(volume_intensity_30d, 3),
                    "volume_intensity_3m": round(volume_intensity_3m, 3),
                    "volume_intensity_1y": round(volume_intensity_1y, 3),

                    # Derived insights
                    "media_attention": media_attention,
                    "coverage_trend": coverage_trend,
                    "sentiment_trend": sentiment_trend,
                    "mainstream_adoption": mainstream_adoption,

                    # Context for LLM
                    "top_articles": top_articles,

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
        start_datetime: str,
        end_datetime: str,
        errors: List[str],
        expanded_terms: Optional[List[str]] = None
    ) -> Dict[str, Any] | None:
        """
        Fetch GDELT data for a specific time period.

        Makes three parallel calls to GDELT API:
        - ArtList mode for article metadata
        - TimelineVol mode for volume trends
        - ToneChart mode for sentiment distribution

        When expanded_terms is provided, constructs OR query with GDELT syntax.

        Args:
            client: Async HTTP client
            keyword: Search term
            start_datetime: Start timestamp (YYYYMMDDHHMMSS format)
            end_datetime: End timestamp (YYYYMMDDHHMMSS format)
            errors: List to append error messages to
            expanded_terms: Optional list of related search terms

        Returns:
            Aggregated data dict or None if all requests failed
        """
        try:
            # Build search query with OR expansion if expanded_terms provided
            # GDELT requires parentheses around OR operator: ("term1" OR "term2")
            if expanded_terms:
                # Construct: ("keyword" OR "term1" OR "term2" ...)
                terms_str = " OR ".join([f'"{keyword}"'] + [f'"{term}"' for term in expanded_terms])
                search_query = f"({terms_str})"
            else:
                # Original behavior: exact phrase matching with quotes
                search_query = f'"{keyword}"'

            # Base parameters for all requests
            base_params = {
                "query": search_query,
                "format": "json",
                "startdatetime": start_datetime,
                "enddatetime": end_datetime
            }

            # Fetch article list
            artlist_params = {**base_params, "mode": "ArtList", "maxrecords": 250}
            artlist_response = await client.get(self.API_URL, params=artlist_params)
            artlist_response.raise_for_status()
            artlist_data = artlist_response.json()

            # Fetch timeline volume
            timeline_params = {**base_params, "mode": "timelinevol"}
            timeline_response = await client.get(self.API_URL, params=timeline_params)
            timeline_response.raise_for_status()
            timeline_data = timeline_response.json()

            # Fetch tone chart
            tone_params = {**base_params, "mode": "ToneChart"}
            tone_response = await client.get(self.API_URL, params=tone_params)
            tone_response.raise_for_status()
            tone_data = tone_response.json()

            # Extract article count and metadata
            articles = artlist_data.get("articles", [])
            article_count = len(articles)

            # Calculate average volume intensity from timeline data
            volume_intensity = 0.0
            if timeline_data.get("timeline"):
                timeline_series = timeline_data.get("timeline", [])
                if timeline_series and len(timeline_series) > 0:
                    data_points = timeline_series[0].get("data", [])
                    if data_points:
                        values = [point.get("value", 0.0) for point in data_points]
                        volume_intensity = sum(values) / len(values) if values else 0.0

            return {
                "article_count": article_count,
                "articles": articles,
                "volume_intensity": volume_intensity,
                "tone_data": tone_data
            }

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

    def _calculate_tone_metrics(self, tone_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate tone metrics from GDELT ToneChart data.

        Args:
            tone_data: ToneChart API response

        Returns:
            Dict with avg_tone and distribution
        """
        tonechart = tone_data.get("tonechart", [])
        if not tonechart:
            return {
                "avg_tone": 0.0,
                "distribution": {"positive": 0, "neutral": 0, "negative": 0}
            }

        # Calculate weighted average tone
        # GDELT bins: 0 (most negative) to 10 (most positive)
        total_count = 0
        weighted_sum = 0
        distribution = {"positive": 0, "neutral": 0, "negative": 0}

        for bin_data in tonechart:
            bin_index = bin_data.get("bin", 5)
            count = bin_data.get("count", 0)

            total_count += count
            weighted_sum += bin_index * count

            # Categorize into positive/neutral/negative
            if bin_index >= 7:
                distribution["positive"] += count
            elif bin_index <= 3:
                distribution["negative"] += count
            else:
                distribution["neutral"] += count

        # Calculate average and normalize to -1.0 to 1.0 scale
        if total_count > 0:
            avg_bin = weighted_sum / total_count
            # Map bin 0-10 to -1.0 to 1.0
            avg_tone = (avg_bin - 5) / 5.0
        else:
            avg_tone = 0.0

        return {
            "avg_tone": avg_tone,
            "distribution": distribution
        }

    def _calculate_media_attention(
        self, articles_30d: int, articles_3m: int, articles_1y: int
    ) -> str:
        """
        Calculate media attention level based on article counts.

        Args:
            articles_30d: Articles in last 30 days
            articles_3m: Articles in 3-month period
            articles_1y: Articles in 1-year period

        Returns:
            "high", "medium", or "low"
        """
        total = articles_30d + articles_3m + articles_1y

        if total >= 500:
            return "high"
        elif total >= 100:
            return "medium"
        else:
            return "low"

    def _calculate_coverage_trend(
        self, volume_30d: float, volume_3m: float, volume_1y: float
    ) -> str:
        """
        Calculate coverage trend from volume intensity data.

        Args:
            volume_30d: Volume intensity for 30-day period
            volume_3m: Volume intensity for 3-month period
            volume_1y: Volume intensity for 1-year period

        Returns:
            "increasing", "stable", or "decreasing"
        """
        # Compare recent volume to historical average
        if volume_3m == 0 and volume_1y == 0:
            return "stable" if volume_30d > 0 else "unknown"

        historical_avg = (volume_3m + volume_1y) / 2

        threshold = 0.3  # 30% difference threshold

        if volume_30d > historical_avg * (1 + threshold):
            return "increasing"
        elif volume_30d < historical_avg * (1 - threshold):
            return "decreasing"
        else:
            return "stable"

    def _calculate_sentiment_trend(self, avg_tone: float) -> str:
        """
        Categorize sentiment from average tone.

        Args:
            avg_tone: Average tone score (-1.0 to 1.0)

        Returns:
            "positive", "neutral", or "negative"
        """
        if avg_tone > 0.2:
            return "positive"
        elif avg_tone < -0.2:
            return "negative"
        else:
            return "neutral"

    def _calculate_mainstream_adoption(
        self, unique_domains: int, total_articles: int
    ) -> str:
        """
        Calculate mainstream adoption from domain diversity.

        Args:
            unique_domains: Count of unique news domains
            total_articles: Total article count

        Returns:
            "mainstream", "emerging", or "niche"
        """
        if total_articles == 0:
            return "niche"

        # Calculate domain diversity ratio
        diversity_ratio = unique_domains / total_articles if total_articles > 0 else 0

        if unique_domains >= 50 and diversity_ratio > 0.3:
            return "mainstream"
        elif unique_domains >= 20:
            return "emerging"
        else:
            return "niche"

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
            "source": "gdelt",
            "collected_at": collected_at,
            "keyword": keyword,
            "articles_30d": 0,
            "articles_3m": 0,
            "articles_1y": 0,
            "articles_total": 0,
            "source_countries": {},
            "geographic_diversity": 0,
            "unique_domains": 0,
            "top_domains": [],
            "avg_tone": 0.0,
            "tone_distribution": {"positive": 0, "neutral": 0, "negative": 0},
            "volume_intensity_30d": 0.0,
            "volume_intensity_3m": 0.0,
            "volume_intensity_1y": 0.0,
            "media_attention": "unknown",
            "coverage_trend": "unknown",
            "sentiment_trend": "neutral",
            "mainstream_adoption": "niche",
            "top_articles": [],
            "errors": errors + [error_msg]
        }
