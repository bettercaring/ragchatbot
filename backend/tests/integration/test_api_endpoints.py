"""Integration tests for FastAPI endpoints in backend/app.py"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional
from unittest.mock import patch, MagicMock


# Define request/response models (same as in app.py)
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None


class SourceItem(BaseModel):
    """Individual source citation with optional link"""
    text: str
    url: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[SourceItem]
    session_id: str


class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]


@pytest.fixture
def test_app(mock_rag_system):
    """Create a test FastAPI app with mocked RAG system (no static file mounting)"""
    app = FastAPI(title="Test RAG System")

    # Use the mocked RAG system
    rag_system = mock_rag_system

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        try:
            # Create session if not provided
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()

            # Process query using RAG system
            answer, sources = rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Get course analytics and statistics"""
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def test_app_with_error(mock_rag_system_with_error):
    """Create a test FastAPI app that raises errors"""
    app = FastAPI(title="Test RAG System - Error")

    # Use the error-throwing mocked RAG system
    rag_system = mock_rag_system_with_error

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()

            answer, sources = rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Get course analytics and statistics"""
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI app"""
    return TestClient(test_app)


@pytest.fixture
def error_client(test_app_with_error):
    """Create a test client that will produce errors"""
    return TestClient(test_app_with_error)


# ===== /api/query endpoint tests =====

@pytest.mark.api
def test_query_endpoint_success_without_session(client, sample_query_request, mock_rag_system):
    """Test /api/query endpoint with successful query (no session_id provided)"""
    response = client.post("/api/query", json=sample_query_request)

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "answer" in data
    assert "sources" in data
    assert "session_id" in data

    # Verify content
    assert data["answer"] == "Variables in Python are used to store data. You can create a variable by assigning a value to a name."
    assert len(data["sources"]) == 2
    assert data["sources"][0]["text"] == "Python Basics - Lesson 1: Introduction to Variables"
    assert data["sources"][0]["url"] == "https://example.com/python-basics/lesson-1"
    assert data["session_id"] == "test-session-123"

    # Verify RAG system was called correctly
    mock_rag_system.session_manager.create_session.assert_called_once()
    mock_rag_system.query.assert_called_once_with("What are Python variables?", "test-session-123")


@pytest.mark.api
def test_query_endpoint_success_with_session(client, sample_query_request_with_session, mock_rag_system):
    """Test /api/query endpoint with existing session_id"""
    response = client.post("/api/query", json=sample_query_request_with_session)

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Check that existing session was used (not created new one)
    assert data["session_id"] == "existing-session-789"

    # Verify session was NOT created
    mock_rag_system.session_manager.create_session.assert_not_called()

    # Verify query was called with existing session
    mock_rag_system.query.assert_called_once_with("Tell me more about data types", "existing-session-789")


@pytest.mark.api
def test_query_endpoint_with_empty_query(client):
    """Test /api/query endpoint with empty query string"""
    response = client.post("/api/query", json={"query": "", "session_id": None})

    # Should still succeed (RAG system handles empty queries)
    assert response.status_code == 200


@pytest.mark.api
def test_query_endpoint_with_missing_query_field(client):
    """Test /api/query endpoint with missing required 'query' field"""
    response = client.post("/api/query", json={"session_id": "test-123"})

    # Should return 422 Unprocessable Entity (validation error)
    assert response.status_code == 422

    data = response.json()
    assert "detail" in data


@pytest.mark.api
def test_query_endpoint_with_invalid_json(client):
    """Test /api/query endpoint with malformed JSON"""
    response = client.post(
        "/api/query",
        data="invalid json{{{",
        headers={"Content-Type": "application/json"}
    )

    # Should return 422 Unprocessable Entity
    assert response.status_code == 422


@pytest.mark.api
def test_query_endpoint_internal_error(error_client, sample_query_request):
    """Test /api/query endpoint when RAG system raises an exception"""
    response = error_client.post("/api/query", json=sample_query_request)

    # Should return 500 Internal Server Error
    assert response.status_code == 500

    data = response.json()
    assert "detail" in data
    assert "Database connection error" in data["detail"]


# ===== /api/courses endpoint tests =====

@pytest.mark.api
def test_courses_endpoint_success(client, mock_rag_system):
    """Test /api/courses endpoint returns course statistics"""
    response = client.get("/api/courses")

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "total_courses" in data
    assert "course_titles" in data

    # Verify content
    assert data["total_courses"] == 1
    assert data["course_titles"] == ["Python Basics"]

    # Verify RAG system was called
    mock_rag_system.get_course_analytics.assert_called_once()


@pytest.mark.api
def test_courses_endpoint_internal_error(error_client):
    """Test /api/courses endpoint when RAG system raises an exception"""
    response = error_client.get("/api/courses")

    # Should return 500 Internal Server Error
    assert response.status_code == 500

    data = response.json()
    assert "detail" in data
    assert "Failed to retrieve analytics" in data["detail"]


@pytest.mark.api
def test_courses_endpoint_empty_database(client, mocker):
    """Test /api/courses endpoint when no courses are loaded"""
    # Create a new test app with empty analytics
    app = FastAPI(title="Test RAG System - Empty")

    mock_rag = mocker.MagicMock()
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 0,
        "course_titles": []
    }

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    test_client = TestClient(app)
    response = test_client.get("/api/courses")

    # Should succeed with empty data
    assert response.status_code == 200
    data = response.json()
    assert data["total_courses"] == 0
    assert data["course_titles"] == []


# ===== Response model validation tests =====

@pytest.mark.api
def test_query_response_model_validation(client, mock_rag_system):
    """Test that QueryResponse model properly validates response data"""
    # Mock RAG system to return sources without URL
    mock_rag_system.query.return_value = (
        "Test answer",
        [
            {"text": "Source without URL", "url": None},
            {"text": "Source with URL", "url": "https://example.com"}
        ]
    )

    response = client.post("/api/query", json={"query": "test query"})

    assert response.status_code == 200
    data = response.json()

    # Verify both sources are included (url is optional)
    assert len(data["sources"]) == 2
    assert data["sources"][0]["url"] is None
    assert data["sources"][1]["url"] == "https://example.com"


@pytest.mark.api
def test_query_response_with_no_sources(client, mock_rag_system):
    """Test query response when no sources are found"""
    # Mock RAG system to return empty sources
    mock_rag_system.query.return_value = (
        "I don't have specific information about that topic.",
        []
    )

    response = client.post("/api/query", json={"query": "unknown topic"})

    assert response.status_code == 200
    data = response.json()

    # Verify empty sources list
    assert data["sources"] == []
    assert "don't have specific information" in data["answer"]


# ===== HTTP method tests =====

@pytest.mark.api
def test_query_endpoint_get_method_not_allowed(client):
    """Test that /api/query does not accept GET requests"""
    response = client.get("/api/query")

    # Should return 405 Method Not Allowed or 404 (depends on FastAPI routing)
    assert response.status_code in [404, 405]


@pytest.mark.api
def test_courses_endpoint_post_method_not_allowed(client):
    """Test that /api/courses does not accept POST requests"""
    response = client.post("/api/courses", json={})

    # Should return 405 Method Not Allowed
    assert response.status_code == 405


# ===== Content-Type tests =====

@pytest.mark.api
def test_query_endpoint_requires_json_content_type(client):
    """Test that /api/query requires JSON content type"""
    response = client.post(
        "/api/query",
        data='{"query": "test"}',
        headers={"Content-Type": "text/plain"}
    )

    # Should return 422 Unprocessable Entity
    assert response.status_code == 422
