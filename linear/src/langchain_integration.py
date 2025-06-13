import os
from typing import Dict, Any, List, Callable, Optional, Union
import json

from langchain_core.tools import ToolException
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from linear_tools import LinearTools

# Initialize the Linear tools
linear_tools = LinearTools()

# Define the async tool functions
async def list_issues_tool_func(params: Union[Dict[str, Any], str, int] = None) -> Dict[str, Any]:
    """
    List Linear issues with various filter parameters.
    
    Parameters:
    - params: Dictionary containing filter parameters:
        - teamId: Optional team ID to filter by
        - projectId: Optional project ID to filter by
        - labelId: Optional label ID to filter by
        - stateId: Optional workflow state ID to filter by
        - priority: Optional priority level (0-4 or text: 'urgent', 'high', 'medium', 'low', 'none') to filter by
        - assignee: Optional assignee name to filter by
        - assigneeId: Optional assignee user ID to filter by
        - first: Optional number of issues to return (default: 50)
    
    Returns:
    - Dictionary containing list of issues
    """
    # Handle non-dictionary inputs for convenience
    if params is None:
        params = {}
    elif isinstance(params, int):
        # If an integer is provided, assume it's a priority
        params = {"priority": params}
    elif isinstance(params, str):
        # If a string is provided, try to parse it as JSON
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            # If not valid JSON, assume it's a team name or ID (most common use case)
            params = {"teamId": params}
    
    # Handle special case for assigneeId - if it's not a UUID, move it to assignee
    if params.get("assigneeId") and not is_valid_uuid(params["assigneeId"]):
        print(f"Converting assigneeId '{params['assigneeId']}' to assignee parameter")
        params["assignee"] = params["assigneeId"]
        del params["assigneeId"]
    
    print(f"Final params for list_issues: {json.dumps(params, indent=2)}")
    try:
        return await linear_tools.list_issues(params)
    except Exception as e:
        raise ToolException(str(e))

def is_valid_uuid(val):
    """Check if a string is a valid UUID."""
    if not val or not isinstance(val, str):
        return False
    
    try:
        # Try to parse as UUID to validate format
        import uuid
        uuid.UUID(val)
        return True
    except ValueError:
        return False

async def get_issue_tool_func(params: Union[Dict[str, Any], str] = None) -> Dict[str, Any]:
    """
    Get a specific Linear issue by ID.
    
    Parameters:
    - params: Either a dictionary with an 'id' key or a string ID
    
    Returns:
    - Dictionary containing issue details
    """
    # Handle string input for convenience
    if isinstance(params, str):
        issue_id = params
    elif isinstance(params, dict) and "id" in params:
        issue_id = params["id"]
    else:
        raise ToolException("Invalid parameters: Expected an issue ID string or a dictionary with an 'id' key")
    
    try:
        return await linear_tools.get_issue(issue_id)
    except Exception as e:
        raise ToolException(str(e))

# Define the router prompt template
router_template = """You are a helpful assistant that routes user queries about Linear issues to the appropriate tool.

Available tools:
1. list_issues - List Linear issues with various filter parameters
2. get_issue - Get a specific Linear issue by ID

Based on the user's query, determine which tool to use and what parameters to provide.

For list_issues, you can filter by:
- teamId: Team ID to filter by
- projectId: Project ID to filter by
- labelId: Label ID to filter by
- stateId: Workflow state ID to filter by
- priority: Priority level (0-4 or text: 'urgent', 'high', 'medium', 'low', 'none')
- assignee: Assignee name to filter by (use this for name-based queries like "assigned to John")
- assigneeId: Assignee user ID to filter by (only use when you have the exact UUID)
- unassigned: Set to true to find issues without an assignee (use for queries like "unassigned issues")
- first: Number of issues to return (default: 50)

For get_issue, you need:
- id: The ID of the issue to retrieve

User query: {query}

Respond with a JSON object containing:
{{"tool": "tool_name", "params": {{"param1": "value1", "param2": "value2"}}}}

Remember to only include parameters that are explicitly mentioned or can be reasonably inferred from the user's query.
"""

# Create the router chain
router_chain = (
    ChatPromptTemplate.from_template(router_template)
    | ChatOpenAI(temperature=0)
    | JsonOutputParser()
)

# Define the routing and execution function
async def route_and_execute(query: str) -> Dict[str, Any]:
    """
    Route a natural language query to the appropriate Linear tool and execute it.
    
    Parameters:
    - query: Natural language query about Linear issues
    
    Returns:
    - Result from the appropriate tool
    """
    try:
        # Route the query to determine which tool to use
        router_result = await router_chain.ainvoke({"query": query})
        print(f"Router result: {json.dumps(router_result, indent=2)}")
        
        # Extract tool name and parameters
        tool_name = router_result.get("tool")
        params = router_result.get("params", {})
        
        # Execute the appropriate tool
        if tool_name == "list_issues":
            print(f"Executing list_issues with params: {json.dumps(params, indent=2)}")
            return await list_issues_tool_func(params)
        elif tool_name == "get_issue":
            print(f"Executing get_issue with params: {json.dumps(params, indent=2)}")
            return await get_issue_tool_func(params)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    except Exception as e:
        return {"error": f"Error routing query: {str(e)}"}

# Create the streaming version of the router
async def create_streaming_linear_mcp(callback_manager=None):
    """
    Create a streaming version of the Linear MCP router.
    
    Parameters:
    - callback_manager: Optional callback manager for streaming
    
    Returns:
    - Streaming router function
    """
    # Create a streaming LLM
    streaming_llm = ChatOpenAI(
        temperature=0,
        streaming=True,
        callbacks=callback_manager
    )
    
    # Create the streaming router chain
    streaming_router_chain = (
        ChatPromptTemplate.from_template(router_template)
        | streaming_llm
        | JsonOutputParser()
    )
    
    # Define the streaming routing and execution function
    async def streaming_route_and_execute(query: str) -> Dict[str, Any]:
        try:
            # Route the query to determine which tool to use
            route_result = await streaming_router_chain.ainvoke({"query": query})
            
            tool_name = route_result.get("tool")
            params = route_result.get("params", {})
            
            # Execute the appropriate tool
            if tool_name == "list_issues":
                return await list_issues_tool_func(params)
            elif tool_name == "get_issue":
                return await get_issue_tool_func(params)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    return streaming_route_and_execute

# Create the Linear MCP function
def create_linear_mcp():
    """
    Create the Linear MCP router function.
    
    Returns:
    - Router function that processes natural language queries
    """
    return route_and_execute
