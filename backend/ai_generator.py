import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """You are an AI assistant specialized in course materials and educational content with access to tools for both searching course content and retrieving course outlines.

Available Tools:
1. **search_course_content**: Search within course materials for specific content, concepts, or answers
   - Use for: Questions about specific topics, detailed explanations, examples, code snippets
   - Example queries: "How do decorators work?", "Show me examples of async functions"

2. **get_course_outline**: Get the complete structure and lesson list of a course
   - Use for: Questions about course organization, available lessons, what's covered
   - Example queries: "What lessons are in the Python course?", "Show me the course structure"

Tool Usage Guidelines:
- Use tools when querying specific course information
- You may use multiple tools in a single response if needed to fully answer the question
- **Sequential Tool Calling**: You can make tool calls across up to 2 separate rounds
  - Example: First call get_course_outline to find a lesson, then call search_course_content with that lesson info
  - After receiving tool results, you can request additional tools if needed to complete the answer
- Synthesize tool results into clear, accurate responses
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course-specific questions**: Use appropriate tool(s) first, then answer
- **No meta-commentary**:
  - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
  - Do not mention "based on the search results" or "using the outline tool"

All responses must be:
1. **Brief, concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding

Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls with support for up to 2 sequential rounds.

        A "round" consists of:
        1. Claude requests one or more tools (stop_reason == "tool_use")
        2. All tools are executed
        3. Results are sent back to Claude

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters (includes tools, tool_choice, system)
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution or error message
        """
        MAX_ROUNDS = 2
        current_round = 1

        # Start with existing messages
        messages = base_params["messages"].copy()
        current_response = initial_response

        while current_round <= MAX_ROUNDS:
            # Termination condition 1: No tool use - Claude returned text
            if current_response.stop_reason != "tool_use":
                return current_response.content[0].text

            # Add AI's tool use response to messages
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute all tool calls and collect results
            tool_results = []
            tool_execution_failed = False

            for content_block in current_response.content:
                if content_block.type == "tool_use":
                    try:
                        tool_result = tool_manager.execute_tool(
                            content_block.name,
                            **content_block.input
                        )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result
                        })
                    except Exception as e:
                        # Handle tool execution errors gracefully
                        error_message = f"Tool execution error: {str(e)}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": error_message,
                            "is_error": True
                        })
                        tool_execution_failed = True

            # Add tool results as user message
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Termination condition 2: Tool execution failed
            if tool_execution_failed:
                # Continue to let Claude see the error and respond
                # but don't allow further tool calls
                final_params = {
                    **self.base_params,
                    "messages": messages,
                    "system": base_params["system"]
                }
                final_response = self.client.messages.create(**final_params)
                return final_response.content[0].text

            # Termination condition 3: Max rounds reached
            if current_round >= MAX_ROUNDS:
                # Make final API call WITHOUT tools to force text response
                final_params = {
                    **self.base_params,
                    "messages": messages,
                    "system": base_params["system"]
                }
                final_response = self.client.messages.create(**final_params)
                return final_response.content[0].text

            # Continue to next round - make API call WITH tools (THE KEY FIX!)
            next_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"],
                "tools": base_params["tools"],
                "tool_choice": base_params["tool_choice"]
            }

            current_response = self.client.messages.create(**next_params)
            current_round += 1

        # Fallback (should never reach here due to max rounds check)
        return current_response.content[0].text