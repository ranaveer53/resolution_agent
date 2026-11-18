"""
FastAPI Backend Server for Decision-Making Resolution Agent.
Provides RESTful endpoints for resolution processing, database inspection, and state resets.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import time

from database import db
from agent import ResolutionAgent
from registry import build_default_registry

app = FastAPI(
    title="Autonomous Order Resolution Agent Backend",
    description="Backend API powering multi-step autonomous decision making, tool-use, exchange evaluations, and refunds.",
    version="1.0.0"
)

# Enable CORS for terminal clients, scripts, and web UIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = ResolutionAgent()


class ResolveRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"
    show_trajectory: Optional[bool] = True


class ResolveResponse(BaseModel):
    status: str
    final_answer: str
    iterations: int
    escalated: bool
    execution_time_seconds: float
    trajectory: Optional[List[Dict[str, Any]]] = None


@app.get("/")
def root():
    return {
        "service": "Decision-Making Resolution Agent Backend",
        "status": "online",
        "docs_url": "/docs",
        "endpoints": {
            "resolve": "POST /api/resolve",
            "orders": "GET /api/orders",
            "inventory": "GET /api/inventory",
            "refunds": "GET /api/refunds",
            "exchanges": "GET /api/exchanges",
            "notifications": "GET /api/notifications",
            "reset": "POST /api/reset"
        }
    }


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "resolution-agent"}


@app.get("/api/orders")
def get_orders():
    """Retrieve all order records from the database."""
    return {"orders": list(db.orders.values())}


@app.get("/api/inventory")
def get_inventory():
    """Retrieve all warehouse inventory counts."""
    return {"inventory": list(db.inventory.values())}


@app.get("/api/refunds")
def get_refunds():
    """Retrieve all processed refunds."""
    return {"refunds": db.refunds}


@app.get("/api/exchanges")
def get_exchanges():
    """Retrieve all confirmed exchanges."""
    return {"exchanges": db.exchanges}


@app.get("/api/notifications")
def get_notifications():
    """Retrieve all dispatched customer notifications."""
    return {"notifications": db.notifications}


@app.post("/api/reset")
def reset_database():
    """Reset database state to original seed data."""
    db.reset()
    return {"status": "success", "message": "Database successfully reset to initial seed state."}


@app.post("/api/resolve", response_model=ResolveResponse)
def resolve_request(req: ResolveRequest):
    """
    Primary endpoint: Invokes the autonomous resolution agent state loop.
    Autonomous investigation, inventory checks, conditional branching, and email notification.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="The 'message' field cannot be empty.")

    start_time = time.time()
    result = agent.run(req.message)
    duration = round(time.time() - start_time, 4)

    return ResolveResponse(
        status=result.get("status", "UNKNOWN"),
        final_answer=result.get("final_answer", ""),
        iterations=result.get("iterations", 0),
        escalated=result.get("escalated", False),
        execution_time_seconds=duration,
        trajectory=result.get("trajectory") if req.show_trajectory else None
    )


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Start uvicorn server directly."""
    print(f"\n==================================================================")
    print(f"🚀 Starting Resolution Agent Backend on http://{host}:{port}")
    print(f"📖 Interactive Swagger API Docs: http://{host}:{port}/docs")
    print(f"==================================================================\n")
    uvicorn.run("backend_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    start_server()
