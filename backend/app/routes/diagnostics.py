from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.llm import load_local_env, model_configured

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("")
def diagnostics(session: Session = Depends(get_session)) -> dict[str, object]:
    load_local_env()
    session.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "phase": "phase_one",
        "checks": {
            "sqlite": "ok",
            "model": "configured" if model_configured() else "not_configured",
            "business_plugins": "disabled_until_phase_two",
        },
    }
