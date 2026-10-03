from fastapi import APIRouter, HTTPException, Query, Request

from ...schemas import FeedbackRequest, FeedbackReviewItem
from ...services.feedback import FeedbackService

router = APIRouter()


def _get_feedback_service(request: Request) -> FeedbackService:
    service = getattr(request.app.state, "feedback_service", None)
    if service is None:
        settings = getattr(request.app.state, "settings", None)
        feedback_dir = getattr(settings, "feedback_dir", None)
        service = FeedbackService(feedback_dir)
        request.app.state.feedback_service = service
    return service


@router.post("/feedback", status_code=202)
def submit_feedback(body: FeedbackRequest, request: Request) -> dict[str, str]:
    record = body.model_dump()
    store = getattr(request.app.state, "store", None)
    if store and hasattr(store, "feedback"):
        store.feedback.append(record)

    feedback_service = _get_feedback_service(request)
    feedback_service.add_feedback(
        request_id=body.request_id,
        predicted_label=record.get("predicted_label", "Unknown"),
        user_label=body.label,
        comment=body.comment,
        photo_consent=body.photo_consent,
        image_b64=body.image_b64,
    )

    return {"status": "accepted", "request_id": body.request_id}


@router.get("/admin/feedback", response_model=list[FeedbackReviewItem])
def list_feedback_queue(
    request: Request, status: str = Query("all")
) -> list[FeedbackReviewItem]:
    feedback_service = _get_feedback_service(request)
    items = feedback_service.get_queue(status=status)
    return [FeedbackReviewItem(**i) for i in items]


@router.post("/admin/feedback/{item_id}/review")
def review_feedback_item(
    item_id: str,
    request: Request,
    action: str = Query(..., pattern="^(approve|reject)$"),
) -> dict[str, str]:
    feedback_service = _get_feedback_service(request)
    status = "approved" if action == "approve" else "rejected"
    res = feedback_service.review_item(item_id, status=status)
    if not res:
        raise HTTPException(status_code=404, detail="Feedback item not found")

    return {"status": "ok", "item_id": item_id, "new_status": status}
