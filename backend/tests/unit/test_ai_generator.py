"""Unit tests for backend/ai_generator.py - AIGenerator sequential tool calling"""

import pytest
from ai_generator import AIGenerator


# Test Helper Functions

def create_mock_tool_use_response(mocker, tool_name, tool_input):
    """Helper to create a mock response with tool use"""
    mock_response = mocker.MagicMock()
    mock_response.stop_reason = "tool_use"

    tool_block = mocker.MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = f"toolu_{tool_name}_123"

    mock_response.content = [tool_block]
    return mock_response


def create_mock_text_response(mocker, text):
    """Helper to create a mock response with text"""
    mock_response = mocker.MagicMock()
    mock_response.stop_reason = "end_turn"

    text_block = mocker.MagicMock()
    text_block.type = "text"
    text_block.text = text

    mock_response.content = [text_block]
    return mock_response


def create_mock_multi_tool_response(mocker, tools):
    """Helper to create a mock response with multiple tool uses

    Args:
        mocker: pytest-mock mocker fixture
        tools: List of dicts with 'name' and 'input' keys
    """
    mock_response = mocker.MagicMock()
    mock_response.stop_reason = "tool_use"

    tool_blocks = []
    for i, tool in enumerate(tools):
        tool_block = mocker.MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = tool["name"]
        tool_block.input = tool["input"]
        tool_block.id = f"toolu_{tool['name']}_{i}"
        tool_blocks.append(tool_block)

    mock_response.content = tool_blocks
    return mock_response


# Test Cases

def test_single_round_tool_execution(mocker):
    """Verify existing single-round behavior works (regression test)

    Claude requests tool → gets result → returns text
    """
    # Setup mocks
    mock_client = mocker.MagicMock()
    mock_tool_manager = mocker.MagicMock()

    # Initial response: Claude requests a tool
    initial_response = create_mock_tool_use_response(
        mocker,
        tool_name="search_course_content",
        tool_input={"query": "Python variables"}
    )

    # Tool execution returns result
    mock_tool_manager.execute_tool.return_value = "Variables are containers for storing data..."

    # Second API call: Claude returns text (no more tools)
    final_response = create_mock_text_response(mocker, "Variables in Python are used to store data values.")
    mock_client.messages.create.return_value = final_response

    # Execute
    generator = AIGenerator(api_key="test", model="test")
    generator.client = mock_client

    base_params = {
        "messages": [{"role": "user", "content": "What are Python variables?"}],
        "system": "You are a helpful assistant",
        "tools": [{"name": "search_course_content"}],
        "tool_choice": {"type": "auto"}
    }

    result = generator._handle_tool_execution(
        initial_response,
        base_params,
        mock_tool_manager
    )

    # Assertions
    assert result == "Variables in Python are used to store data values."
    assert mock_client.messages.create.call_count == 1
    assert mock_tool_manager.execute_tool.call_count == 1

    # Verify tool was called with correct arguments
    mock_tool_manager.execute_tool.assert_called_once_with(
        "search_course_content",
        query="Python variables"
    )


def test_two_rounds_sequential_tools(mocker):
    """Verify multi-round capability (core feature)

    Round 1: get_course_outline → Round 2: search_course_content → Final text
    """
    mock_client = mocker.MagicMock()
    mock_tool_manager = mocker.MagicMock()

    # Round 1: Claude requests get_course_outline
    round1_response = create_mock_tool_use_response(
        mocker,
        tool_name="get_course_outline",
        tool_input={"course_name": "Python"}
    )

    # Round 2: Claude requests search_course_content
    round2_response = create_mock_tool_use_response(
        mocker,
        tool_name="search_course_content",
        tool_input={"query": "lesson 4 topic"}
    )

    # Round 3 (final): Claude returns text
    final_response = create_mock_text_response(mocker, "Lesson 4 of the Python course covers Advanced Functions.")

    # Setup API call returns in sequence
    mock_client.messages.create.side_effect = [round2_response, final_response]

    # Tool execution returns
    mock_tool_manager.execute_tool.side_effect = [
        "Course: Python Basics\nLessons:\n4. Advanced Functions",
        "Advanced functions include decorators and generators..."
    ]

    # Execute
    generator = AIGenerator(api_key="test", model="test")
    generator.client = mock_client

    base_params = {
        "messages": [{"role": "user", "content": "What does lesson 4 cover?"}],
        "system": "You are a helpful assistant",
        "tools": [{"name": "get_course_outline"}, {"name": "search_course_content"}],
        "tool_choice": {"type": "auto"}
    }

    result = generator._handle_tool_execution(
        round1_response,
        base_params,
        mock_tool_manager
    )

    # Assertions
    assert result == "Lesson 4 of the Python course covers Advanced Functions."
    assert mock_client.messages.create.call_count == 2  # Round 2 and final
    assert mock_tool_manager.execute_tool.call_count == 2

    # CRITICAL TEST: Verify first API call (round 2) included tools
    first_call_args = mock_client.messages.create.call_args_list[0][1]
    assert "tools" in first_call_args, "Tools should be included in round 2 API call"
    assert "tool_choice" in first_call_args, "Tool choice should be included in round 2 API call"

    # Verify second API call (final) did NOT include tools (max rounds reached)
    second_call_args = mock_client.messages.create.call_args_list[1][1]
    assert "tools" not in second_call_args, "Tools should not be included after max rounds"


