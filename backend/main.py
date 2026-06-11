"""FastAPI application for agent observability backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import traces, replay, alerts
from app.database import TraceDatabase
from app.services.alerts import CostAlertManager, get_alert_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database instance
db = TraceDatabase(db_path="traces.db")

# Replay engine instance
replay_engine = None

# Alert manager instance
alert_mgr = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Agent Observability Backend...")

    # Set database for API routes
    traces.set_database(db)

    # Initialize replay engine
    try:
        from agent_trace.replay import ReplayEngine
        global replay_engine
        replay_engine = ReplayEngine()
        replay.set_database(db)
        replay.set_replay_engine(replay_engine)
        logger.info("Replay engine initialized")
    except ImportError as e:
        logger.warning(f"Replay module not available: {e}")

    # Initialize alert manager
    global alert_mgr
    alert_mgr = get_alert_manager()
    alerts.set_alert_manager(alert_mgr)
    logger.info("Cost alert manager initialized")

    yield
    logger.info("Shutting down Agent Observability Backend...")


# Create FastAPI app
app = FastAPI(
    title="Agent Observability API",
    description="Backend API for agent tracing, observability, replay, and cost alerting",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(traces.router)
app.include_router(replay.router)
app.include_router(alerts.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Agent Observability API",
        "docs": "/docs",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
