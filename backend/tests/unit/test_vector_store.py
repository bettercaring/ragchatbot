"""Unit tests for backend/vector_store.py - VectorStore behavior with different max_results"""
import pytest
from unittest.mock import MagicMock, patch
from vector_store import VectorStore, SearchResults


def test_search_results_dataclass_empty():
    """Test SearchResults.empty() creates empty results with error"""
    result = SearchResults.empty("Test error message")

    assert result.is_empty()
    assert result.error == "Test error message"
    assert result.documents == []
    assert result.metadata == []
    assert result.distances == []


def test_search_results_dataclass_is_empty():
    """Test SearchResults.is_empty() correctly identifies empty results"""
    # Empty results
    empty_result = SearchResults(documents=[], metadata=[], distances=[])
    assert empty_result.is_empty()

    # Non-empty results
    non_empty_result = SearchResults(
        documents=["Some content"],
        metadata=[{"key": "value"}],
        distances=[0.5]
    )
    assert not non_empty_result.is_empty()


def test_search_results_from_chroma():
    """Test SearchResults.from_chroma() correctly parses ChromaDB results"""
    chroma_results = {
        'documents': [['doc1', 'doc2']],
        'metadatas': [[{'key1': 'value1'}, {'key2': 'value2'}]],
        'distances': [[0.1, 0.2]]
    }

    result = SearchResults.from_chroma(chroma_results)

    assert result.documents == ['doc1', 'doc2']
    assert result.metadata == [{'key1': 'value1'}, {'key2': 'value2'}]
    assert result.distances == [0.1, 0.2]
    assert result.error is None


def test_search_results_from_chroma_empty():
    """Test SearchResults.from_chroma() handles empty ChromaDB results"""
    chroma_results = {
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]]
    }

    result = SearchResults.from_chroma(chroma_results)

    assert result.is_empty()
    assert result.documents == []
    assert result.metadata == []
    assert result.distances == []


@patch('vector_store.chromadb.PersistentClient')
def test_search_with_zero_max_results(mock_client_class, mocker):
    """
    CRITICAL: Demonstrate empty results with max_results=0

    This test shows that when VectorStore is initialized with max_results=0,
    ChromaDB receives n_results=0 and returns empty results.
    """
    # Mock ChromaDB client and collection
    mock_client = MagicMock()
    mock_collection = MagicMock()

    # Configure mock to return empty results (simulating ChromaDB with n_results=0)
    mock_collection.query.return_value = {
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]]
    }

    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_class.return_value = mock_client

    # Initialize VectorStore with max_results=0 (buggy configuration)
    vector_store = VectorStore(
        chroma_path="./test_chroma",
        embedding_model="all-MiniLM-L6-v2",
        max_results=0  # BUG: This causes ChromaDB to return empty results
    )

    # Perform search
    results = vector_store.search("What are Python variables?")

    # Assert: ChromaDB was called with n_results=0
    mock_collection.query.assert_called_once()
    call_args = mock_collection.query.call_args
    assert call_args.kwargs['n_results'] == 0, "ChromaDB should receive n_results=0"

    # Assert: Results are empty
    assert results.is_empty(), "Results should be empty when max_results=0"
    assert len(results.documents) == 0