def test_max_rounds_termination(mocker):
    """Verify termination after 2 rounds

    Claude wants tools in round 3, but system terminates
    """
    mock_client = mocker.MagicMock()
    mock_tool_manager = mocker.MagicMock()

    # Round 1: Claude requests tool
    round1_response = create_mock_tool_use_response(mocker, "tool1", {"query": "test"})

    # Round 2: Claude requests another tool
    round2_response = create_mock_tool_use_response(mocker, "tool2", {"query": "test2"})

    # Final: Claude forced to return text
    final_response = create_mock_text_response(mocker, "Based on the available information...")

    mock_client.messages.create.side_effect = [round2_response, final_response]
    mock_tool_manager.execute_tool.return_value = "Tool result"

    # Execute
    generator = AIGenerator(api_key="test", model="test")
    generator.client = mock_client

    base_params = {
        "messages": [{"role": "user", "content": "query"}],
        "system": "prompt",
        "tools": [{"name": "tool1"}, {"name": "tool2"}],
        "tool_choice": {"type": "auto"}
    }

    result = generator._handle_tool_execution(
        round1_response,
        base_params,
        mock_tool_manager
    )

    # Assertions
    assert result == "Based on the available information..."
    assert mock_client.messages.create.call_count == 2

    # Verify final API call had NO tools (forced termination)
    final_call_args = mock_client.messages.create.call_args[1]
    assert "tools" not in final_call_args, "Tools should not be included after max rounds"


def test_tool_execution_error_handling(mocker):
    """Verify graceful error handling

    Tool execution raises exception → error added to results → graceful message returned
    """
    mock_client = mocker.MagicMock()
    mock_tool_manager = mocker.MagicMock()

    # Round 1: Claude requests tool
    tool_use_response = create_mock_tool_use_response(
        mocker,
        tool_name="search_course_content",
        tool_input={"query": "test"}
    )

    # Tool execution raises exception
    mock_tool_manager.execute_tool.side_effect = Exception("Database connection error")

    # Final: Claude sees error and responds
    final_response = create_mock_text_response(
        mocker,
        "I encountered an error while accessing the course materials."
    )
    mock_client.messages.create.return_value = final_response

    # Execute
    generator = AIGenerator(api_key="test", model="test")
    generator.client = mock_client

    base_params = {
        "messages": [{"role": "user", "content": "query"}],
        "system": "prompt",
        "tools": [{"name": "search_course_content"}],
        "tool_choice": {"type": "auto"}
    }

    result = generator._handle_tool_execution(
        tool_use_response,
        base_params,
        mock_tool_manager
    )

    # Assertions
    assert "error" in result.lower()

    # Verify tool was attempted
    assert mock_tool_manager.execute_tool.call_count == 1

    # Verify final call had NO tools (terminated due to error)
    call_args = mock_client.messages.create.call_args[1]
    assert "tools" not in call_args, "Tools should not be included after error"


def test_early_termination_no_tool_use(mocker):
    """Verify termination when Claude returns text

    Claude decides not to use tools after seeing first results
    """
    mock_client = mocker.MagicMock()
    mock_tool_manager = mocker.MagicMock()

    # Initial response: Claude returns text directly (no tools)
    text_response = create_mock_text_response(mocker, "I can answer this without tools.")

    # Execute
    generator = AIGenerator(api_key="test", model="test")
    generator.client = mock_client

    base_params = {
        "messages": [{"role": "user", "content": "query"}],
        "system": "prompt",
        "tools": [{"name": "search_course_content"}],
        "tool_choice": {"type": "auto"}
    }

    result = generator._handle_tool_execution(
        text_response,
        base_params,
        mock_tool_manager
    )

    # Assertions
    assert result == "I can answer this without tools."
    assert mock_client.messages.create.call_count == 0  # No additional API calls
    assert mock_tool_manager.execute_tool.call_count == 0  # No tools executed


