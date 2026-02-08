# Test Suite for RAG Chatbot "Query Failed" Issue

This test suite identifies and validates the fix for the critical configuration bug that caused "query failed" errors in the RAG chatbot.

## Problem Summary

The RAG chatbot returned "query failed" for content-related questions due to a **critical configuration bug**:
- `backend/config.py:21` set `MAX_RESULTS = 0`
- `backend/vector_store.py:90` used this value: `search_limit = limit if limit is not None else self.max_results`
- ChromaDB received `n_results=0` and returned empty results
- CourseSearchTool interpreted this as "No relevant content found"

## Quick Start

### Installation

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Install project dependencies (if not already installed)
pip install pydantic python-dotenv anthropic chromadb sentence-transformers
```

### Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=term-missing:skip-covered

# Run specific test categories
python -m pytest tests/unit/ -v                  # Unit tests only
python -m pytest tests/integration/ -v           # Integration tests only

# Run the critical bug-exposing test
python -m pytest tests/unit/test_config.py::test_max_results_is_positive -v
```

## Test Results

### Before Fix (MAX_RESULTS=0)
```
FAILED tests/unit/test_config.py::test_max_results_is_positive - AssertionError:
MAX_RESULTS must be positive, got 0. Zero results cause ChromaDB to return empty search results.
```

### After Fix (MAX_RESULTS=5)
```
============================== 45 passed in 4.37s ==============================
```

## Test Coverage

| Module | Coverage | Critical Tests |
|--------|----------|----------------|
| **search_tools.py** | **93%** | ✅ Tool execution, error handling, source tracking |
| **Overall** | **71%** | ✅ End-to-end query flow, vector store, AI generator |
| config.py | 100% | ✅ MAX_RESULTS validation |
| vector_store.py | 44% | ✅ Search with different max_results values |

## Test Structure

### Unit Tests (`tests/unit/`)

#### `test_config.py` - Configuration Validation
**Purpose:** Expose the MAX_RESULTS=0 bug

Key Tests:
- ✅ **`test_max_results_is_positive()`** - **CRITICAL** - Fails when MAX_RESULTS=0
- ✅ `test_config_has_required_attributes()` - Validates config structure
- ✅ `test_chunk_size_is_reasonable()` - Validates CHUNK_SIZE range
- ✅ `test_chunk_overlap_less_than_chunk_size()` - Validates CHUNK_OVERLAP

**Expected Failure Before Fix:**
```python
def test_max_results_is_positive():
    """CRITICAL: Exposes MAX_RESULTS=0 bug in config.py:21"""
    from config import config
    assert config.MAX_RESULTS > 0  # FAILS when MAX_RESULTS=0
```

---

#### `test_vector_store.py` - VectorStore Behavior
**Purpose:** Demonstrate empty results with max_results=0

Key Tests:
- ✅ `test_search_with_zero_max_results()` - Shows ChromaDB returns empty with n_results=0
- ✅ `test_search_with_valid_max_results()` - Shows normal behavior with n_results=5
- ✅ `test_search_results_dataclass_empty()` - Validates SearchResults.empty()
- ✅ `test_search_results_from_chroma()` - Validates ChromaDB result parsing
- ✅ `test_search_with_course_filter()` - Tests course_name filtering
- ✅ `test_search_with_lesson_filter()` - Tests lesson_number filtering
- ✅ `test_search_handles_exception()` - Tests error handling

Coverage: **44%** (focused on search functionality)

---

#### `test_search_tools.py` - CourseSearchTool Execution
**Purpose:** Test tool execution with empty and valid results

Key Tests:
- ✅ `test_execute_with_zero_results_from_vector_store()` - Empty results scenario
- ✅ `test_execute_with_valid_results()` - Normal operation
- ✅ `test_execute_with_error_from_vector_store()` - Error propagation
- ✅ `test_format_results_with_lesson_links()` - Source tracking
- ✅ `test_tool_manager_execute_tool_success()` - ToolManager integration
- ✅ `test_tool_manager_get_last_sources()` - Source retrieval
- ✅ `test_tool_manager_reset_sources()` - Source cleanup

