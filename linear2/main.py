import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

async def run_airbnb_example():
    # Load environment variables
    load_dotenv()

    # Get Linear API key from environment
    linear_api_key = os.environ.get("LINEAR_API_KEY")
    if not linear_api_key:
        raise ValueError("LINEAR_API_KEY environment variable is not set")

    # Create MCPClient with Linear configuration and API key
    client = MCPClient.from_config_file(
        os.path.join(os.path.dirname(__file__), "mcp.json")
    )

    # Create LLM - you can choose between different models
    llm = ChatOpenAI(model="gpt-4o")

    # Create agent with the client
    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    try:
        # Run a query to search for accommodations
        result = await agent.run(
            "Find me all issues in Linear assigned to Bhoomika J with status high and marked done",
            max_steps=30
        )
        print(f"\nResult: {result}")
    finally:
        # Ensure we clean up resources properly
        if client.sessions:
            await client.close_all_sessions()

if __name__ == "__main__":
    asyncio.run(run_airbnb_example())