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


async def get_issue_tool_func(params: Union[Dict[str, Any], str] = None) -> Dict[str, Any]:
    """
    Get a specific Linear issue by ID.
    
    Parameters:
    - params: Either a dictionary with an 'id' key or a string ID
    
    Returns:
    - Dictionary containing issue details
    """
    try:
        # Log the parameters for debugging
        print(f"Calling get_issue with params: {params}")
        
        # Call the Linear API
        if isinstance(params, str):
            return await linear_tools.get_issue(params)
        else:
            error_msg = "Invalid parameters: Expected an issue ID string"
            print(error_msg)
            raise ToolException(error_msg)
    except Exception as e:
        error_msg = f"Error fetching issue: {str(e)}"
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
    description: str = """Get a specific Linear issue by ID. 
    You must provide the issue ID as a string parameter (e.g., "INF-10", "INF-11").
    Do not pass a dictionary or object, just the ID string directly.
    Example: get_issue("INF-10")"""
    
    def _run(self, params: Union[Dict[str, Any], str] = None) -> Dict[str, Any]:
        return asyncio.run(get_issue_tool_func(params))
    
    async def _arun(self, params: Union[Dict[str, Any], str] = None) -> Dict[str, Any]:
        return await get_issue_tool_func(params)

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
        GetIssueTool()
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
            error_msg = f"Error processing query: {str(e)}"
            print(error_msg)
            return {"error": error_msg}
    
    return agent_wrapper