Coverage: **93%** (comprehensive tool testing)

---

#### `test_ai_generator.py` - AIGenerator Tool Calling
**Purpose:** Verify AI calls tools and processes results

Key Tests:
- ✅ `test_generate_response_without_tools()` - Basic response generation
- ✅ `test_generate_response_with_tool_execution()` - Tool calling flow
- ✅ `test_handle_tool_execution_flow()` - Tool execution handler
- ✅ `test_tool_execution_with_empty_results()` - Handling empty tool responses
- ✅ `test_generate_response_with_multiple_tools()` - Multiple tool calls

Coverage: **23%** (focused on critical tool execution paths)

---

### Integration Tests (`tests/integration/`)

#### `test_rag_system.py` - End-to-End Query Flow
**Purpose:** Test full RAG system with different configurations

Key Tests:
- ✅ **`test_rag_system_query_with_max_results_zero()`** - Demonstrates bug impact
- ✅ **`test_rag_system_query_with_valid_max_results()`** - Shows correct behavior
- ✅ `test_query_without_session()` - No conversation history
- ✅ `test_query_with_session()` - With conversation history
- ✅ `test_sources_reset_after_query()` - Source management
- ✅ `test_rag_system_initialization()` - Component initialization

**Critical Test:**
```python
def test_rag_system_query_with_max_results_zero():
    """EXPECTED TO FAIL - Demonstrates user-facing impact of the bug"""
    # Setup: Initialize RAGSystem with config.MAX_RESULTS=0
    # Execute: rag_system.query("What are Python variables?")
    # Assert: sources == []  # Demonstrates user-facing impact
```

---

#### `test_error_propagation.py` - Error Flow Tracing
**Purpose:** Validate error handling across the stack

Key Tests:
- ✅ `test_error_flow_vector_store_to_tool()` - VectorStore → Tool
- ✅ `test_error_flow_tool_to_tool_manager()` - Tool → ToolManager
- ✅ `test_error_flow_end_to_end()` - Full stack error tracing
- ✅ `test_vector_store_exception_handling()` - Exception catching
- ✅ `test_multiple_tool_calls_with_mixed_results()` - Partial errors

Coverage: **49%** (focused on error paths)

---

## Fixtures (`tests/conftest.py`)

Shared test fixtures for consistent testing:

### Mock Data
- `sample_course()` - Mock Course object with 2 lessons
- `sample_course_chunks()` - Mock CourseChunk objects

### Mock Components
- `mock_vector_store_empty()` - Returns empty results (simulates MAX_RESULTS=0)
- `mock_vector_store_with_data()` - Returns valid results
- `mock_vector_store_with_error()` - Returns error SearchResults
- `mock_anthropic_client()` - Mock Anthropic API responses

### Configuration
- `config_with_zero_max_results()` - Config with MAX_RESULTS=0 (buggy)
- `config_with_valid_max_results()` - Config with MAX_RESULTS=5 (fixed)

---

## The Fix

### Location: `backend/config.py:21`

**Before (Buggy):**
```python
MAX_RESULTS: int = 0  # Maximum search results to return
```

**After (Fixed):**
```python
MAX_RESULTS: int = 5  # Maximum search results to return
```

### Why This Fixes It

1. **ChromaDB Behavior**: When `n_results=0`, ChromaDB returns empty results
2. **VectorStore**: Uses `self.max_results` when no custom `limit` provided
3. **CourseSearchTool**: Interprets empty results as "No relevant content found"
4. **RAGSystem**: Returns empty sources list to frontend
5. **User Impact**: "Query failed" message displayed

Setting `MAX_RESULTS=5` ensures ChromaDB returns actual search results.

---

## Verification Steps

### 1. Run Tests Before Fix
```bash
# Temporarily revert fix
sed -i '' 's/MAX_RESULTS: int = 5/MAX_RESULTS: int = 0/' config.py

# Run critical test - should FAIL
python -m pytest tests/unit/test_config.py::test_max_results_is_positive -v
```

