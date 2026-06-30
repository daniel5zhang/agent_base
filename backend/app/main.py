from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import initialize_database
from app.routes.agent import compat_router as agent_compat_router
from app.routes.agent import router as agent_router
from app.routes.artifacts import router as artifacts_router
from app.routes.ask_data import router as ask_data_router
from app.routes.diagnostics import router as diagnostics_router
from app.routes.health import router as health_router
from app.routes.models import router as models_router
from app.routes.plugins import router as plugins_router
from app.routes.runtime import router as runtime_router
from app.routes.threads import router as threads_router
from app.routes.tools import router as tools_router


def create_app() -> FastAPI:
    initialize_database()
    app = FastAPI(title="Enterprise Agent Workbench Server", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3001",
            "http://localhost:3001",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "tauri://localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(agent_router)
    app.include_router(agent_compat_router)
    app.include_router(plugins_router)
    app.include_router(ask_data_router)
    app.include_router(runtime_router)
    app.include_router(threads_router)
    app.include_router(tools_router)
    app.include_router(artifacts_router)
    app.include_router(diagnostics_router)
    return app


app = create_app()
