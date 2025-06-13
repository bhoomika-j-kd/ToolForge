#!/usr/bin/env python3
import os
import sys
import argparse
from dotenv import load_dotenv

def main():
    """
    Main entry point for the Linear MCP server.
    Handles command line arguments and starts the appropriate server.
    """
    parser = argparse.ArgumentParser(description='Linear MCP Server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the HTTP server on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind the HTTP server to')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Check for API key
    if not os.environ.get("LINEAR_API_KEY"):
        print("ERROR: LINEAR_API_KEY environment variable is required")
        print("Please set it in your environment or in a .env file")
        sys.exit(1)
    
    # Import here to avoid circular imports
    import uvicorn
    from http_server import app
    
    # Start the HTTP server
    print(f"Starting Linear MCP HTTP server on {args.host}:{args.port}")
    uvicorn.run(
        "http_server:app", 
        host=args.host, 
        port=args.port, 
        reload=args.debug
    )

if __name__ == "__main__":
    main()
