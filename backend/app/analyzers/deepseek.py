"""
DeepSeek API client and prompt engineering for Hype Cycle classification.
This module handles LLM integration for analyzing collected data.
"""
from typing import Dict, Any, List
import httpx
import json


class DeepSeekAnalyzer:
    """Client for DeepSeek API to classify technologies on Hype Cycle"""

    API_URL = "https://api.deepseek.com/v1/chat/completions"
    TIMEOUT = 60.0  # LLM calls can be slow

    # Valid hype cycle phases
    VALID_PHASES = [
        "innovation_trigger",
        "peak",
        "trough",
        "slope",
        "plateau"
    ]

    # Hype cycle phase definitions for prompts
    PHASE_DEFINITIONS = """
Hype Cycle Phases:
1. innovation_trigger (Innovation Trigger): New technology concept emerges, limited mentions/publications/patents, early adopters experimenting, low engagement/citations, narrow focus
2. peak (Peak of Inflated Expectations): Explosive growth in all metrics, very high social media buzz, rapid increase in publications/patents, mainstream media coverage begins, high sentiment/optimism, accelerating momentum
3. trough (Trough of Disillusionment): Declining mentions from peak levels, negative sentiment shift, publication/patent growth slows or reverses, media coverage drops, investor sentiment turns negative, reality check on limitations
4. slope (Slope of Enlightenment): Stabilizing metrics after trough, improving sentiment from lows, steady sustainable growth, maturing research and patents, practical applications emerge, institutional adoption begins
5. plateau (Plateau of Productivity): Sustained moderate activity, neutral sentiment (technology normalized), stable publication/patent rates, broad established field, mainstream adoption, mature market
"""

    def __init__(self, api_key: str):
        """
        Initialize DeepSeek analyzer.

        Args:
            api_key: DeepSeek API key

        Raises:
            ValueError: If API key is None or empty
        """
        if not api_key:
            raise ValueError("DeepSeek API key is required")
        self.api_key = api_key

    async def analyze(self, keyword: str, collector_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze collected data and classify technology on Hype Cycle.

        Performs two-stage analysis:
        1. Per-source analysis (5 LLM calls)
        2. Final synthesis (1 LLM call)

        Args:
            keyword: Technology keyword
            collector_data: Dict with keys "social", "papers", "patents", "news", "finance"

        Returns:
            {
                "phase": str,  # innovation_trigger, peak, trough, slope, plateau
                "confidence": float,  # 0-1
                "reasoning": str,
                "per_source_analyses": Dict[str, Any]  # Optional but valuable
            }

        Raises:
            Exception: If DeepSeek API calls fail
        """
        errors = []
        per_source_analyses = {}

        # Stage 1: Analyze each source independently
        source_names = ["social", "papers", "patents", "news", "finance"]
        for source_name in source_names:
            source_data = collector_data.get(source_name, {})
            if not source_data:
                errors.append(f"Missing {source_name} data")
                continue

            try:
                analysis = await self._analyze_source(source_name, source_data, keyword)
                per_source_analyses[source_name] = analysis
            except Exception as e:
                errors.append(f"Failed to analyze {source_name}: {str(e)}")

        # If too many sources failed, abort
        if len(per_source_analyses) < 3:
            raise Exception(f"Insufficient data for analysis. Errors: {errors}")

        # Stage 2: Synthesize all source analyses into final classification
        try:
            final_analysis = await self._synthesize_analyses(keyword, per_source_analyses)
            final_analysis["per_source_analyses"] = per_source_analyses
            if errors:
                final_analysis["errors"] = errors
            return final_analysis
        except Exception as e:
            raise Exception(f"Failed to synthesize analyses: {str(e)}")

    async def _analyze_source(
        self,
        source_name: str,
        source_data: Dict[str, Any],
        keyword: str
    ) -> Dict[str, Any]:
        """
        Analyze single data source using specialized prompt.

        Args:
            source_name: Name of source (social, papers, patents, news, finance)
            source_data: Data from that collector
            keyword: Technology keyword

        Returns:
            {"phase": str, "confidence": float, "reasoning": str}
        """
        prompt = self._build_source_prompt(source_name, source_data, keyword)
        result = await self._call_deepseek(prompt, temperature=0.3)
        return result

    async def _synthesize_analyses(
        self,
        keyword: str,
        per_source_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesize all source analyses into final classification.

        Args:
            keyword: Technology keyword
            per_source_results: Dict mapping source names to their analysis results

        Returns:
            {"phase": str, "confidence": float, "reasoning": str}
        """
        prompt = self._build_synthesis_prompt(keyword, per_source_results)
        result = await self._call_deepseek(prompt, temperature=0.3)
        return result

    def _build_source_prompt(
        self,
        source_name: str,
        source_data: Dict[str, Any],
        keyword: str
    ) -> str:
        """
        Build specialized prompt for each data source.

        Args:
            source_name: Name of source (social, papers, patents, news, finance)
            source_data: Data from that collector
            keyword: Technology keyword

        Returns:
            Prompt string for DeepSeek
        """
        if source_name == "social":
            return self._build_social_prompt(source_data, keyword)
        elif source_name == "papers":
            return self._build_papers_prompt(source_data, keyword)
        elif source_name == "patents":
            return self._build_patents_prompt(source_data, keyword)
        elif source_name == "news":
            return self._build_news_prompt(source_data, keyword)
        elif source_name == "finance":
            return self._build_finance_prompt(source_data, keyword)
        else:
            raise ValueError(f"Unknown source: {source_name}")

    def _build_social_prompt(self, data: Dict[str, Any], keyword: str) -> str:
        """Build prompt for social media (Hacker News) analysis"""
        return f"""You are analyzing social media signals from Hacker News to determine the hype cycle phase for "{keyword}".

Data provided:
- Mentions: 30d={data.get('mentions_30d', 0)}, 6m={data.get('mentions_6m', 0)}, 1y={data.get('mentions_1y', 0)}, total={data.get('mentions_total', 0)}
- Engagement: avg_points_30d={data.get('avg_points_30d', 0):.1f}, avg_comments_30d={data.get('avg_comments_30d', 0):.1f}
- Sentiment: {data.get('sentiment', 0):.2f} (range: -1.0 to 1.0)
- Trends: growth={data.get('growth_trend', 'unknown')}, momentum={data.get('momentum', 'unknown')}
- Recency: {data.get('recency', 'unknown')}

{self.PHASE_DEFINITIONS}

Interpretation guidance:
- innovation_trigger: Low mentions (<50 total), low engagement, early buzz
- peak: Very high mentions (>200 in 30d), high sentiment (>0.5), accelerating momentum
- trough: Declining mentions from previous peak, negative sentiment shift
- slope: Stabilizing mentions, improving sentiment, steady growth
- plateau: Sustained moderate volume, neutral sentiment (0.0-0.3), stable trend

Based on these social media signals, classify the hype cycle phase.

Return ONLY a JSON object with no markdown formatting:
{{"phase": "one of: innovation_trigger, peak, trough, slope, plateau", "confidence": 0.75, "reasoning": "1-2 sentence explanation"}}"""

    def _build_papers_prompt(self, data: Dict[str, Any], keyword: str) -> str:
        """Build prompt for research papers (Semantic Scholar) analysis"""
        return f"""You are analyzing academic research signals from Semantic Scholar for "{keyword}".

Data provided:
- Publications: 2y={data.get('publications_2y', 0)}, 5y={data.get('publications_5y', 0)}, total={data.get('publications_total', 0)}
- Citations: avg_2y={data.get('avg_citations_2y', 0):.1f}, avg_5y={data.get('avg_citations_5y', 0):.1f}
- Citation velocity: {data.get('citation_velocity', 0):.2f} (positive = accelerating citations)
- Research maturity: {data.get('research_maturity', 'unknown')}
- Research momentum: {data.get('research_momentum', 'unknown')}
- Research breadth: {data.get('research_breadth', 'unknown')}
- Author diversity: {data.get('author_diversity', 0)}
- Venue diversity: {data.get('venue_diversity', 0)}

{self.PHASE_DEFINITIONS}

Interpretation guidance:
- innovation_trigger: Emerging field (<10 papers in 2y), low citations (<5 avg), narrow breadth
- peak: Rapid publication growth, high momentum (accelerating), broad research, many authors
- trough: Declining publications, negative citation velocity, narrowing focus
- slope: Steady publications, mature field, moderate citations, improving velocity
- plateau: Stable publication rate, high citations, broad established field

Based on these academic signals, classify the hype cycle phase.

Return ONLY a JSON object with no markdown formatting:
{{"phase": "one of: innovation_trigger, peak, trough, slope, plateau", "confidence": 0.80, "reasoning": "1-2 sentence explanation"}}"""

    def _build_patents_prompt(self, data: Dict[str, Any], keyword: str) -> str:
        """Build prompt for patents (PatentsView) analysis"""
        return f"""You are analyzing patent filing signals from PatentsView for "{keyword}".

Data provided:
- Patent filings: 2y={data.get('patents_2y', 0)}, 5y={data.get('patents_5y', 0)}, 10y={data.get('patents_10y', 0)}, total={data.get('patents_total', 0)}
- Citations: avg_2y={data.get('avg_citations_2y', 0):.1f}, avg_5y={data.get('avg_citations_5y', 0):.1f}
- Filing velocity: {data.get('filing_velocity', 0):.2f} (positive = accelerating filings)
- Unique assignees: {data.get('unique_assignees', 0)}
- Assignee concentration: {data.get('assignee_concentration', 'unknown')}
- Geographic diversity: {data.get('geographic_diversity', 0)} countries
- Geographic reach: {data.get('geographic_reach', 'unknown')}
- Patent maturity: {data.get('patent_maturity', 'unknown')}
- Patent momentum: {data.get('patent_momentum', 'unknown')}

{self.PHASE_DEFINITIONS}

Interpretation guidance:
- innovation_trigger: Few patents (<10 in 2y), concentrated assignees (1-3 companies), domestic only
- peak: Rapid filing growth, many assignees (>20), global reach, accelerating momentum
- trough: Declining filings from peak, consolidation (fewer assignees), slowing velocity
- slope: Steady filings, maturing patents, diverse assignees, moderate citations
- plateau: Stable filing rate, established field, high citations, global coverage

Based on these patent signals, classify the hype cycle phase.

Return ONLY a JSON object with no markdown formatting:
{{"phase": "one of: innovation_trigger, peak, trough, slope, plateau", "confidence": 0.78, "reasoning": "1-2 sentence explanation"}}"""

    def _build_news_prompt(self, data: Dict[str, Any], keyword: str) -> str:
        """Build prompt for news coverage (GDELT) analysis"""
        return f"""You are analyzing news media coverage signals from GDELT for "{keyword}".

Data provided:
- Article counts: 30d={data.get('articles_30d', 0)}, 3m={data.get('articles_3m', 0)}, 1y={data.get('articles_1y', 0)}, total={data.get('articles_total', 0)}
- Unique domains: {data.get('unique_domains', 0)}
- Geographic diversity: {data.get('geographic_diversity', 0)} countries
- Average tone: {data.get('avg_tone', 0):.2f} (range: -1.0 to 1.0)
- Media attention: {data.get('media_attention', 'unknown')}
- Coverage trend: {data.get('coverage_trend', 'unknown')}
- Sentiment trend: {data.get('sentiment_trend', 'unknown')}
- Mainstream adoption: {data.get('mainstream_adoption', 'unknown')}

{self.PHASE_DEFINITIONS}

Interpretation guidance:
- innovation_trigger: Low coverage (<50 articles), niche media, few domains, limited geography
- peak: Very high coverage (>500 articles), mainstream media, many domains, positive tone, increasing trend
- trough: Declining coverage from peak, negative tone shift, decreasing trend
- slope: Stabilizing coverage, improving tone, steady trend, broadening media
- plateau: Sustained moderate coverage, neutral tone, stable trend, mainstream domains

Based on these news media signals, classify the hype cycle phase.

Return ONLY a JSON object with no markdown formatting:
{{"phase": "one of: innovation_trigger, peak, trough, slope, plateau", "confidence": 0.72, "reasoning": "1-2 sentence explanation"}}"""

    def _build_finance_prompt(self, data: Dict[str, Any], keyword: str) -> str:
        """Build prompt for financial market (Yahoo Finance) analysis"""
        return f"""You are analyzing financial market signals from Yahoo Finance for "{keyword}".

Data provided:
- Companies found: {data.get('companies_found', 0)}
- Total market cap: ${data.get('total_market_cap', 0):,.0f}
- Average market cap: ${data.get('avg_market_cap', 0):,.0f}
- Price changes: 1m={data.get('avg_price_change_1m', 0):.1f}%, 6m={data.get('avg_price_change_6m', 0):.1f}%, 2y={data.get('avg_price_change_2y', 0):.1f}%
- Volatility: 1m={data.get('avg_volatility_1m', 0):.1f}%, 6m={data.get('avg_volatility_6m', 0):.1f}%
- Volume trend: {data.get('volume_trend', 'unknown')}
- Market maturity: {data.get('market_maturity', 'unknown')}
- Investor sentiment: {data.get('investor_sentiment', 'unknown')}
- Investment momentum: {data.get('investment_momentum', 'unknown')}

{self.PHASE_DEFINITIONS}

Interpretation guidance:
- innovation_trigger: Few companies (<3), small market cap (<$10B total), high volatility (>30%)
- peak: Many companies (>10), large market cap, strong positive returns, high volatility, accelerating momentum, positive sentiment
- trough: Declining returns from peak, negative price changes, very high volatility, negative sentiment
- slope: Stabilizing returns, improving sentiment, moderate volatility, steady momentum, developing maturity
- plateau: Stable moderate returns, neutral sentiment, low volatility (<15%), mature market

Based on these financial market signals, classify the hype cycle phase.

Return ONLY a JSON object with no markdown formatting:
{{"phase": "one of: innovation_trigger, peak, trough, slope, plateau", "confidence": 0.76, "reasoning": "1-2 sentence explanation"}}"""

    def _build_synthesis_prompt(
        self,
        keyword: str,
        per_source_results: Dict[str, Any]
    ) -> str:
        """
        Build synthesis prompt from all source analyses.

        Args:
            keyword: Technology keyword
            per_source_results: Dict mapping source names to their analysis results

        Returns:
            Synthesis prompt string
        """
        # Build source summaries
        source_summaries = []
        source_order = ["social", "papers", "patents", "news", "finance"]
        source_labels = {
            "social": "Social Media (Hacker News)",
            "papers": "Academic Research (Semantic Scholar)",
            "patents": "Patents (PatentsView)",
            "news": "News Coverage (GDELT)",
            "finance": "Financial Markets (Yahoo Finance)"
        }

        for i, source in enumerate(source_order, 1):
            if source in per_source_results:
                result = per_source_results[source]
                summary = f"""{i}. {source_labels[source]}:
   Phase: {result.get('phase', 'unknown')}
   Confidence: {result.get('confidence', 0):.2f}
   Reasoning: {result.get('reasoning', 'N/A')}"""
                source_summaries.append(summary)

        sources_text = "\n\n".join(source_summaries)

        return f"""You are an expert technology analyst synthesizing multiple data sources to determine the definitive hype cycle position for "{keyword}".

You have analyzed this technology from {len(per_source_results)} independent perspectives:

{sources_text}

{self.PHASE_DEFINITIONS}

Synthesize these perspectives into ONE final classification. Consider:
- Conflicting signals may indicate transition phases
- Weight sources by confidence scores
- Social media trends faster than academic validation
- Patents and finance lag behind hype but indicate real investment
- News coverage bridges mainstream adoption
- Recent data (social, news) vs. slower indicators (papers, patents)

Return ONLY a JSON object with no markdown formatting:
{{"phase": "one of: innovation_trigger, peak, trough, slope, plateau", "confidence": 0.85, "reasoning": "2-3 sentence explanation synthesizing key evidence from all sources"}}"""

    async def _call_deepseek(
        self,
        prompt: str,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Make HTTP call to DeepSeek API and parse JSON response.

        Args:
            prompt: The prompt to send
            temperature: Sampling temperature (0.0-1.0, lower = more deterministic)

        Returns:
            Parsed JSON response with phase, confidence, reasoning

        Raises:
            httpx.HTTPStatusError: For HTTP errors (401, 429, etc.)
            httpx.TimeoutException: For request timeouts
            json.JSONDecodeError: For invalid JSON responses
            ValueError: For invalid response structure
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                self.API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Strip markdown code blocks (pattern from FinanceCollector)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            # Parse JSON
            parsed = json.loads(content)

            # Validate response structure
            required_fields = ["phase", "confidence", "reasoning"]
            if not all(field in parsed for field in required_fields):
                raise ValueError(f"DeepSeek response missing required fields. Got: {list(parsed.keys())}")

            # Validate phase
            if parsed["phase"] not in self.VALID_PHASES:
                raise ValueError(f"Invalid phase '{parsed['phase']}'. Must be one of: {self.VALID_PHASES}")

            # Validate confidence
            confidence = parsed["confidence"]
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ValueError(f"Confidence must be float between 0-1. Got: {confidence}")

            return parsed
