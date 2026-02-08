# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Retrieval-Augmented Generation (RAG) chatbot system that enables users to query course materials and receive AI-powered responses. The system uses ChromaDB for vector storage, Anthropic's Claude API for generation, and provides a web interface for interaction.

**Stack**: Python 3.13, FastAPI, ChromaDB, Anthropic Claude API, Sentence Transformers, vanilla JavaScript frontend

## Development Setup

### Install dependencies
```bash
# Install uv package manager if not installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### Environment configuration
Create a `.env` file in the root directory with:
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Run the application
```bash
# Quick start
./run.sh

# Or manually
cd backend
uv run uvicorn app:app --reload --port 8000
```

Access at `http://localhost:8000` (web UI) or `http://localhost:8000/docs` (API docs)

## Testing

### Run tests
```bash
cd backend

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=term-missing:skip-covered

# Run specific test categories
python -m pytest tests/unit/ -v           # Unit tests only
python -m pytest tests/integration/ -v    # Integration tests only
```

### Test dependencies
```bash
cd backend
pip install -r requirements-test.txt
```

## Architecture

### Core Components Flow

The system follows a tool-based RAG architecture where the AI decides when to search for information:

```
User Query → RAGSystem.query() → AIGenerator → Tool Manager → Vector Store
                                       ↓
                                 Response with sources
```

### Key Modules

**`backend/rag_system.py`** - Main orchestrator
- Initializes all components (VectorStore, AIGenerator, ToolManager, SessionManager)
- Handles document ingestion (`add_course_document`, `add_course_folder`)
- Processes queries via `query()` method
- Manages conversation sessions and returns structured responses with sources

**`backend/ai_generator.py`** - Claude API interface
- Handles Anthropic API calls with tool support
- Implements sequential tool calling (up to 2 rounds)
- Key method: `generate_response()` with tool execution handling
- `_handle_tool_execution()` manages multi-round tool interactions

**`backend/search_tools.py`** - Tool definitions and execution
- `Tool` abstract base class for all tools
- `CourseSearchTool` - Searches course content with semantic matching and filtering
- `CourseOutlineTool` - Retrieves complete course structure and lessons
- `ToolManager` - Registers tools, provides definitions to AI, executes tools, tracks sources

**`backend/vector_store.py`** - ChromaDB wrapper
- Two collections: `course_catalog` (metadata) and `course_content` (chunks)
- Main entry: `search()` with semantic course name resolution
- Handles course name fuzzy matching via `_resolve_course_name()`
- Returns structured `SearchResults` dataclass

**`backend/models.py`** - Pydantic data models
- `Course` - Course metadata with lessons
- `Lesson` - Individual lesson with optional link
- `CourseChunk` - Text chunk for vector storage

**`backend/document_processor.py`** - Document parsing
- Processes course documents into structured `Course` and `CourseChunk` objects
- Handles chunking with configurable size and overlap

**`backend/session_manager.py`** - Conversation history
- Manages conversation sessions with rolling history window
- Provides context for follow-up questions

**`backend/config.py`** - Configuration
- All system settings in a single `Config` dataclass
- **CRITICAL**: `MAX_RESULTS` must be > 0 (bug was `MAX_RESULTS = 0` causing empty results)

**`backend/app.py`** - FastAPI application
- `/api/query` - Main query endpoint (POST)
- `/api/courses` - Course analytics (GET)
- Serves static frontend files
- Loads initial documents on startup

### Tool-Based RAG Pattern

The system uses a **tool-based** approach rather than direct RAG:

1. User asks a question
2. AI receives question + tool definitions
3. AI decides which tool(s) to call (if any)
4. Tools execute and return results
5. AI synthesizes results into response
6. Sources are extracted from tool results

This allows:
- AI to handle general questions without searching
- AI to search specific courses or lessons when needed
- AI to get course outlines before searching specific content
- Sequential tool calling for complex queries (2 rounds max)

### Data Model

**Course Structure:**
```
Course
├── title (unique identifier)
├── course_link (optional URL)
├── instructor (optional)
└── lessons []
    ├── lesson_number (1, 2, 3...)
    ├── title
    └── lesson_link (optional URL)
```

**Vector Storage:**
- Course metadata stored in `course_catalog` collection (searchable by title)
- Content chunks stored in `course_content` collection with metadata:
  - `course_title` - Links chunk to course
  - `lesson_number` - Links chunk to specific lesson
  - `chunk_index` - Position in document

### Sequential Tool Calling

The AI can make tool calls across 2 separate rounds:

**Round 1:** AI requests tool(s) → Tools execute → Results sent back to AI
**Round 2:** AI can request more tool(s) based on first results → Final response

Example: AI first calls `get_course_outline` to find lesson numbers, then calls `search_course_content` with specific lesson filter.

## Configuration Values

Key settings in `backend/config.py`:

- `CHUNK_SIZE: int = 800` - Text chunk size for embeddings
- `CHUNK_OVERLAP: int = 100` - Overlap between chunks
- `MAX_RESULTS: int = 5` - **Must be > 0** - Max search results returned
- `MAX_HISTORY: int = 2` - Conversation history window
- `ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"`
- `EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"`

## Common Patterns

### Adding a new tool

1. Create a class that extends `Tool` in `backend/search_tools.py`
2. Implement `get_tool_definition()` - Returns Anthropic tool schema
3. Implement `execute(**kwargs)` - Tool execution logic
4. Register in `RAGSystem.__init__()`:
   ```python
   self.my_tool = MyTool(dependencies)
   self.tool_manager.register_tool(self.my_tool)
   ```

### Modifying search behavior

Search logic is in `VectorStore.search()`:
1. Course name resolution (semantic matching)
2. Filter building (course + lesson filters)
3. ChromaDB query with filters
4. Return as `SearchResults`

### Working with conversation history

Sessions are managed by `SessionManager`:
- `create_session()` - New session ID
- `add_exchange(session_id, query, response)` - Add to history
- `get_conversation_history(session_id)` - Get formatted history

## Important Constraints

- **Never set `MAX_RESULTS = 0`** in config - causes ChromaDB to return empty results
- Tool execution limited to 2 sequential rounds to prevent loops
- Conversation history limited by `MAX_HISTORY` to manage context window
- Course titles used as unique identifiers (must be unique)
- ChromaDB collections persist in `./chroma_db` directory

## Common Issues

**"Query failed" or empty sources:**
- Check `config.MAX_RESULTS > 0`
- Verify documents loaded on startup
- Check ChromaDB collections exist: `ls -la backend/chroma_db`

**Tool not being called:**
- Verify tool registered in `ToolManager`
- Check tool definition schema matches Anthropic format
- Review AI system prompt in `ai_generator.py`

**Sequential tool calls not working:**
- Verify `MAX_ROUNDS = 2` in `_handle_tool_execution()`
- Ensure tools are passed in subsequent API calls (see line 193-194 in `ai_generator.py`)

## Frontend Integration

Frontend (`frontend/`) is vanilla JavaScript + CSS:
- `script.js` - Handles API calls to `/api/query`
- Displays sources as clickable links (if `lesson_link` available)
- Session management via `sessionId` in requests

API responses include:
```json
{
  "answer": "...",
  "sources": [
    {"text": "Course - Lesson 1", "url": "https://..."},
    ...
  ],
  "session_id": "..."
}
```