@patch('vector_store.chromadb.PersistentClient')
def test_search_with_valid_max_results(mock_client_class, mocker):
    """Test normal behavior with max_results=5"""
    # Mock ChromaDB client and collection
    mock_client = MagicMock()
    mock_collection = MagicMock()

    # Configure mock to return valid results
    mock_collection.query.return_value = {
        'documents': [['doc1', 'doc2', 'doc3']],
        'metadatas': [[
            {'course_title': 'Python Basics', 'lesson_number': 1},
            {'course_title': 'Python Basics', 'lesson_number': 1},
            {'course_title': 'Python Basics', 'lesson_number': 2}
        ]],
        'distances': [[0.1, 0.2, 0.3]]
    }

    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_class.return_value = mock_client

    # Initialize VectorStore with max_results=5 (correct configuration)
    vector_store = VectorStore(
        chroma_path="./test_chroma",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    # Perform search
    results = vector_store.search("What are Python variables?")

    # Assert: ChromaDB was called with n_results=5
    mock_collection.query.assert_called_once()
    call_args = mock_collection.query.call_args
    assert call_args.kwargs['n_results'] == 5, "ChromaDB should receive n_results=5"

    # Assert: Results are populated
    assert not results.is_empty(), "Results should not be empty"
    assert len(results.documents) == 3


@patch('vector_store.chromadb.PersistentClient')
def test_search_with_custom_limit(mock_client_class, mocker):
    """Test that custom limit parameter overrides max_results"""
    # Mock ChromaDB client and collection
    mock_client = MagicMock()
    mock_collection = MagicMock()

    mock_collection.query.return_value = {
        'documents': [['doc1', 'doc2']],
        'metadatas': [[{'key': 'value'}, {'key': 'value'}]],
        'distances': [[0.1, 0.2]]
    }

    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_class.return_value = mock_client

    # Initialize with max_results=5
    vector_store = VectorStore(
        chroma_path="./test_chroma",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    # Search with custom limit=10
    results = vector_store.search("test query", limit=10)

    # Assert: ChromaDB receives the custom limit, not max_results
    call_args = mock_collection.query.call_args
    assert call_args.kwargs['n_results'] == 10


@patch('vector_store.chromadb.PersistentClient')
def test_search_with_course_filter(mock_client_class, mocker):
    """Test course_name filtering"""
    # Mock ChromaDB client and collections
    mock_client = MagicMock()
    mock_catalog = MagicMock()
    mock_content = MagicMock()

    # Mock course catalog query (for course resolution)
    mock_catalog.query.return_value = {
        'documents': [['Python Basics']],
        'metadatas': [[{'title': 'Python Basics'}]],
        'distances': [[0.0]]
    }

    # Mock content query
    mock_content.query.return_value = {
        'documents': [['filtered content']],
        'metadatas': [[{'course_title': 'Python Basics', 'lesson_number': 1}]],
        'distances': [[0.1]]
    }

    # Return different collections for different names
    def get_or_create_collection(name, embedding_function=None):
        if name == "course_catalog":
            return mock_catalog
        return mock_content

    mock_client.get_or_create_collection.side_effect = get_or_create_collection
    mock_client_class.return_value = mock_client

    # Initialize VectorStore
    vector_store = VectorStore(
        chroma_path="./test_chroma",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    # Search with course filter
    results = vector_store.search("test query", course_name="Python")

    # Assert: Content collection was queried with course filter
    call_args = mock_content.query.call_args
    assert call_args.kwargs['where'] == {'course_title': 'Python Basics'}
    assert not results.is_empty()


@patch('vector_store.chromadb.PersistentClient')
def test_search_with_lesson_filter(mock_client_class, mocker):
    """Test lesson_number filtering"""
    # Mock ChromaDB client and collection
    mock_client = MagicMock()
    mock_collection = MagicMock()

    mock_collection.query.return_value = {
        'documents': [['lesson content']],
        'metadatas': [[{'course_title': 'Python Basics', 'lesson_number': 2}]],
        'distances': [[0.1]]
    }

    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_class.return_value = mock_client

    # Initialize VectorStore
    vector_store = VectorStore(
        chroma_path="./test_chroma",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    # Search with lesson filter
    results = vector_store.search("test query", lesson_number=2)

    # Assert: ChromaDB was queried with lesson filter
    call_args = mock_collection.query.call_args
    assert call_args.kwargs['where'] == {'lesson_number': 2}


@patch('vector_store.chromadb.PersistentClient')
def test_search_handles_exception(mock_client_class, mocker):
    """Test that search() handles exceptions gracefully"""
    # Mock ChromaDB client and collection
    mock_client = MagicMock()
    mock_collection = MagicMock()

    # Make query raise an exception
    mock_collection.query.side_effect = Exception("Database connection error")

    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_class.return_value = mock_client

    # Initialize VectorStore
    vector_store = VectorStore(
        chroma_path="./test_chroma",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    # Search should not raise, but return error SearchResults
    results = vector_store.search("test query")

    # Assert: Error is captured in SearchResults
    assert results.is_empty()
    assert results.error is not None
    assert "Search error" in results.error
    assert "Database connection error" in results.error
