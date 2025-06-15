"""
Linear API MCP Server

This server exposes Linear API tools through the Model Context Protocol (MCP).
"""

import asyncio
import os
import sys
import json
import traceback
from typing import Annotated, Dict, List, Any, Union, Optional

# MCP imports - using the same pattern as sample.py
import mcp.server.stdio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.shared.exceptions import McpError
from mcp.types import (
    TextContent,
    Tool,
    INVALID_PARAMS
)
from pydantic import BaseModel, Field

# Import Linear tools
from linear_tools import LinearTools

# Import system prompt
from system_prompt import get_system_prompt

# Set up logging to a file
LOG_FILE = os.path.join(os.path.dirname(__file__), "../logs/linear_mcp.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log_message(message):
    """Log a message to both stderr and the log file"""
    print(message, file=sys.stderr)
    with open(LOG_FILE, "a") as f:
        f.write(f"{message}\n")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    log_message("Environment variables loaded from .env file")
except ImportError:
    log_message("Warning: python-dotenv not installed. Environment variables must be set manually.")

# Initialize the server
server = Server("linear")
log_message(f"Server initialized with name 'linear'")

# Initialize Linear tools
try:
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        log_message("ERROR: LINEAR_API_KEY environment variable is not set")
        sys.exit(1)
    
    log_message(f"Initializing Linear tools with API key: {api_key[:5]}...{api_key[-5:]}")
    linear_tools = LinearTools()
    log_message("Linear tools initialized successfully")
except Exception as e:
    log_message(f"Error initializing Linear tools: {e}")
    traceback.print_exc(file=sys.stderr)
    with open(LOG_FILE, "a") as f:
        traceback.print_exc(file=f)
    sys.exit(1)

# Pydantic models for tool inputs
class ListIssuesInput(BaseModel):
    teamId: Annotated[Optional[str], Field(description="Optional team ID to filter by")] = None
    projectId: Annotated[Optional[str], Field(description="Optional project ID to filter by")] = None
    labelId: Annotated[Optional[str], Field(description="Optional label ID to filter by")] = None
    label: Annotated[Optional[str], Field(description="Optional label name to filter by")] = None
    stateId: Annotated[Optional[str], Field(description="Optional workflow state ID to filter by")] = None
    status: Annotated[Optional[str], Field(description="Optional status to filter by")] = None
    priority: Annotated[Optional[int], Field(description="Optional priority level (0-4) to filter by")] = None
    assignee: Annotated[Optional[str], Field(description="Optional assignee name to filter by")] = None
    assigneeId: Annotated[Optional[str], Field(description="Optional assignee user ID to filter by")] = None
    cycle: Annotated[Optional[str], Field(description="Optional cycle name to filter by")] = None
    first: Annotated[Optional[int], Field(description="Optional number of issues to return (default: 50)")] = 50
    title: Annotated[Optional[str], Field(description="Optional title to filter by")] = None

class GetIssueInput(BaseModel):
    id: Annotated[Union[str, List[str]], Field(description="The ID of the issue to retrieve, or a list of issue IDs")]

class GetCycleStatusInput(BaseModel):
    cycle_name: Annotated[str, Field(description="Name of the cycle to get status for (e.g., 'Sprint 19')")]

# MCP Tool implementation
@server.list_tools()
async def list_tools():
    log_message("Listing tools...")
    return [
        Tool(
            name="list_issues",
            description="List Linear issues with various filter parameters",
            inputSchema=ListIssuesInput.model_json_schema(),
        ),
        Tool(
            name="get_issue",
            description="Get one or more Linear issues by ID",
            inputSchema=GetIssueInput.model_json_schema(),
        ),
        Tool(
            name="get_cycle_status",
            description="Get status update for a specific cycle with ticket counts by status, completion percentage, and progress tracking",
            inputSchema=GetCycleStatusInput.model_json_schema(),
        ),
    ]

@server.call_tool()
async def call_tool(name, arguments):
    log_message(f"Tool called: {name} with arguments: {json.dumps(arguments)}")
    
    if name == "list_issues":
        try:
            log_message(f"Validating list_issues arguments...")
            args = ListIssuesInput(**arguments)
            params = {k: v for k, v in args.model_dump().items() if v is not None}
            log_message(f"Calling linear_tools.list_issues with params: {json.dumps(params)}")
            
            try:
                result = await linear_tools.list_issues(params)
                log_message(f"list_issues result type: {type(result)}")
                log_message(f"list_issues result: {json.dumps(result, default=str)[:1000]}...")
                return [TextContent(type="text", text=json.dumps(result))]
            except Exception as api_error:
                log_message(f"API Error in list_issues: {str(api_error)}")
                log_message("API Error Traceback:")
                traceback.print_exc(file=sys.stderr)
                with open(LOG_FILE, "a") as f:
                    traceback.print_exc(file=f)
                raise McpError(f"API Error listing issues: {str(api_error)}")
                
        except Exception as e:
            log_message(f"Error in list_issues: {e}")
            log_message("Error Traceback:")
            traceback.print_exc(file=sys.stderr)
            with open(LOG_FILE, "a") as f:
                traceback.print_exc(file=f)
            raise McpError(f"Error listing issues: {str(e)}")
            
    elif name == "get_issue":
        try:
            log_message(f"Validating get_issue arguments...")
            args = GetIssueInput(**arguments)
            log_message(f"Calling linear_tools.get_issue with id: {args.id}")
            
            try:
                result = await linear_tools.get_issue(args.id)
                log_message(f"get_issue result type: {type(result)}")
                log_message(f"get_issue result: {json.dumps(result, default=str)[:1000]}...")
                return [TextContent(type="text", text=json.dumps(result))]
            except Exception as api_error:
                log_message(f"API Error in get_issue: {str(api_error)}")
                log_message("API Error Traceback:")
                traceback.print_exc(file=sys.stderr)
                with open(LOG_FILE, "a") as f:
                    traceback.print_exc(file=f)
                raise McpError(f"API Error getting issue: {str(api_error)}")
                
        except Exception as e:
            log_message(f"Error in get_issue: {e}")
            log_message("Error Traceback:")
            traceback.print_exc(file=sys.stderr)
            with open(LOG_FILE, "a") as f:
                traceback.print_exc(file=f)
            raise McpError(f"Error getting issue: {str(e)}")
            
    elif name == "get_cycle_status":
        try:
            log_message(f"Validating get_cycle_status arguments...")
            args = GetCycleStatusInput(**arguments)
            log_message(f"Calling linear_tools.get_cycle_status with cycle_name: {args.cycle_name}")
            
            try:
                result = await linear_tools.get_cycle_status(args.cycle_name)
                log_message(f"get_cycle_status result type: {type(result)}")
                log_message(f"get_cycle_status result: {json.dumps(result, default=str)[:1000]}...")
                return [TextContent(type="text", text=json.dumps(result))]
            except Exception as api_error:
                log_message(f"API Error in get_cycle_status: {str(api_error)}")
                log_message("API Error Traceback:")
                traceback.print_exc(file=sys.stderr)
                with open(LOG_FILE, "a") as f:
                    traceback.print_exc(file=f)
                raise McpError(f"API Error getting cycle status: {str(api_error)}")
                
        except Exception as e:
            log_message(f"Error in get_cycle_status: {e}")
            log_message("Error Traceback:")
            traceback.print_exc(file=sys.stderr)
            with open(LOG_FILE, "a") as f:
                traceback.print_exc(file=f)
            raise McpError(f"Error getting cycle status: {str(e)}")
    
    else:
        log_message(f"Unknown tool: {name}")
        raise McpError(f"Unknown tool: {name}")

async def main():
    """Main entry point for the Linear MCP server."""
    log_message("Starting Linear MCP server...")
    
    # Check for required environment variables
    if not os.environ.get("LINEAR_API_KEY"):
        log_message("ERROR: LINEAR_API_KEY environment variable is required")
        sys.exit(1)
    
    try:
        # Get the system prompt
        system_prompt = get_system_prompt()
        log_message("Loaded system prompt successfully")
        
        # Start the server
        log_message("Initializing MCP server with stdio...")
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            log_message("Got stdio streams, running server...")
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="linear",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                    system_prompt=system_prompt,
                ),
            )
        log_message("Linear MCP server completed")
    except Exception as e:
        log_message(f"Error starting Linear MCP server: {e}")
        traceback.print_exc(file=sys.stderr)
        with open(LOG_FILE, "a") as f:
            traceback.print_exc(file=f)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_message("Server stopped by user")
    except Exception as e:
        log_message(f"Unexpected error: {e}")
        traceback.print_exc(file=sys.stderr)
        with open(LOG_FILE, "a") as f:
            traceback.print_exc(file=f)
        sys.exit(1)
