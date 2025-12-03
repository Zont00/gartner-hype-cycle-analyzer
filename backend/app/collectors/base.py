"""
Base collector interface for data collection modules.
Each collector will implement this interface to gather data from different sources.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseCollector(ABC):
    """Abstract base class for all data collectors"""

    @abstractmethod
    async def collect(self, keyword: str, expanded_terms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Collect data for the given keyword, optionally with expanded search terms.

        Args:
            keyword: Technology keyword to analyze
            expanded_terms: Optional list of 3-5 related search terms for query expansion.
                          When provided, collector should search for keyword OR any expanded term.

        Returns:
            Dictionary containing collected metrics
        """
        pass
