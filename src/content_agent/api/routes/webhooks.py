import structlog
from fastapi import APIRouter, Request

router = APIRouter()
logger = structlog.get_logger()


@router.post("/redmine")
async def redmine_webhook(request: Request) -> dict[str, str]:
    """Receive Redmine webhook events (issue created/updated)."""
    payload = await request.json()
    logger.info("webhook.redmine.received", payload_keys=list(payload.keys()))
    # TODO: parse payload, extract issue ID, trigger pipeline if conditions met
    return {"status": "received"}
