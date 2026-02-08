"""Unit tests for backend/search_tools.py - CourseSearchTool and ToolManager"""
import pytest
from unittest.mock import MagicMock
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


def test_execute_with_zero_results_from_vector_store(mock_vector_store_empty):
    """
    Test CourseSearchTool.execute() with empty SearchResults
    This simulates the MAX_RESULTS=0 bug scenario
    """
    tool = CourseSearchTool(mock_vector_store_empty)

    # Execute search
    result = tool.execute(query="What are Python variables?")

    # Assert: Tool returns "No relevant content found"
    assert "No relevant content found" in result
    assert tool.last_sources == []


def test_execute_with_valid_results(mock_vector_store_with_data):
    """Test CourseSearchTool.execute() with populated SearchResults"""
    tool = CourseSearchTool(mock_vector_store_with_data)

    # Execute search
    result = tool.execute(query="What are Python variables?")

    # Assert: Formatted output contains course title and lesson info
    assert "Python Basics" in result
    assert "Lesson 1" in result
    assert "Variables in Python" in result

    # Assert: last_sources populated with source metadata
    assert len(tool.last_sources) > 0
    assert tool.last_sources[0]["text"] == "Python Basics - Lesson 1"


def test_execute_with_error_from_vector_store(mock_vector_store_with_error):
    """Test CourseSearchTool error propagation"""
    tool = CourseSearchTool(mock_vector_store_with_error)

    # Execute search
    result = tool.execute(query="test query")

    # Assert: Error message returned directly
    assert "Database connection error" in result
    assert tool.last_sources == []


def test_execute_with_course_filter(mocker):
    """Test CourseSearchTool with course_name parameter"""
    mock_store = mocker.MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Content from Python course"],
        metadata=[{"course_title": "Python Basics", "lesson_number": 1}],
        distances=[0.1]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson-1"

    tool = CourseSearchTool(mock_store)

    # Execute with course filter
    result = tool.execute(query="variables", course_name="Python")

    # Assert: search() called with course_name
    mock_store.search.assert_called_once_with(
        query="variables",
        course_name="Python",
        lesson_number=None
    )
    assert "Python Basics" in result


def test_execute_with_lesson_filter(mocker):
    """Test CourseSearchTool with lesson_number parameter"""
    mock_store = mocker.MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=["Lesson 2 content"],
        metadata=[{"course_title": "Python Basics", "lesson_number": 2}],
        distances=[0.1]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/lesson-2"

    tool = CourseSearchTool(mock_store)

    # Execute with lesson filter
    result = tool.execute(query="control flow", lesson_number=2)

    # Assert: search() called with lesson_number
    mock_store.search.assert_called_once_with(
        query="control flow",
        course_name=None,
        lesson_number=2
    )
    assert "Lesson 2" in result


def test_format_results_with_lesson_links(mocker):
    """Test _format_results() method formats output correctly"""
    mock_store = mocker.MagicMock()
    mock_store.get_lesson_link.side_effect = [
        "https://example.com/lesson-1",
        "https://example.com/lesson-2"
    ]

    tool = CourseSearchTool(mock_store)

    # Create SearchResults with multiple documents
    results = SearchResults(
        documents=[
            "Content from lesson 1",
            "Content from lesson 2"
        ],
        metadata=[
            {"course_title": "Python Basics", "lesson_number": 1, "chunk_index": 0},
            {"course_title": "Python Basics", "lesson_number": 2, "chunk_index": 0}
        ],
        distances=[0.1, 0.2]
    )

    # Format results
    formatted = tool._format_results(results)

    # Verify header format: [Course Title - Lesson N]
    assert "[Python Basics - Lesson 1]" in formatted
    assert "[Python Basics - Lesson 2]" in formatted

    # Verify source tracking with lesson links
    assert len(tool.last_sources) == 2
    assert tool.last_sources[0]["text"] == "Python Basics - Lesson 1"
    assert tool.last_sources[0]["url"] == "https://example.com/lesson-1"
    assert tool.last_sources[1]["text"] == "Python Basics - Lesson 2"
    assert tool.last_sources[1]["url"] == "https://example.com/lesson-2"


def test_format_results_without_lesson_number(mocker):
    """Test _format_results() when lesson_number is None"""
    mock_store = mocker.MagicMock()

    tool = CourseSearchTool(mock_store)

    # Create SearchResults without lesson numbers
    results = SearchResults(
        documents=["General course content"],
        metadata=[{"course_title": "Python Basics", "chunk_index": 0}],
        distances=[0.1]
    )

    # Format results
    formatted = tool._format_results(results)

    # Verify: No lesson number in header
    assert "[Python Basics]" in formatted
    assert "Lesson" not in formatted

    # Verify: Source has no lesson number
    assert tool.last_sources[0]["text"] == "Python Basics"
    assert tool.last_sources[0]["url"] is None