def test_multiple_tools_single_round(mocker):
    """Verify multiple tools executed in one round

    Claude requests 2 tools simultaneously → both executed → final response
    """
    mock_client = mocker.MagicMock()
    mock_tool_manager = mocker.MagicMock()

    # Round 1: Claude requests TWO tools at once
    multi_tool_response = create_mock_multi_tool_response(
        mocker,
        [
            {"name": "get_course_outline", "input": {"course_name": "Python"}},
            {"name": "search_course_content", "input": {"query": "variables"}}
        ]
    )

    # Tool execution returns
    mock_tool_manager.execute_tool.side_effect = [
        "Course: Python Basics\nLessons: 1. Introduction, 2. Variables",
        "Variables are used to store data..."
    ]

    # Final response
    final_response = create_mock_text_response(mocker, "The Python course covers variables in lesson 2.")
    mock_client.messages.create.return_value = final_response

    # Execute
    generator = AIGenerator(api_key="test", model="test")
    generator.client = mock_client

    base_params = {
        "messages": [{"role": "user", "content": "query"}],
        "system": "prompt",
        "tools": [{"name": "get_course_outline"}, {"name": "search_course_content"}],
        "tool_choice": {"type": "auto"}
    }

    result = generator._handle_tool_execution(
        multi_tool_response,
        base_params,
        mock_tool_manager
    )

    # Assertions
    assert result == "The Python course covers variables in lesson 2."
    assert mock_tool_manager.execute_tool.call_count == 2

    # Verify both tools were called with correct arguments
    call_args_list = mock_tool_manager.execute_tool.call_args_list
    assert call_args_list[0][0][0] == "get_course_outline"
    assert call_args_list[1][0][0] == "search_course_content"


def test_tools_included_in_second_api_call(mocker):
    """CRITICAL: Verify tools are passed to API in round 2

    This test verifies the core bug fix: tools parameter must be included
    in subsequent API calls to enable sequential tool calling.
    """
    mock_client = mocker.MagicMock()
    mock_tool_manager = mocker.MagicMock()

    # Round 1: Claude uses tool
    round1_response = create_mock_tool_use_response(
        mocker,
        tool_name="get_course_outline",
        tool_input={"course_name": "Python"}
    )

    # Round 2: Claude wants to use tool again
    round2_response = create_mock_tool_use_response(
        mocker,
        tool_name="search_course_content",
        tool_input={"query": "Advanced Functions"}
    )

    # Final: Text response
    final_response = create_mock_text_response(mocker, "Answer based on both tools")

    # Setup mock returns
    mock_client.messages.create.side_effect = [round2_response, final_response]
    mock_tool_manager.execute_tool.return_value = "Tool result"

    # Execute
    generator = AIGenerator(api_key="test", model="test")
    generator.client = mock_client

    tools_list = [
        {"name": "get_course_outline", "input_schema": {}},
        {"name": "search_course_content", "input_schema": {}}
    ]

    base_params = {
        "messages": [{"role": "user", "content": "query"}],
        "system": "prompt",
        "tools": tools_list,
        "tool_choice": {"type": "auto"}
    }

    result = generator._handle_tool_execution(
        round1_response,
        base_params,
        mock_tool_manager
    )

    # THE CRITICAL ASSERTIONS
    # Verify that the first API call (round 2) included tools
    first_api_call = mock_client.messages.create.call_args_list[0]
    call_kwargs = first_api_call[1]

    assert "tools" in call_kwargs, "BUG: Tools parameter missing from round 2 API call"
    assert call_kwargs["tools"] == tools_list, "Tools list should match original"
    assert "tool_choice" in call_kwargs, "Tool choice should be included"
    assert call_kwargs["tool_choice"] == {"type": "auto"}, "Tool choice should be 'auto'"

    # Verify the messages were accumulated correctly
    assert "messages" in call_kwargs
    messages = call_kwargs["messages"]
    assert len(messages) >= 3, "Should have user query, assistant tool use, and tool results"
