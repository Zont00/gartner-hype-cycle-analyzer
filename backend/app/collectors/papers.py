"""
Research papers collector using Semantic Scholar API.
Gathers publication metrics, citation data, and academic research trends for technology keywords.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx

from app.collectors.base import BaseCollector
from app.config import get_settings


class PapersCollector(BaseCollector):
    """Collects academic research signals from Semantic Scholar API"""

    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    TIMEOUT = 30.0

    async def collect(self, keyword: str, expanded_terms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Collect Semantic Scholar research paper data for the given keyword, optionally with expanded search terms.

        Queries the Semantic Scholar API across multiple time periods
        (2 years, 5 years) to analyze publication volume, citation metrics,
        research velocity, and academic attention trends.

        When expanded_terms is provided, uses Boolean OR to search for keyword OR any expanded term.

        Args:
            keyword: Technology keyword to analyze
            expanded_terms: Optional list of related search terms for query expansion

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

        # Calculate year boundaries for time periods (non-overlapping)
        # 2y: Recent papers (current_year - 2 to current_year - 1)
        # 5y: Middle historical papers (current_year - 7 to current_year - 3)
        # 10y: Oldest historical papers (current_year - 12 to current_year - 8)
        year_2y_start = current_year - 2
        year_2y_end = current_year - 1
        year_5y_start = current_year - 7
        year_5y_end = current_year - 3
        year_10y_start = current_year - 12
        year_10y_end = current_year - 8

        errors = []

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                # Fetch data for each time period
                data_2y = await self._fetch_period(
                    client, keyword, year_2y_start, year_2y_end, errors, expanded_terms
                )
                data_5y = await self._fetch_period(
                    client, keyword, year_5y_start, year_5y_end, errors, expanded_terms
                )
                data_10y = await self._fetch_period(
                    client, keyword, year_10y_start, year_10y_end, errors, expanded_terms
                )

                # If all requests failed, return error state
                if all(d is None for d in [data_2y, data_5y, data_10y]):
                    return self._error_response(keyword, collected_at, "All API requests failed", errors)

                # Extract publication counts
                publications_2y = data_2y.get("total", 0) if data_2y else 0
                publications_5y = data_5y.get("total", 0) if data_5y else 0
                publications_10y = data_10y.get("total", 0) if data_10y else 0

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

                # Calculate citation metrics for 10-year period
                avg_citations_10y = 0.0
                avg_influential_citations_10y = 0.0

                if data_10y and data_10y.get("data"):
                    papers = data_10y.get("data", [])
                    total_citations = sum(p.get("citationCount", 0) or 0 for p in papers)
                    total_influential = sum(p.get("influentialCitationCount", 0) or 0 for p in papers)
                    avg_citations_10y = total_citations / len(papers) if papers else 0.0
                    avg_influential_citations_10y = total_influential / len(papers) if papers else 0.0

                # Aggregate all papers for paper type distribution analysis
                all_papers = []
                if data_2y and data_2y.get("data"):
                    all_papers.extend(data_2y.get("data", []))
                if data_5y and data_5y.get("data"):
                    all_papers.extend(data_5y.get("data", []))
                if data_10y and data_10y.get("data"):
                    all_papers.extend(data_10y.get("data", []))

                # Calculate paper type distribution
                paper_type_distribution = self._calculate_paper_type_distribution(all_papers)

                # Aggregate authors
                top_authors = self._aggregate_authors(all_papers)

                # Calculate derived insights
                citation_velocity = self._calculate_citation_velocity(
                    avg_citations_2y, avg_citations_5y
                )
                research_maturity, research_maturity_reasoning = self._calculate_research_maturity(
                    publications_2y, publications_5y, publications_10y, avg_citations_2y, paper_type_distribution
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
                    "publications_10y": publications_10y,
                    "publications_total": publications_2y + publications_5y + publications_10y,

                    # Citation metrics
                    "avg_citations_2y": round(avg_citations_2y, 2),
                    "avg_citations_5y": round(avg_citations_5y, 2),
                    "avg_citations_10y": round(avg_citations_10y, 2),
                    "avg_influential_citations_2y": round(avg_influential_citations_2y, 2),
                    "avg_influential_citations_5y": round(avg_influential_citations_5y, 2),
                    "avg_influential_citations_10y": round(avg_influential_citations_10y, 2),
                    "citation_velocity": round(citation_velocity, 3),

                    # Research breadth indicators
                    "author_diversity": author_diversity,
                    "venue_diversity": venue_diversity,

                    # Author metrics
                    "top_authors": top_authors,

                    # Paper type analysis
                    "paper_type_distribution": paper_type_distribution,

                    # Derived insights
                    "research_maturity": research_maturity,
                    "research_maturity_reasoning": research_maturity_reasoning,
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
        errors: List[str],
        expanded_terms: Optional[List[str]] = None
    ) -> Dict[str, Any] | None:
        """
        Fetch Semantic Scholar data for a specific time period.

        When expanded_terms is provided, constructs Boolean OR query with all terms.

        Args:
            client: Async HTTP client
            keyword: Search term
            year_start: Start year (inclusive)
            year_end: End year (exclusive)
            errors: List to append error messages to
            expanded_terms: Optional list of related search terms

        Returns:
            API response dict or None if request failed
        """
        try:
            # Build year filter (e.g., "2020-2023")
            year_filter = f"{year_start}-{year_end - 1}"

            # Request fields we need from the API
            fields = "paperId,title,year,citationCount,influentialCitationCount,authors,venue,publicationTypes"

            # Prepare headers with API key if configured
            settings = get_settings()
            headers = {}
            if settings.semantic_scholar_api_key:
                headers["x-api-key"] = settings.semantic_scholar_api_key

            # Build query with OR expansion if expanded_terms provided
            # Semantic Scholar uses | for OR operator
            if expanded_terms:
                # Construct: "keyword" | "term1" | "term2" ...
                query_parts = [f'"{keyword}"'] + [f'"{term}"' for term in expanded_terms]
                query_str = " | ".join(query_parts)
            else:
                # Original behavior: exact phrase matching with quotes
                query_str = f'"{keyword}"'

            # Make request to Semantic Scholar API
            response = await client.get(
                self.API_URL,
                params={
                    "query": query_str,
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
        self,
        publications_2y: int,
        publications_5y: int,
        publications_10y: int,
        avg_citations_2y: float,
        paper_type_distribution: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        Calculate research maturity level incorporating paper type distribution.

        Args:
            publications_2y: Publications in last 2 years
            publications_5y: Publications in prior 5 years
            publications_10y: Publications in oldest 10 years
            avg_citations_2y: Average citations for recent papers
            paper_type_distribution: Dict with type_percentages

        Returns:
            Tuple of (maturity_level, reasoning_string)
        """
        total_publications = publications_2y + publications_5y + publications_10y
        type_percentages = paper_type_distribution.get("type_percentages", {})

        # Extract key paper type percentages
        review_pct = type_percentages.get("review_percentage", 0.0)
        journal_pct = type_percentages.get("journalarticle_percentage", 0.0)
        conference_pct = type_percentages.get("conference_percentage", 0.0)

        # Type-aware maturity classification
        # Mature indicators: high review papers (>30%) OR high journal articles with substantial publications
        if review_pct > 30:
            return ("mature",
                    f"High review paper percentage ({review_pct:.1f}%) indicates established field "
                    f"with comprehensive synthesis literature. Total {total_publications} publications "
                    f"with {avg_citations_2y:.1f} avg citations.")

        if total_publications > 50 and journal_pct > 40:
            return ("mature",
                    f"Substantial publication volume ({total_publications} papers) dominated by "
                    f"journal articles ({journal_pct:.1f}%) with {avg_citations_2y:.1f} avg citations "
                    f"indicates mature research field.")

        if avg_citations_2y > 20 and journal_pct > 30:
            return ("mature",
                    f"High citation rate ({avg_citations_2y:.1f} avg) with journal dominance "
                    f"({journal_pct:.1f}%) indicates mature, impactful research field.")

        # Emerging indicators: high conference papers (>60%) OR very few publications with low citations
        if conference_pct > 60 and total_publications < 20:
            return ("emerging",
                    f"Conference paper dominance ({conference_pct:.1f}%) with limited publications "
                    f"({total_publications}) indicates early-stage research with rapid dissemination focus.")

        if total_publications < 10 and avg_citations_2y < 5:
            return ("emerging",
                    f"Very limited publications ({total_publications}) with low citations "
                    f"({avg_citations_2y:.1f} avg) indicates emerging research area in early stages.")

        # Developing: transition phase
        return ("developing",
                f"Moderate publication volume ({total_publications}) with mixed paper types "
                f"(conference: {conference_pct:.1f}%, journal: {journal_pct:.1f}%, review: {review_pct:.1f}%) "
                f"and {avg_citations_2y:.1f} avg citations indicates developing research field in transition.")

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

    def _calculate_paper_type_distribution(self, all_papers: List[Dict]) -> Dict[str, Any]:
        """
        Analyze distribution of paper types across all papers.

        Args:
            all_papers: List of all papers from all time periods

        Returns:
            Dictionary with type_counts, type_percentages, and papers_with_type_info
        """
        type_counts = {
            "Review": 0,
            "JournalArticle": 0,
            "Conference": 0,
            "Book": 0,
            "Other": 0
        }

        total_with_types = 0
        for paper in all_papers:
            pub_types = paper.get("publicationTypes", [])
            if pub_types:
                total_with_types += 1
                # A paper can have multiple types, count each
                for pub_type in pub_types:
                    if pub_type in type_counts:
                        type_counts[pub_type] += 1
                    else:
                        type_counts["Other"] += 1

        # Calculate percentages
        type_percentages = {}
        if total_with_types > 0:
            for type_name, count in type_counts.items():
                type_percentages[f"{type_name.lower()}_percentage"] = round(
                    (count / total_with_types) * 100, 1
                )
        else:
            # No type data available - set all to 0
            for type_name in type_counts.keys():
                type_percentages[f"{type_name.lower()}_percentage"] = 0.0

        return {
            "type_counts": type_counts,
            "type_percentages": type_percentages,
            "papers_with_type_info": total_with_types
        }

    def _aggregate_authors(self, all_papers: List[Dict]) -> List[Dict[str, Any]]:
        """
        Aggregate authors across all papers and return top 10 by publication count.

        Args:
            all_papers: List of all papers from all time periods

        Returns:
            List of top 10 authors with publication counts
        """
        author_counts = {}
        for paper in all_papers:
            authors = paper.get("authors", [])
            for author in authors:
                name = author.get("name", "")
                if name:
                    author_counts[name] = author_counts.get(name, 0) + 1

        # Sort by count and return top 10
        top_authors = [
            {"name": name, "publication_count": count}
            for name, count in sorted(
                author_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        ]

        return top_authors

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
            "publications_10y": 0,
            "publications_total": 0,
            "avg_citations_2y": 0.0,
            "avg_citations_5y": 0.0,
            "avg_citations_10y": 0.0,
            "avg_influential_citations_2y": 0.0,
            "avg_influential_citations_5y": 0.0,
            "avg_influential_citations_10y": 0.0,
            "citation_velocity": 0.0,
            "author_diversity": 0,
            "venue_diversity": 0,
            "top_authors": [],
            "paper_type_distribution": {
                "type_counts": {"Review": 0, "JournalArticle": 0, "Conference": 0, "Book": 0, "Other": 0},
                "type_percentages": {
                    "review_percentage": 0.0,
                    "journalarticle_percentage": 0.0,
                    "conference_percentage": 0.0,
                    "book_percentage": 0.0,
                    "other_percentage": 0.0
                },
                "papers_with_type_info": 0
            },
            "research_maturity": "unknown",
            "research_maturity_reasoning": "Data collection failed - unable to assess research maturity",
            "research_momentum": "unknown",
            "research_trend": "unknown",
            "research_breadth": "unknown",
            "top_papers": [],
            "errors": errors + [error_msg]
        }
