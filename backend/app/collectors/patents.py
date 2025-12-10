"""
Patent data collector using PatentsView Search API.
Gathers patent filing signals, assignee diversity, geographical distribution,
and innovation velocity metrics for technology keywords.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import quote
import httpx
import json

from app.collectors.base import BaseCollector
from app.config import get_settings


class PatentsCollector(BaseCollector):
    """Collects patent signals from PatentsView Search API"""

    API_URL = "https://search.patentsview.org/api/v1/patent/"
    TIMEOUT = 30.0

    async def collect(self, keyword: str, expanded_terms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Collect patent data for the given keyword, optionally with expanded search terms.

        Queries the PatentsView Search API across three time periods
        (2 years, 5 years, 10 years) to analyze patent filing trends,
        assignee diversity, geographical distribution, and innovation velocity.

        Args:
            keyword: Technology keyword to analyze

        Returns:
            Dictionary containing:
                - source: Data source identifier
                - collected_at: ISO timestamp
                - keyword: Echo of search term
                - patents_2y, patents_5y, patents_10y: Patent counts by period
                - unique_assignees: Number of unique assignee organizations
                - top_assignees: Top 5 assignees by patent count
                - countries: Patent count by country
                - geographic_diversity: Number of unique countries
                - avg_citations_2y, avg_citations_5y: Average citations by period
                - filing_velocity: Patent filing growth rate
                - assignee_concentration: "concentrated", "moderate", or "diverse"
                - geographic_reach: "domestic", "regional", or "global"
                - patent_maturity: "emerging", "developing", or "mature"
                - patent_momentum: "accelerating", "steady", or "decelerating"
                - patent_trend: "increasing", "stable", or "decreasing"
                - top_patents: Sample of patents for LLM context
                - errors: List of non-fatal errors encountered
        """
        now = datetime.now()
        collected_at = now.isoformat()
        current_year = now.year

        # Calculate year boundaries for time periods (non-overlapping)
        # 2y: 2023-2024 (current_year-2 to current_year-1)
        # 5y: 2019-2022 (current_year-7 to current_year-3)
        # 10y: 2014-2018 (current_year-12 to current_year-8)
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

                # Extract patent counts
                patents_2y = data_2y.get("total_hits", 0) if data_2y else 0
                patents_5y = data_5y.get("total_hits", 0) if data_5y else 0
                patents_10y = data_10y.get("total_hits", 0) if data_10y else 0

                # Aggregate all patents for detailed analysis
                all_patents = []
                if data_2y and data_2y.get("patents"):
                    all_patents.extend(data_2y.get("patents", []))
                if data_5y and data_5y.get("patents"):
                    all_patents.extend(data_5y.get("patents", []))
                if data_10y and data_10y.get("patents"):
                    all_patents.extend(data_10y.get("patents", []))

                # Extract assignee diversity metrics with type classification
                assignee_counts = {}
                assignee_types = {}  # Map org name -> assignee type
                classified_assignees = []  # List of all classified types for distribution calculation

                for patent in all_patents:
                    assignees = patent.get("assignees", [])
                    for assignee in assignees:
                        org = assignee.get("assignee_organization", "Individual")
                        assignee_type_code = assignee.get("assignee_type")

                        if org:
                            # Count patents per assignee
                            assignee_counts[org] = assignee_counts.get(org, 0) + 1

                            # Classify assignee type (only once per unique org)
                            if org not in assignee_types:
                                assignee_types[org] = self._classify_assignee(org, assignee_type_code)

                            # Track all classifications for distribution calculation
                            classified_assignees.append(assignee_types[org])

                unique_assignees = len(assignee_counts)
                top_assignees = [
                    {
                        "name": name,
                        "patent_count": count,
                        "type": assignee_types.get(name, "Corporate")
                    }
                    for name, count in sorted(
                        assignee_counts.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:5]
                ]

                # Extract geographic distribution
                country_counts = {}
                for patent in all_patents:
                    assignees = patent.get("assignees", [])
                    for assignee in assignees:
                        country = assignee.get("assignee_country", "Unknown")
                        if country and country != "Unknown":
                            country_counts[country] = country_counts.get(country, 0) + 1

                geographic_diversity = len(country_counts)

                # Calculate citation metrics for 2y and 5y periods
                avg_citations_2y = 0.0
                avg_citations_5y = 0.0

                if data_2y and data_2y.get("patents"):
                    patents_2y_list = data_2y.get("patents", [])
                    total_citations = 0
                    count_with_citations = 0
                    for patent in patents_2y_list:
                        citation_val = patent.get("patent_num_times_cited_by_us_patents")
                        try:
                            citations = int(citation_val) if citation_val is not None else 0
                            total_citations += citations
                            count_with_citations += 1
                        except (ValueError, TypeError):
                            pass
                    avg_citations_2y = total_citations / count_with_citations if count_with_citations > 0 else 0.0

                if data_5y and data_5y.get("patents"):
                    patents_5y_list = data_5y.get("patents", [])
                    total_citations = 0
                    count_with_citations = 0
                    for patent in patents_5y_list:
                        citation_val = patent.get("patent_num_times_cited_by_us_patents")
                        try:
                            citations = int(citation_val) if citation_val is not None else 0
                            total_citations += citations
                            count_with_citations += 1
                        except (ValueError, TypeError):
                            pass
                    avg_citations_5y = total_citations / count_with_citations if count_with_citations > 0 else 0.0

                # Extract top patents for LLM context (sort by citations)
                top_patents = []
                patents_with_citations = []
                for patent in all_patents:
                    citation_val = patent.get("patent_num_times_cited_by_us_patents")
                    try:
                        citations = int(citation_val) if citation_val is not None else 0
                    except (ValueError, TypeError):
                        citations = 0

                    assignees = patent.get("assignees", [])
                    assignee_name = assignees[0].get("assignee_organization", "Individual") if assignees else "Individual"
                    assignee_country = assignees[0].get("assignee_country", "Unknown") if assignees else "Unknown"

                    patents_with_citations.append({
                        "patent_number": patent.get("patent_id", "unknown"),  # API uses patent_id
                        "title": patent.get("patent_title", ""),
                        "date": patent.get("patent_date", ""),
                        "assignee": assignee_name,
                        "country": assignee_country,
                        "citations": citations
                    })

                # Sort by citations (highest first) and take top 5
                patents_with_citations.sort(key=lambda x: x["citations"], reverse=True)
                top_patents = patents_with_citations[:5]

                # Calculate derived insights
                filing_velocity = self._calculate_filing_velocity(patents_2y, patents_5y)
                assignee_concentration = self._calculate_assignee_concentration(
                    assignee_counts, patents_2y + patents_5y + patents_10y
                )
                geographic_reach = self._calculate_geographic_reach(country_counts)
                patent_maturity = self._calculate_patent_maturity(
                    patents_2y + patents_5y + patents_10y, avg_citations_2y
                )
                patent_momentum = self._calculate_patent_momentum(patents_2y, patents_5y)
                patent_trend = self._calculate_patent_trend(patents_2y, patents_5y)

                # Calculate assignee type distribution and derived metrics
                assignee_type_distribution = self._calculate_assignee_type_distribution(classified_assignees)
                university_ratio = self._calculate_university_ratio(assignee_type_distribution)
                academic_ratio = self._calculate_academic_ratio(assignee_type_distribution)
                commercialization_index = self._calculate_commercialization_index(assignee_type_distribution)
                innovation_stage, innovation_stage_reasoning = self._calculate_innovation_stage(
                    assignee_type_distribution, university_ratio, patents_2y + patents_5y + patents_10y
                )

                return {
                    "source": "patentsview",
                    "collected_at": collected_at,
                    "keyword": keyword,

                    # Patent counts by time period
                    "patents_2y": patents_2y,
                    "patents_5y": patents_5y,
                    "patents_10y": patents_10y,
                    "patents_total": patents_2y + patents_5y + patents_10y,

                    # Assignee diversity metrics
                    "unique_assignees": unique_assignees,
                    "top_assignees": top_assignees,

                    # Assignee type classification metrics
                    "assignee_type_distribution": assignee_type_distribution.get("type_percentages", {}),
                    "university_ratio": university_ratio,
                    "academic_ratio": academic_ratio,
                    "commercialization_index": commercialization_index,
                    "innovation_stage": innovation_stage,
                    "innovation_stage_reasoning": innovation_stage_reasoning,

                    # Geographic distribution
                    "countries": country_counts,
                    "geographic_diversity": geographic_diversity,

                    # Citation metrics
                    "avg_citations_2y": round(avg_citations_2y, 2),
                    "avg_citations_5y": round(avg_citations_5y, 2),

                    # Derived insights
                    "filing_velocity": round(filing_velocity, 3),
                    "assignee_concentration": assignee_concentration,
                    "geographic_reach": geographic_reach,
                    "patent_maturity": patent_maturity,
                    "patent_momentum": patent_momentum,
                    "patent_trend": patent_trend,

                    # Context for LLM
                    "top_patents": top_patents,

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
        Fetch PatentsView data for a specific time period.

        When expanded_terms is provided, constructs OR query matching keyword OR any expanded term.

        Args:
            client: Async HTTP client
            keyword: Search term
            year_start: Start year (inclusive)
            year_end: End year (inclusive)
            errors: List to append error messages to
            expanded_terms: Optional list of related search terms

        Returns:
            API response dict or None if request failed
        """
        try:
            # Build date filter (ISO format YYYY-MM-DD)
            date_start = f"{year_start}-01-01"
            date_end = f"{year_end}-12-31"

            # Build query using _text_all for keyword matching (ensures ALL words present)
            # Search in both title and abstract
            if expanded_terms:
                # With expanded terms: create OR clause for each term (keyword + expanded)
                text_clauses = []
                for term in [keyword] + expanded_terms:
                    text_clauses.append({
                        "_or": [
                            {"_text_all": {"patent_title": term}},
                            {"_text_all": {"patent_abstract": term}}
                        ]
                    })

                query = {
                    "_and": [
                        {"_or": text_clauses},  # Match ANY of the terms
                        {"_gte": {"patent_date": date_start}},
                        {"_lte": {"patent_date": date_end}}
                    ]
                }
            else:
                # Original behavior: single keyword
                query = {
                    "_and": [
                        {
                            "_or": [
                                {"_text_all": {"patent_title": keyword}},
                                {"_text_all": {"patent_abstract": keyword}}
                            ]
                        },
                        {"_gte": {"patent_date": date_start}},
                        {"_lte": {"patent_date": date_end}}
                    ]
                }

            # Fields to retrieve (use patent_id not patent_number)
            # Citation field: patent_num_times_cited_by_us_patents
            # Note: assignee_type is nested inside assignees object, not a top-level field
            fields = [
                "patent_id",
                "patent_title",
                "patent_abstract",
                "patent_date",
                "patent_num_times_cited_by_us_patents",
                "assignees"
            ]

            # Options: 100 results per page (max 1000)
            options = {"size": 100}

            # Get API key from settings
            settings = get_settings()
            headers = {}
            if settings.patentsview_api_key:
                headers["X-Api-Key"] = settings.patentsview_api_key
            else:
                errors.append("Missing PatentsView API key")
                return None

            # Make GET request with manually encoded JSON parameters
            # httpx doesn't encode JSON params correctly, so we build the URL manually
            q = json.dumps(query)
            f = json.dumps(fields)
            o = json.dumps(options)
            url = f'{self.API_URL}?q={quote(q)}&f={quote(f)}&o={quote(o)}'

            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Check for API error flag
            if data.get("error", False):
                errors.append("API returned error flag")
                return None

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited - check for Retry-After header
                retry_after = e.response.headers.get("Retry-After", "unknown")
                errors.append(f"Rate limited (retry after {retry_after}s)")
            elif e.response.status_code == 401:
                errors.append("Authentication failed - invalid API key")
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

    def _calculate_filing_velocity(self, patents_2y: int, patents_5y: int) -> float:
        """
        Calculate patent filing velocity (rate of filing growth).

        Args:
            patents_2y: Patents in last 2 years
            patents_5y: Patents in prior 5 years

        Returns:
            Filing velocity score (higher = faster growth)
        """
        # Calculate per-year rates
        recent_rate = patents_2y / 2.0
        historical_rate = patents_5y / 5.0

        # Handle edge case: no historical data
        if historical_rate == 0:
            return 0.0 if recent_rate == 0 else 1.0

        # Calculate growth rate: (recent - historical) / historical
        velocity = (recent_rate - historical_rate) / historical_rate
        return velocity

    def _calculate_assignee_concentration(
        self, assignee_counts: Dict[str, int], total_patents: int
    ) -> str:
        """
        Calculate assignee concentration level.

        Args:
            assignee_counts: Dictionary of assignee name -> patent count
            total_patents: Total number of patents

        Returns:
            "concentrated", "moderate", or "diverse"
        """
        if total_patents == 0 or not assignee_counts:
            return "unknown"

        # Get top 3 assignees
        sorted_assignees = sorted(
            assignee_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        top_3_count = sum(count for _, count in sorted_assignees[:3])

        # Calculate percentage of patents from top 3
        top_3_percentage = top_3_count / total_patents

        if top_3_percentage > 0.5:
            return "concentrated"
        elif top_3_percentage > 0.25:
            return "moderate"
        else:
            return "diverse"

    def _calculate_geographic_reach(self, country_counts: Dict[str, int]) -> str:
        """
        Calculate geographic reach based on country distribution.

        Args:
            country_counts: Dictionary of country code -> patent count

        Returns:
            "domestic", "regional", or "global"
        """
        if not country_counts:
            return "unknown"

        total_patents = sum(country_counts.values())
        if total_patents == 0:
            return "unknown"

        # Count countries with >5% of patents
        significant_countries = sum(
            1 for count in country_counts.values()
            if count / total_patents > 0.05
        )

        if significant_countries == 1:
            return "domestic"
        elif significant_countries <= 3:
            return "regional"
        else:
            return "global"

    def _calculate_patent_maturity(self, total_patents: int, avg_citations_2y: float) -> str:
        """
        Calculate patent maturity level.

        Args:
            total_patents: Total number of patents
            avg_citations_2y: Average citations for recent patents

        Returns:
            "emerging", "developing", or "mature"
        """
        # Mature: High patent count (>500) or high recent citations (>15)
        if total_patents > 500 or avg_citations_2y > 15:
            return "mature"

        # Emerging: Very few patents (<50) and low citations (<5)
        if total_patents < 50 and avg_citations_2y < 5:
            return "emerging"

        # Developing: Everything in between
        return "developing"

    def _calculate_patent_momentum(self, patents_2y: int, patents_5y: int) -> str:
        """
        Calculate patent momentum by comparing filing rates across periods.

        Args:
            patents_2y: Patents in last 2 years
            patents_5y: Patents in prior 5 years

        Returns:
            "accelerating", "steady", or "decelerating"
        """
        # Calculate filing rate per year for each period
        recent_rate = patents_2y / 2.0
        historical_rate = patents_5y / 5.0

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

    def _calculate_patent_trend(self, patents_2y: int, patents_5y: int) -> str:
        """
        Calculate patent trend direction.

        Args:
            patents_2y: Patents in last 2 years
            patents_5y: Patents in prior 5 years

        Returns:
            "increasing", "stable", or "decreasing"
        """
        # Calculate per-year rates
        recent_rate = patents_2y / 2.0
        historical_rate = patents_5y / 5.0

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

    def _classify_assignee(self, assignee_org: str, assignee_type: Optional[int] = None) -> str:
        """
        Classify assignee into one of 5 categories based on organization name and type code.

        Uses pattern matching on organization names to identify universities and research
        institutes, then falls back to assignee_type codes for government/individual
        classification.

        Args:
            assignee_org: Organization name (e.g., "MIT", "IBM", "Stanford University")
            assignee_type: Optional PatentsView assignee_type code (1-9)

        Returns:
            One of: "University", "Research Institute", "Corporate", "Government", "Individual"
        """
        if not assignee_org or assignee_org == "Individual":
            return "Individual"

        # Normalize for case-insensitive matching
        org_lower = assignee_org.lower()

        # Priority 1: Check for University patterns
        university_keywords = [
            "university", "universit",  # International variations (université, università, etc.)
            "college",
            " state",  # Space prefix to avoid matching "estate", "restate", etc.
            " tech ",  # Space-bounded to avoid "technology", "technical"
        ]
        university_abbreviations = [
            "mit", "caltech", "eth", "epfl", "cmu", "ucla", "ucb", "nyu"
        ]

        for keyword in university_keywords:
            if keyword in org_lower:
                # Special case: "College of" might be corporate training
                if keyword == "college" and "college of" in org_lower:
                    continue
                return "University"

        # Check for common university abbreviations (as whole words)
        org_words = org_lower.split()
        for abbrev in university_abbreviations:
            if abbrev in org_words:
                return "University"

        # Priority 2: Check for Research Institute patterns
        institute_keywords = [
            "institute", "institut",  # International variations
            "research center", "research centre",
            "laboratory", "laborator",  # Catches "laboratories"
            "national lab",  # "Sandia National Laboratories"
            "max planck",  # Max Planck Institute
            "fraunhofer",  # Fraunhofer Society
            "cnrs",  # French National Centre for Scientific Research
            "nist",  # National Institute of Standards and Technology
        ]

        # Special handling for corporate research labs vs. research institutes
        # "IBM Research" should be Corporate, "Sandia National Laboratories" should be Research Institute
        corporate_research_exceptions = [
            "ibm research", "microsoft research", "google research", "amazon research",
            "facebook research", "meta research", "apple research", "intel research"
        ]

        # Check for corporate research exceptions first
        is_corporate_research = any(exc in org_lower for exc in corporate_research_exceptions)

        if not is_corporate_research:
            for keyword in institute_keywords:
                if keyword in org_lower:
                    return "Research Institute"

        # Priority 3: Check assignee_type code for Government/Individual
        # Based on typical patent database conventions:
        # - Code 2-3: Individual/inventor
        # - Code 4-5: Company/organization
        # - Code 6-7: Government entity
        if assignee_type is not None:
            if assignee_type in [2, 3]:
                return "Individual"
            elif assignee_type in [6, 7]:
                return "Government"

        # Priority 4: Default to Corporate
        # If no university/institute patterns matched and not government/individual by type code
        return "Corporate"

    def _calculate_assignee_type_distribution(self, classified_assignees: List[str]) -> Dict[str, Any]:
        """
        Calculate percentage distribution of assignee types.

        Args:
            classified_assignees: List of all assignee type classifications

        Returns:
            Dictionary with type counts and percentages for each category
        """
        # Count each type
        type_counts = {
            "University": 0,
            "Research Institute": 0,
            "Corporate": 0,
            "Government": 0,
            "Individual": 0
        }

        for assignee_type in classified_assignees:
            if assignee_type in type_counts:
                type_counts[assignee_type] += 1

        # Calculate percentages
        total = len(classified_assignees)
        type_percentages = {}
        if total > 0:
            for type_name, count in type_counts.items():
                type_percentages[type_name] = round((count / total) * 100, 1)
        else:
            # No assignees - set all to 0
            for type_name in type_counts.keys():
                type_percentages[type_name] = 0.0

        return {
            "type_counts": type_counts,
            "type_percentages": type_percentages,
            "total_assignees": total
        }

    def _calculate_university_ratio(self, type_distribution: Dict[str, Any]) -> float:
        """
        Calculate percentage of university assignees.

        Args:
            type_distribution: Output from _calculate_assignee_type_distribution()

        Returns:
            University percentage (0-100)
        """
        return type_distribution.get("type_percentages", {}).get("University", 0.0)

    def _calculate_academic_ratio(self, type_distribution: Dict[str, Any]) -> float:
        """
        Calculate percentage of academic assignees (universities + research institutes).

        Args:
            type_distribution: Output from _calculate_assignee_type_distribution()

        Returns:
            Academic percentage (0-100)
        """
        percentages = type_distribution.get("type_percentages", {})
        university = percentages.get("University", 0.0)
        research_institute = percentages.get("Research Institute", 0.0)
        return round(university + research_institute, 1)

    def _calculate_commercialization_index(self, type_distribution: Dict[str, Any]) -> float:
        """
        Calculate commercialization index (corporate / academic ratio).

        Higher values indicate stronger commercial adoption.

        Args:
            type_distribution: Output from _calculate_assignee_type_distribution()

        Returns:
            Commercialization index (0+ where >2.0 indicates strong commercial adoption)
        """
        percentages = type_distribution.get("type_percentages", {})
        corporate = percentages.get("Corporate", 0.0)
        university = percentages.get("University", 0.0)
        research_institute = percentages.get("Research Institute", 0.0)
        academic = university + research_institute

        # Handle edge case: no academic assignees
        if academic == 0:
            # If corporate presence but no academic, high commercialization
            return 10.0 if corporate > 0 else 0.0

        return round(corporate / academic, 2)

    def _calculate_innovation_stage(
        self,
        type_distribution: Dict[str, Any],
        university_ratio: float,
        total_patents: int
    ) -> tuple[str, str]:
        """
        Determine innovation stage based on assignee type distribution and patent volume.

        Args:
            type_distribution: Output from _calculate_assignee_type_distribution()
            university_ratio: Percentage of university assignees
            total_patents: Total number of patents

        Returns:
            Tuple of (stage, reasoning) where stage is one of:
            - "early_research": Dominated by academic research
            - "developing": Transitioning from academic to commercial
            - "commercialized": Corporate dominance with commercial adoption
        """
        percentages = type_distribution.get("type_percentages", {})
        corporate = percentages.get("Corporate", 0.0)
        academic_ratio = percentages.get("University", 0.0) + percentages.get("Research Institute", 0.0)

        # Early research stage: High university ratio (>40%) or low patent count with academic dominance
        if university_ratio > 40 or (total_patents < 50 and academic_ratio > 50):
            reasoning = (
                f"High university presence ({university_ratio:.1f}%) with {total_patents} total patents "
                f"indicates early research phase dominated by academic institutions"
            )
            return ("early_research", reasoning)

        # Commercialized stage: Corporate dominance (>70%) with low academic (<20%)
        if corporate > 70 and academic_ratio < 20:
            reasoning = (
                f"Corporate dominance ({corporate:.1f}%) with low academic presence ({academic_ratio:.1f}%) "
                f"indicates mature commercialization across {total_patents} patents"
            )
            return ("commercialized", reasoning)

        # Developing stage: Balanced mix or transition period
        reasoning = (
            f"Balanced distribution (academic: {academic_ratio:.1f}%, corporate: {corporate:.1f}%) "
            f"across {total_patents} patents indicates transition from research to commercial adoption"
        )
        return ("developing", reasoning)

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
            "source": "patentsview",
            "collected_at": collected_at,
            "keyword": keyword,
            "patents_2y": 0,
            "patents_5y": 0,
            "patents_10y": 0,
            "patents_total": 0,
            "unique_assignees": 0,
            "top_assignees": [],
            "assignee_type_distribution": {},
            "university_ratio": 0.0,
            "academic_ratio": 0.0,
            "commercialization_index": 0.0,
            "innovation_stage": "unknown",
            "innovation_stage_reasoning": "Insufficient data",
            "countries": {},
            "geographic_diversity": 0,
            "avg_citations_2y": 0.0,
            "avg_citations_5y": 0.0,
            "filing_velocity": 0.0,
            "assignee_concentration": "unknown",
            "geographic_reach": "unknown",
            "patent_maturity": "unknown",
            "patent_momentum": "unknown",
            "patent_trend": "unknown",
            "top_patents": [],
            "errors": errors + [error_msg]
        }
