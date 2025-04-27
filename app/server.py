import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.graph import graph


app = FastAPI(
    title="LangGraph API",
    description="API for LangGraph interactions",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@ app.post("/agent")
async def agent(request: Request):
    """Endpoint for running the agent."""
    body = await request.json()

    query = body.get("query")
    input={
        "messages":query
    }
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    
    res=await graph.ainvoke(input,config={"thread_id": "1"})
    # res = "hello"
    # print(res['messages'][-1])

    return res['messages'][-1].content


def main():
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
