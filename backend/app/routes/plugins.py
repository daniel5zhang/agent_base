from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/catalog")
def catalog(
    tenant_id: str = Query(min_length=1),
    workspace_id: str = Query(min_length=1),
    role: str = Query(min_length=1),
) -> dict[str, object]:
    _ = (tenant_id, workspace_id, role)
    return {
        "plugins": [],
        "phase": "phase_one",
        "message": "业务插件将在二阶段启用",
    }
