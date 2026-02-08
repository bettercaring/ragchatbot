"""Integration tests for error propagation through the RAG system"""
import pytest
from unittest.mock import MagicMock, patch
from rag_system import RAGSystem
from vector_store import SearchResults, VectorStore
from search_tools import CourseSearchTool


def test_error_flow_vector_store_to_tool(mocker):
    """
    Test error flow from VectorStore → CourseSearchTool

    Trace error propagation:
    1. VectorStore.search() raises exception
    2. SearchResults.error populated
    3. CourseSearchTool.execute() returns error string
    """
    # Mock VectorStore to return SearchResults with error
    # (real VectorStore.search() catches exceptions and returns SearchResults with error)
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults.empty("Search error: ChromaDB connection failed")

    # Create CourseSearchTool with mocked VectorStore
    tool = CourseSearchTool(mock_vector_store)

    # Execute search
    result = tool.execute(query="test query")

    # Assert: Error propagated from VectorStore to Tool
    assert "Search error" in result
    assert "ChromaDB connection failed" in result

    # Assert: No sources populated
    assert tool.last_sources == []


def test_error_flow_tool_to_tool_manager(mocker):
    """
    Test error flow from Tool → ToolManager

    Verify:
    1. Tool returns error string
    2. ToolManager passes error string through
    """
    from search_tools import ToolManager

    # Mock VectorStore returning error
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults.empty("Database error")

    # Create tool and register with manager
    tool = CourseSearchTool(mock_vector_store)
    manager = ToolManager()
    manager.register_tool(tool)

    # Execute tool via manager
    result = manager.execute_tool("search_course_content", query="test")

    # Assert: Error propagated through ToolManager
    assert "Database error" in result


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_error_flow_end_to_end(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_valid_max_results,
    mocker
):
    """
    Test full stack error tracing: VectorStore → Tool → ToolManager → AIGenerator → RAGSystem

    Simulate ChromaDB connection failure and trace error through entire system
    """
    # Mock VectorStore to return error SearchResults
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults.empty("ChromaDB connection timeout")
    mock_vector_store_class.return_value = mock_vector_store

    # Mock AIGenerator
    mock_ai_generator = mocker.MagicMock()

    # First response: AI calls search tool
    tool_use_block = mocker.MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "search_course_content"
    tool_use_block.input = {"query": "test query"}
    tool_use_block.id = "tool_error"

    first_response = mocker.MagicMock()
    first_response.content = [tool_use_block]
    first_response.stop_reason = "tool_use"

    # Second response: AI responds to error
    second_response = mocker.MagicMock()
    second_response.content = [
        mocker.MagicMock(
            text="I encountered an error accessing the course database. Please try again later.",
            type="text"
        )
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

    # Initialize RAGSystem
    rag_system = RAGSystem(config=config_with_valid_max_results)

    # Mock generate_response to simulate real error flow
    def mock_generate_response(query, conversation_history, tools, tool_manager):
        # Simulate tool execution that encounters error
        tool_result = tool_manager.execute_tool("search_course_content", query="test query")
        # tool_result should contain error message
        assert "ChromaDB connection timeout" in tool_result
        # AI responds to error
        return "I encountered an error accessing the course database. Please try again later."

    mock_ai_generator.generate_response = mock_generate_response

    # Execute query
    response, sources = rag_system.query("test query")

    # Assert: Error handled gracefully at RAGSystem level
    assert "error" in response.lower() or "try again" in response.lower()

    # Assert: No sources when error occurs
    assert sources == []


def test_search_results_error_propagation():
    """Test that SearchResults.empty() correctly creates error results"""
    # Create error results
    error_result = SearchResults.empty("Test error message")

    # Verify error properties
    assert error_result.is_empty()
    assert error_result.error == "Test error message"
    assert error_result.documents == []
    assert error_result.metadata == []
    assert error_result.distances == []


@patch('vector_store.chromadb.PersistentClient')
def test_vector_store_exception_handling(mock_client_class, mocker):
    """Test that VectorStore.search() catches exceptions and returns error SearchResults"""
    # Mock ChromaDB to raise exception
    mock_client = mocker.MagicMock()
    mock_collection = mocker.MagicMock()
    mock_collection.query.side_effect = Exception("Network timeout")

    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_class.return_value = mock_client

    # Create VectorStore
    vector_store = VectorStore(
        chroma_path="./test_chroma",
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    # Execute search
    result = vector_store.search("test query")

    # Assert: Exception caught and error SearchResults returned
    assert result.is_empty()
    assert result.error is not None
    assert "Search error" in result.error
    assert "Network timeout" in result.error


def test_course_search_tool_handles_error_results(mocker):
    """Test that CourseSearchTool correctly handles error SearchResults"""
    # Mock VectorStore returning error
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.search.return_value = SearchResults.empty("Vector database unavailable")

    # Create tool
    tool = CourseSearchTool(mock_vector_store)

    # Execute
    result = tool.execute(query="test")

    # Assert: Error message returned directly
    assert result == "Vector database unavailable"

    # Assert: last_sources empty
    assert tool.last_sources == []


def test_tool_manager_handles_missing_tool():
    """Test ToolManager error handling for non-existent tool"""
    from search_tools import ToolManager

    manager = ToolManager()

    # Try to execute non-existent tool
    result = manager.execute_tool("nonexistent_tool", query="test")

    # Assert: Meaningful error message
    assert "not found" in result
    assert "nonexistent_tool" in result


@patch('rag_system.DocumentProcessor')
@patch('rag_system.VectorStore')
@patch('rag_system.AIGenerator')
@patch('rag_system.SessionManager')
def test_multiple_tool_calls_with_mixed_results(
    mock_session_manager_class,
    mock_ai_generator_class,
    mock_vector_store_class,
    mock_doc_processor_class,
    config_with_valid_max_results,
    mocker
):
    """
    Test scenario where multiple tools are called and one returns error

    Verify:
    1. First tool returns valid results
    2. Second tool returns error
    3. AI receives both results
    4. System handles gracefully
    """
    # Mock VectorStore with alternating results
    mock_vector_store = mocker.MagicMock()

    # First call returns valid results
    # Second call returns error
    mock_vector_store.search.side_effect = [
        SearchResults(
            documents=["Valid content"],
            metadata=[{"course_title": "Test", "lesson_number": 1}],
            distances=[0.1]
        ),
        SearchResults.empty("Database connection lost")
    ]
    mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"
    mock_vector_store._resolve_course_name.return_value = "Test Course"
    mock_vector_store.get_all_courses_metadata.return_value = []

    mock_vector_store_class.return_value = mock_vector_store

    # Mock AIGenerator
    mock_ai_generator = mocker.MagicMock()

    # First response: AI calls two tools
    tool_use_1 = mocker.MagicMock()
    tool_use_1.type = "tool_use"
    tool_use_1.name = "search_course_content"
    tool_use_1.input = {"query": "test"}
    tool_use_1.id = "tool_1"

    tool_use_2 = mocker.MagicMock()
    tool_use_2.type = "tool_use"
    tool_use_2.name = "search_course_content"
    tool_use_2.input = {"query": "test2"}
    tool_use_2.id = "tool_2"

    first_response = mocker.MagicMock()
    first_response.content = [tool_use_1, tool_use_2]
    first_response.stop_reason = "tool_use"

    # Second response: AI synthesizes results despite error
    second_response = mocker.MagicMock()
    second_response.content = [
        mocker.MagicMock(
            text="Based on available information: Valid content. Note: Some data was unavailable.",
            type="text"
        )
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

    # Initialize RAGSystem
    rag_system = RAGSystem(config=config_with_valid_max_results)

    # Mock generate_response
    def mock_generate_response(query, conversation_history, tools, tool_manager):
        # Execute both tools
        result1 = tool_manager.execute_tool("search_course_content", query="test")
        result2 = tool_manager.execute_tool("search_course_content", query="test2")

        # First should succeed, second should have error
        assert "Valid content" in result1 or "[Test" in result1
        assert "Database connection lost" in result2

        return "Based on available information: Valid content. Note: Some data was unavailable."

    mock_ai_generator.generate_response = mock_generate_response

    # Execute query
    response, sources = rag_system.query("test query")

    # Assert: Response generated despite partial error
    assert len(response) > 0

    # Assert: Sources from successful tool call only
    assert len(sources) > 0  # Should have source from first tool call