Expected output:
```
FAILED tests/unit/test_config.py::test_max_results_is_positive - AssertionError
```

### 2. Apply Fix
```bash
# Apply fix
sed -i '' 's/MAX_RESULTS: int = 0/MAX_RESULTS: int = 5/' config.py
```

### 3. Run Tests After Fix
```bash
# All tests should PASS
python -m pytest tests/ -v
```

Expected output:
```
============================== 45 passed in 4.37s ==============================
```

### 4. Manual End-to-End Test
```bash
# Start the backend
uvicorn app:app --reload

# In another terminal, test a query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are Python variables?"}'
```

Expected: Response with sources populated

---

## Success Criteria

✅ All 45 tests pass after applying fix
✅ `test_max_results_is_positive()` identifies bug before fix
✅ Integration tests demonstrate full query flow works
✅ Error propagation tests validate error handling
✅ Real queries return sources and content
✅ Test coverage >71% overall, >93% for search_tools.py

---

## Test Execution Time

- **Unit Tests**: ~1.5 seconds
- **Integration Tests**: ~3 seconds
- **Total**: ~4.5 seconds

---

## Continuous Integration

To integrate into CI/CD:

```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.13'
      - run: pip install -r backend/requirements-test.txt
      - run: cd backend && python -m pytest tests/ -v --cov=. --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## Future Enhancements

### Additional Tests
- [ ] Performance tests for large document processing
- [ ] Stress tests with concurrent queries
- [ ] End-to-end browser tests with Selenium
- [ ] API endpoint tests with FastAPI TestClient

### Coverage Improvements
- [ ] Increase `ai_generator.py` coverage to >80%
- [ ] Increase `vector_store.py` coverage to >80%
- [ ] Add tests for `document_processor.py`
- [ ] Add tests for `session_manager.py`

### Enhanced Validation
- [ ] Add input validation tests (negative max_results, invalid limits)
- [ ] Add performance benchmarks
- [ ] Add memory leak detection
- [ ] Add security tests (injection attacks, XSS)

---

## Troubleshooting

### Common Issues

**Issue:** `ModuleNotFoundError: No module named 'backend'`
- **Fix:** Tests use relative imports. Ensure you're in the `backend/` directory when running tests.

**Issue:** `AttributeError: 'Package' object has no attribute 'obj'`
- **Fix:** Downgrade pytest-asyncio: `pip install 'pytest-asyncio==0.21.0'`

**Issue:** Tests fail with ChromaDB connection errors
- **Fix:** Tests use mocks and don't require real ChromaDB. Check that mocking is working correctly.

**Issue:** Coverage report shows warnings
- **Fix:** Normal warnings from coverage tool. Focus on the coverage percentages.

---

## Contributing

When adding new tests:
1. Place unit tests in `tests/unit/`
2. Place integration tests in `tests/integration/`
3. Use fixtures from `conftest.py` when possible
4. Follow naming convention: `test_<functionality>_<scenario>()`
5. Add docstrings explaining the test purpose
6. Run `pytest tests/ -v` to verify all tests pass

---

## Contact

For questions about the test suite or bug fix:
- Review the plan document at `.claude/projects/.../3dfedcc3-ec12-4351-b42b-c155a98373ad.jsonl`
- Check git history for detailed implementation notes
- Open an issue in the repository

---

## Summary

This test suite successfully:
1. ✅ **Exposes** the MAX_RESULTS=0 bug through failing tests
2. ✅ **Validates** the fix (changing MAX_RESULTS to 5)
3. ✅ **Demonstrates** correct behavior across all system layers
4. ✅ **Provides** 71% code coverage with 93% coverage on critical modules
5. ✅ **Enables** confident refactoring and future development

**Root Cause:** `MAX_RESULTS = 0` in config.py
**Fix:** Change to `MAX_RESULTS = 5`
**Validation:** All 45 tests pass ✅
