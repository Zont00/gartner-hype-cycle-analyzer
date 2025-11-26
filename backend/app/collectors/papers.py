"""
Research papers collector using Semantic Scholar API.
Gathers publication metrics, citation data, and academic research trends for technology keywords.
"""
from datetime import datetime
from typing import Dict, Any, List
import httpx

from app.collectors.base import BaseCollector
from app.config import get_settings


class PapersCollector(BaseCollector):
    """Collects academic research signals from Semantic Scholar API"""

    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    TIMEOUT = 30.0

    async def collect(self, keyword: str) -> Dict[str, Any]:
        """
        Collect Semantic Scholar research paper data for the given keyword.

        Queries the Semantic Scholar API across multiple time periods
        (2 years, 5 years) to analyze publication volume, citation metrics,
        research velocity, and academic attention trends.

        Args:
            keyword: Technology keyword to analyze

        Returns:
            Dictionary containing:
                - source: Data source identifier
                - collected_at: ISO timestamp
                - keyword: Echo of search term
                - publications_2y, publications_5y: Paper counts by period
                - avg_citations_2y, avg_citations_5y: Average citations by period
                - citation_velocity: Rate of citation growth
                - research_maturity: Maturity level ("emerging", "developing", "mature")
                - research_momentum: Growth pattern ("accelerating", "steady", "decelerating")
                - research_trend: Trend direction ("increasing", "stable", "decreasing")
                - research_breadth: Diversity indicator ("narrow", "moderate", "broad")
                - top_papers: Sample of highly cited papers
                - errors: List of non-fatal errors encountered
        """
        now = datetime.now()
        collected_at = now.isoformat()
        current_year = now.year

        # Calculate year boundaries for time periods
        year_2y_start = current_year - 2
        year_5y_start = current_year - 5

        errors = []

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                # Fetch data for each time period
                data_2y = await self._fetch_period(
                    client, keyword, year_2y_start, current_year, errors
                )
                data_5y = await self._fetch_period(
                    client, keyword, year_5y_start, year_2y_start, errors
                )

                # If all requests failed, return error state
                if all(d is None for d in [data_2y, data_5y]):
                    return self._error_response(keyword, collected_at, "All API requests failed", errors)

                # Extract publication counts
                publications_2y = data_2y.get("total", 0) if data_2y else 0
                publications_5y = data_5y.get("total", 0) if data_5y else 0

                # Calculate citation metrics for 2-year period
                avg_citations_2y = 0.0
                avg_influential_citations_2y = 0.0
                top_papers = []

                if data_2y and data_2y.get("data"):
                    papers = data_2y.get("data", [])
                    total_citations = sum(p.get("citationCount", 0) or 0 for p in papers)
                    total_influential = sum(p.get("influentialCitationCount", 0) or 0 for p in papers)
                    avg_citations_2y = total_citations / len(papers) if papers else 0.0
                    avg_influential_citations_2y = total_influential / len(papers) if papers else 0.0

                    # Extract top papers for LLM context (sort by citations)
                    sorted_papers = sorted(
                        papers,
                        key=lambda p: p.get("citationCount", 0) or 0,
                        reverse=True
                    )
                    for paper in sorted_papers[:5]:
                        top_papers.append({
                            "title": paper.get("title", ""),
                            "year": paper.get("year"),
                            "citations": paper.get("citationCount", 0) or 0,
                            "influential_citations": paper.get("influentialCitationCount", 0) or 0,
                            "authors": len(paper.get("authors", [])),
                            "venue": paper.get("venue", "")
                        })

                # Calculate citation metrics for 5-year period
                avg_citations_5y = 0.0
                avg_influential_citations_5y = 0.0
                author_diversity = 0
                venue_diversity = 0

                if data_5y and data_5y.get("data"):
                    papers = data_5y.get("data", [])
                    total_citations = sum(p.get("citationCount", 0) or 0 for p in papers)
                    total_influential = sum(p.get("influentialCitationCount", 0) or 0 for p in papers)
                    avg_citations_5y = total_citations / len(papers) if papers else 0.0
                    avg_influential_citations_5y = total_influential / len(papers) if papers else 0.0

                    # Calculate breadth indicators
                    unique_authors = set()
                    unique_venues = set()
                    for paper in papers:
                        for author in paper.get("authors", []):
                            author_id = author.get("authorId")
                            if author_id:
                                unique_authors.add(author_id)
                        venue = paper.get("venue", "")
                        if venue:
                            unique_venues.add(venue)
                    author_diversity = len(unique_authors)
                    venue_diversity = len(unique_venues)

                # Calculate derived insights
                citation_velocity = self._calculate_citation_velocity(
                    avg_citations_2y, avg_citations_5y
                )
                research_maturity = self._calculate_research_maturity(
                    publications_2y, publications_5y, avg_citations_2y
                )
                research_momentum = self._calculate_research_momentum(
                    publications_2y, publications_5y
                )
                research_trend = self._calculate_research_trend(
                    publications_2y, publications_5y
                )
                research_breadth = self._calculate_research_breadth(
                    author_diversity, venue_diversity, publications_2y + publications_5y
                )

                return {
                    "source": "semantic_scholar",
                    "collected_at": collected_at,
                    "keyword": keyword,

                    # Publication counts by time period
                    "publications_2y": publications_2y,
                    "publications_5y": publications_5y,
                    "publications_total": publications_2y + publications_5y,

                    # Citation metrics
                    "avg_citations_2y": round(avg_citations_2y, 2),
                    "avg_citations_5y": round(avg_citations_5y, 2),
                    "avg_influential_citations_2y": round(avg_influential_citations_2y, 2),
                    "avg_influential_citations_5y": round(avg_influential_citations_5y, 2),
                    "citation_velocity": round(citation_velocity, 3),

                    # Research breadth indicators
                    "author_diversity": author_diversity,
                    "venue_diversity": venue_diversity,

                    # Derived insights
                    "research_maturity": research_maturity,
                    "research_momentum": research_momentum,
                    "research_trend": research_trend,
                    "research_breadth": research_breadth,

                    # Context for LLM
                    "top_papers": top_papers,

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
        year_start: int,
        year_end: int,
        errors: List[str]
    ) -> Dict[str, Any] | None:
        """
        Fetch Semantic Scholar data for a specific time period.

        Args:
            client: Async HTTP client
            keyword: Search term
            year_start: Start year (inclusive)
            year_end: End year (exclusive)
            errors: List to append error messages to

        Returns:
            API response dict or None if request failed
        """
        try:
            # Build year filter (e.g., "2020-2023")
            year_filter = f"{year_start}-{year_end - 1}"

            # Request fields we need from the API
            fields = "paperId,title,year,citationCount,influentialCitationCount,authors,venue"

            # Prepare headers with API key if configured
            settings = get_settings()
            headers = {}
            if settings.semantic_scholar_api_key:
                headers["x-api-key"] = settings.semantic_scholar_api_key

            # Make request to Semantic Scholar API
            # Always wrap keyword with quotes for exact phrase matching
            response = await client.get(
                self.API_URL,
                params={
                    "query": f'"{keyword}"',
                    "year": year_filter,
                    "fields": fields,
                    "limit": 100  # Maximum allowed per request
                },
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            # API returns {"total": int, "offset": int, "next": int, "data": [papers]}
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                errors.append("Rate limited")
            elif e.response.status_code == 400:
                errors.append("Invalid query parameters")
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
            errors.append(f"Unexpected error in fetch: {str(e)}")
            return None

    def _calculate_citation_velocity(self, avg_citations_2y: float, avg_citations_5y: float) -> float:
        """
        Calculate citation velocity (rate of citation growth).

        Args:
            avg_citations_2y: Average citations for recent 2-year period
            avg_citations_5y: Average citations for older 5-year period

        Returns:
            Citation velocity score (higher = faster growth)
        """
        # Handle edge cases
        if avg_citations_5y == 0:
            # If no historical citations, velocity is 0 if no recent citations either
            return 0.0 if avg_citations_2y == 0 else 1.0

        # Calculate growth rate: (recent - historical) / historical
        velocity = (avg_citations_2y - avg_citations_5y) / avg_citations_5y
        return velocity

    def _calculate_research_maturity(
        self, publications_2y: int, publications_5y: int, avg_citations_2y: float
    ) -> str:
        """
        Calculate research maturity level based on publication and citation patterns.

        Args:
            publications_2y: Publications in last 2 years
            publications_5y: Publications in prior 5 years
            avg_citations_2y: Average citations for recent papers

        Returns:
            "emerging", "developing", or "mature"
        """
        total_publications = publications_2y + publications_5y

        # Mature: High publication count (>50) or high recent citations (>20)
        if total_publications > 50 or avg_citations_2y > 20:
            return "mature"

        # Emerging: Very few publications (<10) and low citations (<5)
        if total_publications < 10 and avg_citations_2y < 5:
            return "emerging"

        # Developing: Everything in between
        return "developing"

    def _calculate_research_momentum(self, publications_2y: int, publications_5y: int) -> str:
        """
        Calculate research momentum by comparing publication rates across periods.

        Args:
            publications_2y: Publications in last 2 years
            publications_5y: Publications in prior 5 years

        Returns:
            "accelerating", "steady", or "decelerating"
        """
        # Calculate publication rate per year for each period
        recent_rate = publications_2y / 2.0  # Per year in 2-year period
        historical_rate = publications_5y / 5.0  # Per year in 5-year period

        # Handle edge case: no historical data
        if historical_rate == 0:
            return "steady" if recent_rate == 0 else "accelerating"

        # Calculate growth ratio
        growth_ratio = recent_rate / historical_rate

        # Accelerating: Recent rate >50% higher
        if growth_ratio > 1.5:
            return "accelerating"

        # Decelerating: Recent rate <50% of historical
        if growth_ratio < 0.5:
            return "decelerating"

        # Steady: Within 50% range
        return "steady"

    def _calculate_research_trend(self, publications_2y: int, publications_5y: int) -> str:
        """
        Calculate research trend direction.

        Args:
            publications_2y: Publications in last 2 years
            publications_5y: Publications in prior 5 years

        Returns:
            "increasing", "stable", or "decreasing"
        """
        # Calculate per-year rates
        recent_rate = publications_2y / 2.0
        historical_rate = publications_5y / 5.0

        # Handle edge case
        if historical_rate == 0:
            return "stable" if recent_rate == 0 else "increasing"

        # Calculate percentage difference
        diff_ratio = (recent_rate - historical_rate) / historical_rate

        # Increasing: Recent rate >30% higher
        if diff_ratio > 0.3:
            return "increasing"

        # Decreasing: Recent rate >30% lower
        if diff_ratio < -0.3:
            return "decreasing"

        # Stable: Within 30% range
        return "stable"

    def _calculate_research_breadth(
        self, author_diversity: int, venue_diversity: int, total_publications: int
    ) -> str:
        """
        Calculate research breadth from author and venue diversity.

        Args:
            author_diversity: Number of unique authors
            venue_diversity: Number of unique venues
            total_publications: Total publication count

        Returns:
            "narrow", "moderate", or "broad"
        """
        # Handle edge case
        if total_publications == 0:
            return "narrow"

        # Calculate diversity ratios (how many unique authors/venues per paper)
        author_ratio = author_diversity / total_publications if total_publications > 0 else 0
        venue_ratio = venue_diversity / total_publications if total_publications > 0 else 0

        # Broad: High diversity (many unique authors and venues)
        # Typically >2 authors per paper and >0.3 venues per paper suggests broad research
        if author_ratio > 2.0 and venue_ratio > 0.3:
            return "broad"

        # Narrow: Low diversity (few unique authors or venues)
        # <1.5 authors per paper or <0.1 venues per paper suggests narrow research
        if author_ratio < 1.5 or venue_ratio < 0.1:
            return "narrow"

        # Moderate: Everything in between
        return "moderate"

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
            "source": "semantic_scholar",
            "collected_at": collected_at,
            "keyword": keyword,
            "publications_2y": 0,
            "publications_5y": 0,
            "publications_total": 0,
            "avg_citations_2y": 0.0,
            "avg_citations_5y": 0.0,
            "avg_influential_citations_2y": 0.0,
            "avg_influential_citations_5y": 0.0,
            "citation_velocity": 0.0,
            "author_diversity": 0,
            "venue_diversity": 0,
            "research_maturity": "unknown",
            "research_momentum": "unknown",
            "research_trend": "unknown",
            "research_breadth": "unknown",
            "top_papers": [],
            "errors": errors + [error_msg]
        }
