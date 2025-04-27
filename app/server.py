# server.py

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from graph import graph
from typing import Any, Dict

# Initialize FastAPI app
app = FastAPI(
    title="LangGraph API",
    description="An API for interacting with the LangGraph agent.",
    version="0.1.0"
)

# Setup CORS middleware to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/agent", summary="Run the LangGraph agent", response_description="Agent response message")
async def run_agent(request: Request) -> str:
    """
    POST endpoint to interact with the LangGraph agent.

    Expects a JSON body containing a 'query' field.
    Returns the latest message content from the agent's response.
    """
    try:
        body: Dict[str, Any] = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    query = body.get("query")
    
    if not query:
        raise HTTPException(status_code=400, detail="The 'query' field is required.")

    input_data = {
        "messages": query
    }

    try:
        response = await graph.ainvoke(input_data, config={"thread_id": "1"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error invoking LangGraph agent: {str(e)}") from e

    if not response or 'messages' not in response or not response['messages']:
        raise HTTPException(status_code=500, detail="Invalid response structure from LangGraph agent.")

    # Return the content of the last message
    return response['messages'][-1].content


def main() -> None:
    """Entrypoint for running the FastAPI application with Uvicorn."""
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
