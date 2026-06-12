"""FastAPI application for agent observability backend."""

import logging
import os
import sys
from contextlib import asynccontextmanager

# Add SDK to Python path so agent_trace package is importable
_sdk_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sdk", "python")
if _sdk_path not in sys.path:
    sys.path.insert(0, _sdk_path)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import traces, replay, alerts, evaluations, streaming, analytics, auth_routes, notifications
from app.database import TraceDatabase
from app.db.sqlite_impl import SQLiteEvaluationRepository
from app.errors import AppError, ConflictError, NotFoundError, ServiceError, ValidationError
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

    # Run migrations
    try:
        from app.db.migrations.runner import run_migrations
        run_migrations(db.db_path)
        logger.info("Database migrations applied")
    except Exception as e:
        logger.warning(f"Migration runner: {e}")

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

    # Initialize evaluation repository
    eval_repo = SQLiteEvaluationRepository(db_path=db.db_path)
    evaluations.set_repository(eval_repo)
    logger.info("Evaluation repository initialized")

    # Initialize analytics
    analytics.set_database(db)
    logger.info("Analytics module initialized")

    # Initialize auth tables
    from app.auth import _ensure_users_table
    _ensure_users_table()
    logger.info("Auth module initialized")

    # Initialize notifications
    from app.services.notifications import get_dispatcher
    notif_dispatcher = get_dispatcher()
    notifications.set_dispatcher(notif_dispatcher)
    logger.info("Notification dispatcher initialized")

    yield
    logger.info("Shutting down Agent Observability Backend...")


# Create FastAPI app
app = FastAPI(
    title="Agent Observability API",
    description="Backend API for agent tracing, observability, replay, and cost alerting",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Global exception handlers ──────────────────────────────


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": exc.message, "detail": exc.detail},
    )


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": exc.message, "detail": exc.detail},
    )


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return JSONResponse(
        status_code=409,
        content={"error": exc.message, "detail": exc.detail},
    )


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(
        status_code=500,
        content={"error": exc.message, "detail": exc.detail},
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=500,
        content={"error": exc.message, "detail": exc.detail},
    )


# ── Middleware ──────────────────────────────────────────────


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
app.include_router(evaluations.router)
app.include_router(streaming.router)
app.include_router(analytics.router)
app.include_router(auth_routes.router)
app.include_router(notifications.router)
app.include_router(dashboards.router)


# ── Session endpoints (added to traces router scope) ────────


@app.get("/api/traces/sessions")
async def list_sessions(limit: int = 50):
    """List distinct sessions with metadata."""
    sessions = db._repo.list_sessions(limit=limit)
    return {"sessions": sessions}


@app.get("/api/traces/sessions/{session_id}")
async def get_session_traces(session_id: str):
    """Get all traces belonging to a session."""
    session_traces = db._repo.get_session_traces(session_id)
    if not session_traces:
        raise NotFoundError("Session", session_id)
    return {"session_id": session_id, "traces": session_traces}


# ── Health / root ───────────────────────────────────────────


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

