"""
Analysis router for Gartner Hype Cycle classification endpoints.

This module provides the HTTP API endpoints for analyzing technology keywords
and classifying them on the Gartner Hype Cycle.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from app.database import get_db
from app.analyzers.hype_classifier import HypeCycleClassifier
import aiosqlite
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """Request model for technology analysis endpoint."""

    keyword: str = Field(
        ...,  # Required field
        min_length=1,
        max_length=100,
        description="Technology keyword to analyze (e.g., 'quantum computing')",
        examples=["quantum computing", "blockchain", "artificial intelligence"]
    )

    @field_validator('keyword')
    @classmethod
    def strip_keyword(cls, v: str) -> str:
        """Strip whitespace from keyword."""
        return v.strip()


class AnalyzeResponse(BaseModel):
    """Response model for technology analysis endpoint."""

    keyword: str = Field(description="Technology keyword analyzed")
    phase: str = Field(description="Hype cycle phase (innovation_trigger, peak, trough, slope, plateau)")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence score (0-1)")
    reasoning: str = Field(description="LLM-generated explanation for the classification")
    timestamp: str = Field(description="Analysis timestamp (ISO 8601 format)")
    cache_hit: bool = Field(description="Whether this result was served from cache")
    expires_at: str = Field(description="Cache expiration timestamp (ISO 8601 format)")
    per_source_analyses: Dict[str, Any] = Field(description="Individual source classifications")
    collector_data: Dict[str, Any] = Field(description="Raw data from all collectors")
    collectors_succeeded: int = Field(ge=0, le=5, description="Number of collectors that succeeded")
    partial_data: bool = Field(description="Whether analysis was performed with partial data (<5 collectors)")
    errors: List[str] = Field(description="Error messages from failed collectors or analysis")
    query_expansion_applied: bool = Field(description="Whether query expansion was used for this analysis")
    expanded_terms: List[str] = Field(description="List of expanded search terms used (empty if no expansion)")


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze technology on Gartner Hype Cycle",
    description="""
    Analyze a technology keyword and classify it on the Gartner Hype Cycle.

    Returns cached result if available (cache TTL: 24 hours by default).
    Otherwise, runs full analysis pipeline:
    - Collects data from 5 parallel sources (social media, research papers, patents, news, finance)
    - Performs two-stage LLM classification via DeepSeek
    - Caches result for future requests

    Requires minimum 3 of 5 collectors to succeed for analysis.
    """,
    responses={
        200: {
            "description": "Successful analysis (cache hit or fresh)",
            "content": {
                "application/json": {
                    "example": {
                        "keyword": "quantum computing",
                        "phase": "peak",
                        "confidence": 0.82,
                        "reasoning": "Strong signals across all sources indicate peak hype...",
                        "timestamp": "2025-12-02T10:30:45.123456",
                        "cache_hit": False,
                        "expires_at": "2025-12-03T10:30:45.123456",
                        "per_source_analyses": {
                            "social": {"phase": "peak", "confidence": 0.85, "reasoning": "..."},
                            "papers": {"phase": "peak", "confidence": 0.78, "reasoning": "..."}
                        },
                        "collector_data": {
                            "social": {"mentions_30d": 245, "sentiment": 0.72},
                            "papers": {"publications_2y": 156, "avg_citations_2y": 23.4}
                        },
                        "collectors_succeeded": 5,
                        "partial_data": False,
                        "errors": []
                    }
                }
            }
        },
        422: {
            "description": "Request validation failed (invalid keyword format)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "keyword"],
                                "msg": "Field required",
                                "type": "missing"
                            }
                        ]
                    }
                }
            }
        },
        500: {
            "description": "Internal server error (database failures, DeepSeek errors)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Analysis failed: DeepSeek API error: 401 Unauthorized"
                    }
                }
            }
        },
        503: {
            "description": "Service unavailable (insufficient data from collectors)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Insufficient data: only 2/5 collectors succeeded. Minimum 3 required. Errors: ['social collector failed: timeout', 'papers collector failed: rate limit']"
                    }
                }
            }
        }
    }
)
async def analyze_technology(
    request: AnalyzeRequest,
    db: aiosqlite.Connection = Depends(get_db)
) -> AnalyzeResponse:
    """
    Analyze a technology keyword and classify it on the Gartner Hype Cycle.

    Args:
        request: AnalyzeRequest with validated keyword field
        db: Database connection (injected via dependency)

    Returns:
        AnalyzeResponse with complete classification result

    Raises:
        HTTPException(503): Insufficient data (<3 collectors succeeded)
        HTTPException(500): Unexpected errors (database, DeepSeek API, etc.)
    """
    try:
        # Instantiate classifier (reads settings internally)
        classifier = HypeCycleClassifier()

        # Run classification (cache-first, then parallel collectors + DeepSeek)
        result = await classifier.classify(request.keyword, db)

        # Result dict matches AnalyzeResponse schema, return directly
        return result

    except Exception as e:
        error_message = str(e)

        # Check if this is an insufficient data error (temporary condition)
        if "Insufficient data" in error_message:
            logger.warning(f"Insufficient data for keyword '{request.keyword}': {error_message}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_message
            )

        # Unexpected error (database, DeepSeek API, etc.)
        logger.exception(f"Analysis failed for keyword '{request.keyword}': {error_message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {error_message}"
        )
