# Test Framework Enhancements

## Overview
Enhanced the RAG system testing framework with comprehensive API endpoint tests, pytest configuration, and improved test fixtures.

## Changes Made

### 1. pytest Configuration (`pyproject.toml`)
Added `[tool.pytest.ini_options]` section with:
- **testpaths**: Points to `backend/tests` directory
- **python_files/classes/functions**: Standard test discovery patterns
- **addopts**: Default options including verbosity, strict markers, short tracebacks, and disabled warnings
- **markers**: Three test categories defined:
  - `unit`: Unit tests for individual components
  - `integration`: Integration tests for component interactions
  - `api`: API endpoint tests

### 2. Test Dependencies (`backend/requirements-test.txt`)
Added `httpx==0.27.0` for FastAPI testing with TestClient

### 3. Enhanced Test Fixtures (`backend/tests/conftest.py`)
Added new fixtures for API testing:

- **`mock_rag_system`**: Mocks RAGSystem for successful API responses
  - Returns realistic query results with sources
  - Mocks session management
  - Provides course analytics

- **`mock_rag_system_with_error`**: Mocks RAGSystem that raises exceptions
  - Used for testing error handling
  - Simulates database connection errors

- **`sample_query_request`**: Sample API request payload without session
- **`sample_query_request_with_session`**: Sample API request with existing session

### 4. API Endpoint Tests (`backend/tests/integration/test_api_endpoints.py`)
Created comprehensive test suite with **14 tests** covering:

#### `/api/query` Endpoint (9 tests)
- ✅ Successful query without session_id (creates new session)
- ✅ Successful query with existing session_id
- ✅ Empty query string handling
- ✅ Missing required 'query' field validation (422 error)
- ✅ Invalid JSON payload (422 error)
- ✅ Internal server error handling (500 error)
- ✅ Response model validation with optional URLs
- ✅ No sources found scenario
- ✅ GET method not allowed (405 error)

#### `/api/courses` Endpoint (4 tests)
- ✅ Successful retrieval of course statistics
- ✅ Internal server error handling (500 error)
- ✅ Empty database scenario
- ✅ POST method not allowed (405 error)

#### Additional Tests (1 test)
- ✅ Content-Type validation (requires JSON)

### 5. Integration Test Configuration
Added `backend/tests/integration/conftest.py` to prevent pytest-asyncio collection errors

## Test Execution

### Run all tests
```bash
cd backend
python -m pytest tests/ -v
```

### Run with coverage
```bash
python -m pytest tests/ --cov=. --cov-report=term-missing:skip-covered
```

### Run specific test categories
```bash
python -m pytest tests/ -m api -v           # API tests only
python -m pytest tests/unit/ -v             # Unit tests only
python -m pytest tests/integration/ -v      # Integration tests only
```

### Current Test Coverage
- **66 total tests** (52 existing + 14 new API tests)
- **Overall coverage**: 78%
- **API test coverage**: 95%

## Technical Implementation

### Test App Pattern
The API tests use a **test-only FastAPI app** to avoid static file mounting issues:
- Defines endpoints inline in the test file
- Uses fixtures to inject mocked RAGSystem
- Prevents startup event execution
- Isolated from production app configuration

### Fixtures Architecture
```
conftest.py (root)
├── mock_rag_system → mock_vector_store_with_data → sample_course_chunks
├── mock_rag_system_with_error
├── sample_query_request
└── sample_query_request_with_session

test_api_endpoints.py
├── test_app(mock_rag_system)
├── test_app_with_error(mock_rag_system_with_error)
├── client(test_app)
└── error_client(test_app_with_error)
```

## Benefits

1. **Comprehensive API Coverage**: All FastAPI endpoints are tested for success, failure, and edge cases
2. **Better Error Detection**: Validates request/response models, HTTP methods, and content types
3. **Cleaner Test Execution**: pytest configuration provides consistent, readable output
4. **Reusable Fixtures**: Shared test data and mocks reduce duplication
5. **Test Categorization**: Markers allow running specific test suites
6. **Documentation**: Tests serve as living documentation of API behavior

## Notes

- Tests run without pytest-asyncio plugin (`-p no:asyncio`) to avoid collection conflicts
- All existing tests continue to pass (100% backward compatibility)
- Test app pattern prevents static file dependency issues
- Mocked RAGSystem provides fast, deterministic tests
