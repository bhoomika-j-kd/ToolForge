import os
import json
import asyncio
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks.manager import CallbackManager

from langchain_integration import create_linear_mcp

# Load environment variables
load_dotenv()

# Check for API key
if not os.environ.get("LINEAR_API_KEY"):
    raise ValueError("LINEAR_API_KEY environment variable is required")

# Create FastAPI app
app = FastAPI(title="Linear MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the Linear MCP function
linear_mcp = create_linear_mcp()

# Define request models
class QueryRequest(BaseModel):
    query: str

# Define response models
class QueryResponse(BaseModel):
    result: Dict[str, Any]

# Custom streaming callback handler
class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = True
        
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        if token:
            await self.queue.put(json.dumps({"type": "token", "content": token}) + "\n")
    
    async def on_llm_end(self, response, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "llm_end"}) + "\n")
    
    async def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "tool_start", "tool": serialized["name"]}) + "\n")
    
    async def on_tool_end(self, output, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "tool_end", "output": output}) + "\n")
    
    async def on_chain_start(self, serialized, inputs, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "chain_start"}) + "\n")
    
    async def on_chain_end(self, outputs, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "chain_end", "outputs": str(outputs)}) + "\n")
    
    async def on_chain_error(self, error, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "chain_error", "error": str(error)}) + "\n")
    
    async def on_tool_error(self, error, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "tool_error", "error": str(error)}) + "\n")
    
    async def on_text(self, text, **kwargs) -> None:
        await self.queue.put(json.dumps({"type": "text", "text": text}) + "\n")
    
    def done(self) -> None:
        self.is_running = False

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a natural language query for Linear."""
    try:
        # Process the query
        result = await linear_mcp(request.query)
        return {"result": result}
    except Exception as e:
        return {"result": {"error": str(e)}}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# Main function to run the server
def main():
    import uvicorn
    uvicorn.run("http_server:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
