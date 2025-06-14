import os
import json
from typing import Dict, List, Any, Optional, Union
from linear_python import LinearClient
import aiohttp

class LinearTools:
    """Tools for interacting with the Linear API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Linear API key."""
        self.api_key = api_key or os.environ.get("LINEAR_API_KEY")
        if not self.api_key:
            raise ValueError("LINEAR_API_KEY environment variable or api_key parameter is required")
        
        # Initialize the Linear client
        self.client = LinearClient(self.api_key)
    
    async def _execute_graphql(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against the Linear API with fallback mechanisms."""
        variables = variables or {}
        
        # Try multiple possible methods that might exist in the client library
        try:
            # First try client.query() if it exists
            if hasattr(self.client, "query"):
                return await self.client.query(query, variables)
            
            # Then try client.raw_query() which is the correct method in linear-python 0.2.2
            if hasattr(self.client, "raw_query"):
                return await self.client.raw_query(query, variables)
            
            # Then try client.execute()
            if hasattr(self.client, "execute"):
                return await self.client.execute(query, variables)
            
            # Then try client.graphql()
            if hasattr(self.client, "graphql"):
                return await self.client.graphql(query, variables)
        except Exception as e:
            print(f"Error using client methods: {e}")
        
        # As a last resort, make a direct HTTP request to the Linear API
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key  # Linear API expects the API key directly without "Bearer" prefix
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.linear.app/graphql",
                headers=headers,
                json={"query": query, "variables": variables}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"GraphQL request failed with status {response.status}: {error_text}")
                
                result = await response.json()
                if "errors" in result:
                    raise Exception(f"GraphQL errors: {json.dumps(result['errors'])}")
                
                return result
    
    async def list_issues(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        List Linear issues with various filter parameters.
        
        Parameters:
        - params: Dictionary containing filter parameters:
            - teamId: Optional team ID to filter by
            - projectId: Optional project ID to filter by
            - labelId: Optional label ID to filter by
            - label: Optional label name to filter by
            - stateId: Optional workflow state ID to filter by
            - status: Optional status to filter by
            - priority: Optional priority level (0-4) to filter by
            - assignee: Optional assignee name to filter by
            - assigneeId: Optional assignee user ID to filter by
            - first: Optional number of issues to return (default: 50)
            - title: Optional title to filter by
        
        Returns:
        - Dictionary containing list of issues
        """
        params = params or {}
        
        # Build the filter object for the GraphQL query
        filter_parts = []
        if params.get("teamId"):
            filter_parts.append(f'team: {{ id: {{ eq: "{params["teamId"]}" }} }}')
        if params.get("projectId"):
            filter_parts.append(f'project: {{ id: {{ eq: "{params["projectId"]}" }} }}')
        if params.get("labelId"):
            filter_parts.append(f'labels: {{ id: {{ eq: "{params["labelId"]}" }} }}')
        if params.get("label"):
            filter_parts.append(f'labels: {{ name: {{ eq: "{params["label"]}" }} }}')
        if params.get("stateId"):
            filter_parts.append(f'state: {{ id: {{ eq: "{params["stateId"]}" }} }}')
        if params.get("status"):
            filter_parts.append(f'state: {{ name: {{ eq: "{params["status"]}" }} }}')
        if params.get("priority"):
            filter_parts.append(f'priority: {{ eq: {params["priority"]} }}')
        if params.get("assignee") is not None:
            if params["assignee"] == "":
                # Empty string means filter for unassigned issues
                filter_parts.append(f'assignee: {{ null: true }}')
            else:
                filter_parts.append(f'assignee: {{ name: {{ contains: "{params["assignee"]}" }} }}')
        if params.get("title"):
            filter_parts.append(f'title: {{ contains: "{params["title"]}" }}')
            
        filter_string = ", ".join(filter_parts)
        filter_arg = f"filter: {{ {filter_string} }}" if filter_string else ""
        
        first = params.get("first", 50)
        
        # GraphQL query for issues with all necessary fields
        query = f"""
        query Issues($first: Int!) {{
            issues(first: $first {filter_arg and ", " + filter_arg}) {{
                nodes {{
                    id
                    title
                    identifier
                    description
                    priority
                    state {{
                        id
                        name
                        type
                    }}
                    assignee {{
                        id
                        name
                        displayName
                    }}
                    team {{
                        id
                        name
                        key
                    }}
                    labels {{
                        nodes {{
                            id
                            name
                            color
                        }}
                    }}
                    createdAt
                    updatedAt
                }}
            }}
        }}
        """
        
        variables = {"first": first}
        
        # Log the query and parameters for debugging
        # print(f"GraphQL Query: {query}")
        # print(f"Variables: {variables}")
        # print(f"Filter parts: {filter_parts}")
        # print(f"Original params: {params}")
        
        try:
            result = await self._execute_graphql(query, variables)
            
            if "data" not in result or "issues" not in result["data"]:
                raise Exception(f"Unexpected response format: {json.dumps(result)}")
            
            issues = result["data"]["issues"]["nodes"]
            processed_issues = []
            
            for issue in issues:
                processed_issue = {
                    "id": issue["id"],
                    "title": issue["title"],
                    "identifier": issue["identifier"],
                    "description": issue["description"],
                    "priority": issue["priority"],
                    "status": issue["state"]["name"] if issue["state"] else None,
                    "state_type": issue["state"]["type"] if issue["state"] else None,
                    "state_id": issue["state"]["id"] if issue["state"] else None,
                    "assignee": issue["assignee"]["name"] if issue["assignee"] else None,
                    "assignee_id": issue["assignee"]["id"] if issue["assignee"] else None,
                    "team": issue["team"]["name"] if issue["team"] else None,
                    "team_id": issue["team"]["id"] if issue["team"] else None,
                    "team_key": issue["team"]["key"] if issue["team"] else None,
                    "labels": [{"id": label["id"], "name": label["name"], "color": label["color"]} 
                              for label in issue["labels"]["nodes"]] if issue["labels"] else [],
                    "created_at": issue["createdAt"],
                    "updated_at": issue["updatedAt"]
                }
                processed_issues.append(processed_issue)
            
            return {"nodes": processed_issues}
        
        except Exception as e:
            error_msg = f"Error listing issues: {str(e)}"
            print(error_msg)
            return {"error": error_msg}
    
    async def get_issue(self, id: Union[str, List[str]]) -> Dict[str, Any]:
        """
        Get one or more Linear issues by ID.
        
        Parameters:
        - id: The ID of the issue to retrieve, or a list of issue IDs
        
        Returns:
        - Dictionary containing issue details, or a list of issue details
        """
        # If a single ID is provided, convert to list for uniform processing
        if isinstance(id, str):
            ids = [id]
            return_single = True
        else:
            ids = id
            return_single = False
            
        results = []
        
        for issue_id in ids:
            query = """
            query Issue($id: String!) {
                issue(id: $id) {
                    id
                    title
                    identifier
                    description
                    priority
                    state {
                        id
                        name
                        type
                    }
                    assignee {
                        id
                        name
                        displayName
                    }
                    team {
                        id
                        name
                        key
                    }
                    labels {
                        nodes {
                            id
                            name
                            color
                        }
                    }
                    createdAt
                    updatedAt
                }
            }
            """
            
            variables = {"id": issue_id}
            
            try:
                result = await self._execute_graphql(query, variables)
                
                if "data" not in result or "issue" not in result["data"]:
                    results.append({"error": f"Unexpected response format for issue {issue_id}: {json.dumps(result)}"})
                    continue
                
                issue = result["data"]["issue"]
                if not issue:
                    results.append({"error": f"Issue with ID {issue_id} not found"})
                    continue
                
                # Process the response to flatten and simplify the structure
                processed_issue = {
                    "id": issue["id"],
                    "title": issue["title"],
                    "identifier": issue["identifier"],
                    "description": issue["description"],
                    "priority": issue["priority"],
                    "status": issue["state"]["name"] if issue["state"] else None,
                    "state_type": issue["state"]["type"] if issue["state"] else None,
                    "state_id": issue["state"]["id"] if issue["state"] else None,
                    "assignee": issue["assignee"]["name"] if issue["assignee"] else None,
                    "assignee_id": issue["assignee"]["id"] if issue["assignee"] else None,
                    "team": issue["team"]["name"] if issue["team"] else None,
                    "team_id": issue["team"]["id"] if issue["team"] else None,
                    "team_key": issue["team"]["key"] if issue["team"] else None,
                    "labels": [{"id": label["id"], "name": label["name"], "color": label["color"]} 
                              for label in issue["labels"]["nodes"]] if issue["labels"] else [],
                    "created_at": issue["createdAt"],
                    "updated_at": issue["updatedAt"]
                }
                
                results.append(processed_issue)
            
            except Exception as e:
                results.append({"error": f"Error getting issue {issue_id}: {str(e)}"})
        
        # Return a single result if only one ID was provided
        if return_single:
            return results[0]
        
        return {"issues": results}
