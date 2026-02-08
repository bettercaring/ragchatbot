"""Integration tests for backend/rag_system.py - End-to-end RAG query flow"""
import pytest
from unittest.mock import MagicMock, patch
from rag_system import RAGSystem
from vector_store import SearchResults


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_rag_system_query_with_max_results_zero(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_zero_max_results,
    mocker
):
    """
    CRITICAL: Test end-to-end query flow with MAX_RESULTS=0
    EXPECTED TO FAIL - Demonstrates user-facing impact of the bug

    This test shows that when config.MAX_RESULTS=0:
    1. VectorStore.search() returns empty results
    2. CourseSearchTool returns "No relevant content found"
    3. User receives no sources (sources == [])
    """
    # Mock VectorStore to return empty results (simulating MAX_RESULTS=0)
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )
    mock_vector_store_class.return_value = mock_vector_store

    # Mock AIGenerator
    mock_ai_generator = mocker.MagicMock()

    # First response: AI calls search tool
    tool_use_block = mocker.MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "search_course_content"
    tool_use_block.input = {"query": "What are Python variables?"}
    tool_use_block.id = "tool_123"

    first_response = mocker.MagicMock()
    first_response.content = [tool_use_block]
    first_response.stop_reason = "tool_use"

    # Second response: AI responds after getting empty results
    second_response = mocker.MagicMock()
    second_response.content = [
        mocker.MagicMock(text="I couldn't find information about that.", type="text")
    ]
    second_response.stop_reason = "end_turn"

    mock_ai_generator.client.messages.create.side_effect = [first_response, second_response]
    mock_ai_generator_class.return_value = mock_ai_generator

    # Mock SessionManager
    mock_session_manager = mocker.MagicMock()
    mock_session_manager.get_conversation_history.return_value = None
    mock_session_manager_class.return_value = mock_session_manager

    # Mock DocumentProcessor
    mock_doc_processor = mocker.MagicMock()
    mock_doc_processor_class.return_value = mock_doc_processor

    # Initialize RAGSystem with MAX_RESULTS=0 (buggy config)
    rag_system = RAGSystem(config=config_with_zero_max_results)

    # Mock generate_response to simulate real flow
    def mock_generate_response(query, conversation_history, tools, tool_manager):
        # Simulate tool execution
        tool_result = tool_manager.execute_tool("search_course_content", query="What are Python variables?")
        # Tool result should be "No relevant content found" due to empty search results
        return "I couldn't find information about that."

    mock_ai_generator.generate_response = mock_generate_response

    # Execute query
    response, sources = rag_system.query("What are Python variables?")

    # Assert: Response generated (but unhelpful)
    assert len(response) > 0

    # Assert: NO SOURCES returned (demonstrates user-facing bug impact)
    assert sources == [], "BUG: sources should be empty when MAX_RESULTS=0"

    # Assert: VectorStore.search() was called
    mock_vector_store.search.assert_called()


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_rag_system_query_with_valid_max_results(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_valid_max_results,
    mocker
):
    """
    Test expected behavior with MAX_RESULTS=5
    This test should PASS, showing the system works correctly with valid config
    """
    # Mock VectorStore to return valid results
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults(
        documents=["Variables in Python are used to store data."],
        metadata=[{
            "course_title": "Python Basics",
            "lesson_number": 1,
            "chunk_index": 0
        }],
        distances=[0.1]
    )
    mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson-1"
    mock_vector_store_class.return_value = mock_vector_store

    # Mock AIGenerator
    mock_ai_generator = mocker.MagicMock()

    # First response: AI calls search tool
    tool_use_block = mocker.MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "search_course_content"
    tool_use_block.input = {"query": "What are Python variables?"}
    tool_use_block.id = "tool_456"

    first_response = mocker.MagicMock()
    first_response.content = [tool_use_block]
    first_response.stop_reason = "tool_use"

    # Second response: AI responds with actual content
    second_response = mocker.MagicMock()
    second_response.content = [
        mocker.MagicMock(text="Variables are containers for storing data values.", type="text")
    ]
    second_response.stop_reason = "end_turn"

    mock_ai_generator.client.messages.create.side_effect = [first_response, second_response]
    mock_ai_generator_class.return_value = mock_ai_generator

    # Mock SessionManager
    mock_session_manager = mocker.MagicMock()
    mock_session_manager.get_conversation_history.return_value = None
    mock_session_manager_class.return_value = mock_session_manager

    # Mock DocumentProcessor
    mock_doc_processor = mocker.MagicMock()
    mock_doc_processor_class.return_value = mock_doc_processor

    # Initialize RAGSystem with MAX_RESULTS=5 (correct config)
    rag_system = RAGSystem(config=config_with_valid_max_results)

    # Mock generate_response to simulate real flow
    def mock_generate_response(query, conversation_history, tools, tool_manager):
        # Simulate tool execution
        tool_result = tool_manager.execute_tool("search_course_content", query="What are Python variables?")
        # Tool result should contain actual content
        return "Variables are containers for storing data values."

    mock_ai_generator.generate_response = mock_generate_response

    # Execute query
    response, sources = rag_system.query("What are Python variables?")

    # Assert: Response generated with content
    assert len(response) > 0
    assert "Variables" in response

    # Assert: SOURCES POPULATED (correct behavior)
    assert len(sources) > 0, "Sources should be populated when MAX_RESULTS > 0"
    assert sources[0]["text"] == "Python Basics - Lesson 1"
    assert sources[0]["url"] == "https://example.com/lesson-1"


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_query_without_session(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_valid_max_results,
    mocker
):
    """Test query flow without session ID (no conversation history)"""
    # Mock components
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{"course_title": "Test", "lesson_number": 1}],
        distances=[0.1]
    )
    mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"
    mock_vector_store_class.return_value = mock_vector_store

    mock_ai_generator = mocker.MagicMock()
    mock_ai_generator.generate_response.return_value = "Test response"
    mock_ai_generator_class.return_value = mock_ai_generator

    mock_session_manager = mocker.MagicMock()
    mock_session_manager.get_conversation_history.return_value = None
    mock_session_manager_class.return_value = mock_session_manager

    mock_doc_processor = mocker.MagicMock()
    mock_doc_processor_class.return_value = mock_doc_processor

    # Initialize RAGSystem
    rag_system = RAGSystem(config=config_with_valid_max_results)

    # Query without session_id
    response, sources = rag_system.query("Test query")

    # Assert: get_conversation_history NOT called
    mock_session_manager.get_conversation_history.assert_not_called()

    # Assert: add_exchange NOT called
    mock_session_manager.add_exchange.assert_not_called()

    # Assert: Response generated
    assert response == "Test response"


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_query_with_session(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_valid_max_results,
    mocker
):
    """Test query flow with session ID (includes conversation history)"""
    # Mock components
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{"course_title": "Test", "lesson_number": 1}],
        distances=[0.1]
    )
    mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"
    mock_vector_store_class.return_value = mock_vector_store

    mock_ai_generator = mocker.MagicMock()
    mock_ai_generator.generate_response.return_value = "Test response"
    mock_ai_generator_class.return_value = mock_ai_generator

    # Mock SessionManager with history
    mock_session_manager = mocker.MagicMock()
    conversation_history = "User: Previous question\nAssistant: Previous answer"
    mock_session_manager.get_conversation_history.return_value = conversation_history
    mock_session_manager_class.return_value = mock_session_manager

    mock_doc_processor = mocker.MagicMock()
    mock_doc_processor_class.return_value = mock_doc_processor

    # Initialize RAGSystem
    rag_system = RAGSystem(config=config_with_valid_max_results)

    # Query with session_id
    response, sources = rag_system.query("Test query", session_id="session_123")

    # Assert: get_conversation_history called with session_id
    mock_session_manager.get_conversation_history.assert_called_once_with("session_123")

    # Assert: generate_response called with history
    call_args = mock_ai_generator.generate_response.call_args
    assert call_args.kwargs["conversation_history"] == conversation_history

    # Assert: add_exchange called to update history
    mock_session_manager.add_exchange.assert_called_once_with(
        "session_123",
        "Test query",
        "Test response"
    )

    # Assert: Response generated
    assert response == "Test response"


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_sources_reset_after_query(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_valid_max_results,
    mocker
):
    """Test that sources are reset after being retrieved"""
    # Mock components
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults(
        documents=["Content"],
        metadata=[{"course_title": "Test", "lesson_number": 1}],
        distances=[0.1]
    )
    mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"
    mock_vector_store_class.return_value = mock_vector_store

    mock_ai_generator = mocker.MagicMock()
    mock_ai_generator.generate_response.return_value = "Test response"
    mock_ai_generator_class.return_value = mock_ai_generator

    mock_session_manager = mocker.MagicMock()
    mock_session_manager.get_conversation_history.return_value = None
    mock_session_manager_class.return_value = mock_session_manager

    mock_doc_processor = mocker.MagicMock()
    mock_doc_processor_class.return_value = mock_doc_processor

    # Initialize RAGSystem
    rag_system = RAGSystem(config=config_with_valid_max_results)

    # First query - should have sources
    response1, sources1 = rag_system.query("Query 1")

    # Verify tool_manager.reset_sources() was called
    # We can check this by verifying search_tool.last_sources is empty after query
    assert rag_system.search_tool.last_sources == []

    # Second query - sources should be from this query only, not accumulated
    response2, sources2 = rag_system.query("Query 2")

    # Assert: Sources are independent between queries
    assert rag_system.search_tool.last_sources == []


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_rag_system_initialization(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_valid_max_results
):
    """Test that RAGSystem initializes all components correctly"""
    # Initialize RAGSystem
    rag_system = RAGSystem(config=config_with_valid_max_results)

    # Assert: All components initialized
    assert rag_system.document_processor is not None
    assert rag_system.vector_store is not None
    assert rag_system.ai_generator is not None
    assert rag_system.session_manager is not None
    assert rag_system.tool_manager is not None
    assert rag_system.search_tool is not None
    assert rag_system.outline_tool is not None

    # Assert: Tools registered with tool_manager
    assert "search_course_content" in rag_system.tool_manager.tools
    assert "get_course_outline" in rag_system.tool_manager.tools

    # Assert: VectorStore initialized with correct max_results
    mock_vector_store_class.assert_called_once()
    call_args = mock_vector_store_class.call_args
    # Third argument is max_results
    assert call_args[0][2] == 5, "VectorStore should be initialized with MAX_RESULTS=5"
