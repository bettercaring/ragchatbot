"""Shared fixtures for all tests"""
import pytest
import sys
from pathlib import Path
from typing import List, Dict
from unittest.mock import Mock, MagicMock

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from models import Course, Lesson, CourseChunk
from vector_store import SearchResults


@pytest.fixture
def sample_course() -> Course:
    """Mock Course object with 2 lessons"""
    return Course(
        title="Python Basics",
        course_link="https://example.com/python-basics",
        instructor="John Doe",
        lessons=[
            Lesson(
                lesson_number=1,
                title="Introduction to Variables",
                lesson_link="https://example.com/python-basics/lesson-1"
            ),
            Lesson(
                lesson_number=2,
                title="Control Flow",
                lesson_link="https://example.com/python-basics/lesson-2"
            )
        ]
    )


@pytest.fixture
def sample_course_chunks() -> List[CourseChunk]:
    """Mock CourseChunk objects"""
    return [
        CourseChunk(
            content="Variables in Python are used to store data. You can create a variable by assigning a value to a name.",
            course_title="Python Basics",
            lesson_number=1,
            chunk_index=0
        ),
        CourseChunk(
            content="Python supports different data types including integers, floats, strings, and booleans.",
            course_title="Python Basics",
            lesson_number=1,
            chunk_index=1
        ),
        CourseChunk(
            content="Control flow statements like if, elif, and else allow you to make decisions in your code.",
            course_title="Python Basics",
            lesson_number=2,
            chunk_index=0
        )
    ]


@pytest.fixture
def mock_vector_store_empty(mocker):
    """VectorStore returning empty results (simulates MAX_RESULTS=0)"""
    mock_store = mocker.MagicMock()
    mock_store.search.return_value = SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )
    return mock_store


@pytest.fixture
def mock_vector_store_with_data(mocker, sample_course_chunks):
    """VectorStore returning valid results"""
    mock_store = mocker.MagicMock()

    # Create metadata matching the sample chunks
    metadata = [
        {
            "course_title": "Python Basics",
            "lesson_number": 1,
            "chunk_index": 0,
            "lesson_link": "https://example.com/python-basics/lesson-1"
        },
        {
            "course_title": "Python Basics",
            "lesson_number": 1,
            "chunk_index": 1,
            "lesson_link": "https://example.com/python-basics/lesson-1"
        },
        {
            "course_title": "Python Basics",
            "lesson_number": 2,
            "chunk_index": 0,
            "lesson_link": "https://example.com/python-basics/lesson-2"
        }
    ]

    mock_store.search.return_value = SearchResults(
        documents=[chunk.content for chunk in sample_course_chunks],
        metadata=metadata,
        distances=[0.1, 0.2, 0.3]
    )
    return mock_store


@pytest.fixture
def mock_vector_store_with_error(mocker):
    """VectorStore returning error SearchResults"""
    mock_store = mocker.MagicMock()
    mock_store.search.return_value = SearchResults.empty("Database connection error")
    return mock_store


@pytest.fixture
def mock_anthropic_client(mocker):
    """Mock Anthropic API responses"""
    mock_client = mocker.MagicMock()

    # Default response without tool use
    mock_response = mocker.MagicMock()
    mock_response.content = [
        mocker.MagicMock(
            type="text",
            text="This is a test response from the AI."
        )
    ]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = mocker.MagicMock(input_tokens=100, output_tokens=50)

    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def config_with_zero_max_results(mocker):
    """Config with MAX_RESULTS=0 (buggy)"""
    mock_config = mocker.MagicMock()
    mock_config.MAX_RESULTS = 0
    mock_config.CHUNK_SIZE = 1000
    mock_config.CHUNK_OVERLAP = 200
    return mock_config


@pytest.fixture
def config_with_valid_max_results(mocker):
    """Config with MAX_RESULTS=5 (fixed)"""
    mock_config = mocker.MagicMock()
    mock_config.MAX_RESULTS = 5
    mock_config.CHUNK_SIZE = 1000
    mock_config.CHUNK_OVERLAP = 200
    return mock_config
