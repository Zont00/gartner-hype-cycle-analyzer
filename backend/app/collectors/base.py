"""
Base collector interface for data collection modules.
Each collector will implement this interface to gather data from different sources.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseCollector(ABC):
    """Abstract base class for all data collectors"""

    @abstractmethod
    async def collect(self, keyword: str) -> Dict[str, Any]:
        """
        Collect data for the given keyword.

        Args:
            keyword: Technology keyword to analyze

        Returns:
            Dictionary containing collected metrics
        """
        pass
