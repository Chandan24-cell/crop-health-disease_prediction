from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/history")
def history(request: Request, limit: int = 50) -> list[dict[str, object]]:
    return list(request.app.state.store.records)[: max(0, min(limit, 200))]