def test_get_tool_definition():
    """Test CourseSearchTool.get_tool_definition() returns correct schema"""
    mock_store = MagicMock()
    tool = CourseSearchTool(mock_store)

    definition = tool.get_tool_definition()

    # Verify structure
    assert definition["name"] == "search_course_content"
    assert "description" in definition
    assert "input_schema" in definition

    # Verify parameters
    schema = definition["input_schema"]
    assert "query" in schema["properties"]
    assert "course_name" in schema["properties"]
    assert "lesson_number" in schema["properties"]
    assert schema["required"] == ["query"]


def test_tool_manager_register_tool(mocker):
    """Test ToolManager.register_tool() registers tools"""
    manager = ToolManager()
    mock_store = mocker.MagicMock()
    tool = CourseSearchTool(mock_store)

    # Register tool
    manager.register_tool(tool)

    # Assert: Tool is registered
    assert "search_course_content" in manager.tools


def test_tool_manager_get_tool_definitions(mocker):
    """Test ToolManager.get_tool_definitions() returns all definitions"""
    manager = ToolManager()
    mock_store = mocker.MagicMock()

    tool1 = CourseSearchTool(mock_store)
    tool2 = CourseOutlineTool(mock_store)

    manager.register_tool(tool1)
    manager.register_tool(tool2)

    # Get definitions
    definitions = manager.get_tool_definitions()

    # Assert: All tools included
    assert len(definitions) == 2
    tool_names = [d["name"] for d in definitions]
    assert "search_course_content" in tool_names
    assert "get_course_outline" in tool_names


def test_tool_manager_execute_tool_success(mock_vector_store_with_data):
    """Test ToolManager.execute_tool() executes registered tool"""
    manager = ToolManager()
    tool = CourseSearchTool(mock_vector_store_with_data)
    manager.register_tool(tool)

    # Execute tool
    result = manager.execute_tool(
        "search_course_content",
        query="What are variables?"
    )

    # Assert: Tool executed successfully
    assert "Python Basics" in result
    assert len(result) > 0


def test_tool_manager_execute_tool_not_found():
    """Test ToolManager.execute_tool() handles missing tool"""
    manager = ToolManager()

    # Execute non-existent tool
    result = manager.execute_tool("nonexistent_tool", query="test")

    # Assert: Error message returned
    assert "not found" in result


def test_tool_manager_get_last_sources(mock_vector_store_with_data):
    """Test ToolManager.get_last_sources() retrieves sources from tools"""
    manager = ToolManager()
    tool = CourseSearchTool(mock_vector_store_with_data)
    manager.register_tool(tool)

    # Execute search to populate sources
    manager.execute_tool("search_course_content", query="variables")

    # Get sources
    sources = manager.get_last_sources()

    # Assert: Sources retrieved
    assert len(sources) > 0
    assert "text" in sources[0]
    assert "url" in sources[0]


def test_tool_manager_get_last_sources_empty():
    """Test ToolManager.get_last_sources() returns empty list when no sources"""
    manager = ToolManager()
    mock_store = MagicMock()
    tool = CourseSearchTool(mock_store)
    manager.register_tool(tool)

    # Get sources without executing any search
    sources = manager.get_last_sources()

    # Assert: Empty list
    assert sources == []


def test_tool_manager_reset_sources(mock_vector_store_with_data):
    """Test ToolManager.reset_sources() clears sources after retrieval"""
    manager = ToolManager()
    tool = CourseSearchTool(mock_vector_store_with_data)
    manager.register_tool(tool)

    # Execute search and verify sources exist
    manager.execute_tool("search_course_content", query="variables")
    assert len(manager.get_last_sources()) > 0

    # Reset sources
    manager.reset_sources()

    # Assert: Sources cleared
    assert manager.get_last_sources() == []
    assert tool.last_sources == []


def test_course_outline_tool_get_definition():
    """Test CourseOutlineTool.get_tool_definition() returns correct schema"""
    mock_store = MagicMock()
    tool = CourseOutlineTool(mock_store)

    definition = tool.get_tool_definition()

    # Verify structure
    assert definition["name"] == "get_course_outline"
    assert "description" in definition
    assert definition["input_schema"]["required"] == ["course_name"]


def test_course_outline_tool_execute(mocker):
    """Test CourseOutlineTool.execute() retrieves and formats course outline"""
    mock_store = mocker.MagicMock()

    # Mock course resolution
    mock_store._resolve_course_name.return_value = "Python Basics"

    # Mock course metadata
    mock_store.get_all_courses_metadata.return_value = [
        {
            "title": "Python Basics",
            "instructor": "John Doe",
            "course_link": "https://example.com/python",
            "lessons": [
                {"lesson_number": 1, "lesson_title": "Lesson 1", "lesson_link": "https://example.com/lesson-1"},
                {"lesson_number": 2, "lesson_title": "Lesson 2", "lesson_link": "https://example.com/lesson-2"}
            ]
        }
    ]

    tool = CourseOutlineTool(mock_store)

    # Execute outline retrieval
    result = tool.execute(course_name="Python")

    # Assert: Formatted outline contains course info
    assert "Python Basics" in result
    assert "John Doe" in result
    assert "Lesson 1" in result
    assert "Lesson 2" in result
    assert "Total Lessons: 2" in result

    # Assert: Source tracking
    assert len(tool.last_sources) == 1
    assert tool.last_sources[0]["text"] == "Python Basics"
