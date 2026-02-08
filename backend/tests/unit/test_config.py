"""Unit tests for backend/config.py - Exposes MAX_RESULTS=0 bug"""
import pytest
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


def test_max_results_is_positive():
    """
    CRITICAL: Exposes MAX_RESULTS=0 bug in config.py:21

    This test is EXPECTED TO FAIL with the current configuration.
    MAX_RESULTS must be positive for ChromaDB to return search results.
    When MAX_RESULTS=0, ChromaDB returns empty results, causing "query failed".
    """
    from config import config

    assert config.MAX_RESULTS > 0, (
        f"MAX_RESULTS must be positive, got {config.MAX_RESULTS}. "
        f"Zero results cause ChromaDB to return empty search results."
    )


def test_config_has_required_attributes():
    """Verify config has all required attributes"""
    from config import config

    # Check required attributes exist
    assert hasattr(config, 'MAX_RESULTS')
    assert hasattr(config, 'CHUNK_SIZE')
    assert hasattr(config, 'CHUNK_OVERLAP')
    assert hasattr(config, 'ANTHROPIC_API_KEY')
    assert hasattr(config, 'ANTHROPIC_MODEL')


def test_chunk_size_is_reasonable():
    """Verify CHUNK_SIZE is reasonable for vector search"""
    from config import config

    # Chunk size should be between 100 and 10000 characters
    assert 100 <= config.CHUNK_SIZE <= 10000, (
        f"CHUNK_SIZE should be between 100 and 10000, got {config.CHUNK_SIZE}"
    )


def test_chunk_overlap_less_than_chunk_size():
    """Verify CHUNK_OVERLAP is less than CHUNK_SIZE"""
    from config import config

    assert config.CHUNK_OVERLAP < config.CHUNK_SIZE, (
        f"CHUNK_OVERLAP ({config.CHUNK_OVERLAP}) must be less than "
        f"CHUNK_SIZE ({config.CHUNK_SIZE})"
    )
