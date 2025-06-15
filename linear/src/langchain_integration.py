import os
from typing import Dict, Any, Union, Type, Optional, List
import json

from langchain_core.tools import ToolException, BaseTool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from linear_tools import LinearTools
from system_prompt import get_system_prompt

import asyncio

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
    try:
        # Ensure params is a dictionary
        if params is None:
            params = {}
        
        # Log the parameters for debugging
        print(f"Calling list_issues with params: {json.dumps(params, indent=2)}")
        
        # Call the Linear API
        return await linear_tools.list_issues(params)
    except Exception as e:
        error_msg = f"Error listing issues: {str(e)}"
        print(error_msg)
        raise ToolException(error_msg)


async def get_issue_tool_func(params: Union[Dict[str, Any], str, List[str]] = None) -> Dict[str, Any]:
    """
    Get one or more Linear issues by ID.
    
    Parameters:
    - params: Either a dictionary with an 'id' key, a string ID, or a list of string IDs
    
    Returns:
    - Dictionary containing issue details or a list of issue details
    """
    try:
        # Handle different parameter types
        if params is None:
            raise ValueError("Issue ID is required")
            
        # Log the parameters for debugging
        print(f"Calling get_issue with params: {params}")
        
        # Call the Linear API
        return await linear_tools.get_issue(params)
    except Exception as e:
        error_msg = f"Error getting issue: {str(e)}"
        print(error_msg)
        raise ToolException(error_msg)

async def get_cycle_status_tool_func(cycle_name: str) -> Dict[str, Any]:
    """
    Get status update for a specific cycle with ticket counts by status,
    completion percentage, and progress tracking.
    
    Parameters:
    - cycle_name: Name of the cycle to get status for (e.g., "Sprint 19")
    
    Returns:
    - Dictionary containing cycle status information
    """
    try:
        if not cycle_name:
            raise ValueError("Cycle name is required")
            
        # Log the parameters for debugging
        print(f"Calling get_cycle_status with cycle_name: {cycle_name}")
        
        # Call the Linear API
        result = await linear_tools.get_cycle_status(cycle_name)
        
        # Check for errors
        if "error" in result:
            return result
            
        # Format the response with expandable ticket lists
        cycle_details = result["cycle_details"]
        ticket_counts = result["ticket_counts"]
        completion_stats = result["completion_stats"]
        progress_tracking = result["progress_tracking"]
        issues_by_status = result.get("issues_by_status", {})
        
        # Return the formatted result
        return {
            "cycle_details": cycle_details,
            "ticket_counts": ticket_counts,
            "completion_stats": completion_stats,
            "progress_tracking": progress_tracking,
            "issues_by_status": issues_by_status
        }
    except Exception as e:
        error_msg = f"Error getting cycle status: {str(e)}"
        print(error_msg)
        raise ToolException(error_msg)

# 1. Define tool wrappers for agent
class ListIssuesTool(BaseTool):
    name: str = "list_issues"
    description: str = "List Linear issues with various filter parameters"
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        # Collect all keyword arguments into a dictionary
        params = kwargs
        return asyncio.run(list_issues_tool_func(params))
    
    async def _arun(self, **kwargs) -> Dict[str, Any]:
        # Collect all keyword arguments into a dictionary
        params = kwargs
        return await list_issues_tool_func(params)

class GetIssueTool(BaseTool):
    name: str = "get_issue"
    description: str = """Get one or more Linear issues by ID. 
    You must provide the issue ID(s) as a string parameter (e.g., "INF-10", "INF-11") or a list of string parameters (e.g., ["INF-10", "INF-11"]).
    Do not pass a dictionary or object, just the ID string(s) directly.
    Example: get_issue("INF-10") or get_issue(["INF-10", "INF-11"])"""
    
    def _run(self, params: Union[Dict[str, Any], str, List[str]] = None) -> Dict[str, Any]:
        return asyncio.run(get_issue_tool_func(params))
    
    async def _arun(self, params: Union[Dict[str, Any], str, List[str]] = None) -> Dict[str, Any]:
        return await get_issue_tool_func(params)

class CycleStatusTool(BaseTool):
    name: str = "get_cycle_status"
    description: str = """Get status update for a specific cycle with ticket counts by status,
    completion percentage, and progress tracking.
    
    You must provide the cycle name as a string parameter (e.g., "Sprint 19").
    Example: get_cycle_status("Sprint 19")
    """
    
    def _run(self, cycle_name: str) -> Dict[str, Any]:
        raise NotImplementedError("This tool does not support synchronous execution")
        
    async def _arun(self, cycle_name: str) -> Dict[str, Any]:
        return await get_cycle_status_tool_func(cycle_name)

# Create the Linear MCP function
def create_linear_mcp():
    """
    Create the Linear MCP router function using OpenAI functions agent.
    
    Returns:
    - Router function that processes natural language queries
    """
    # 1. Define list of tools
    tools = [
        ListIssuesTool(),
        GetIssueTool(),
        CycleStatusTool()
    ]
    
    # 2. Create the LLM with explicit API key
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
        
    llm = ChatOpenAI(
        model="gpt-4", 
        temperature=0,
        openai_api_key=openai_api_key
    )
    
    # Create a prompt template with the required agent_scratchpad
    prompt = ChatPromptTemplate.from_messages([
        ("system", get_system_prompt()),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create the agent
    agent = create_openai_functions_agent(llm, tools, prompt)
    
    # Create the agent executor
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    # Return a wrapper function that takes a query and returns the result
    async def agent_wrapper(query: str) -> Dict[str, Any]:
        try:
            # Process the query
            result = await agent_executor.ainvoke({"input": query})
            # Make sure the result is a dictionary
            if isinstance(result["output"], str):
                return {"message": result["output"]}
            return result["output"]
        except Exception as e:
            error_str = str(e)
            # Check for context length exceeded error
            if "context_length_exceeded" in error_str or "maximum context length" in error_str:
                return {"message": "Your search returned too many results. Please narrow your search by adding more specific filters (status, priority, assignee, label, etc)."}
            error_msg = f"Error processing query: {error_str}"
            print(error_msg)
            return {"error": error_msg}
    
    return agent_wrapper
