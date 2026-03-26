"""
Stage 1 MVP - FastAPI Application (Controller Layer)
Main entry point for the adaptive questionnaire backend.
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from controllers import checkin_router, voice_router


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Disable caching for JS and CSS static assets when running on localhost."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        host = request.headers.get("host", "").split(":")[0]
        if host in ("localhost", "127.0.0.1") and (
            request.url.path.endswith(".js") or request.url.path.endswith(".css")
        ):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    from controllers.checkin import initialize_provider
    initialize_provider()
    print("[STARTUP] Application initialized with MockPatientDataProvider by default")
    yield


app = FastAPI(
    title="Stage 1 MVP - Adaptive Questionnaire",
    description="Demo API for pre-visit adaptive symptom questionnaire",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(NoCacheStaticMiddleware)

# Register routers
app.include_router(checkin_router)
app.include_router(voice_router)


# Mount voice agent routes (optional; app still starts if unavailable)
try:
    from voice_agent.main import app as voice_agent_app

    app.mount("/voice-agent", voice_agent_app.fastapi_app)
    logger.info("[STARTUP] Mounted voice agent at /voice-agent")
except Exception as e:
    logger.warning("[STARTUP] Voice agent not mounted: %s", e)

# This mounts your views folder so FastAPI serves the HTML/JS/CSS
app.mount("/", StaticFiles(directory="views", html=True), name="views")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

