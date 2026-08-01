"""
GAT Project Management Module

Infrastructure for GAT including:
- User configuration management
- Project discovery
- Data storage (DuckDB backend - future)
"""

# Legacy discovery - commented out for v1.0 refactor
# from .discovery import ProjectDiscovery

from .manager import ProjectManager

__all__ = ["ProjectManager"]
