"""API Router for Home Assistant Add-on"""

from fastapi import APIRouter, HTTPException
from .models import Status, HAEntity

router = APIRouter(prefix="/api", tags=["api"])

@router.get("/status", response_model=Status)
async def get_status():
    """Get add-on status"""
    return Status(
        status="running",
        version="1.2.0",
        message="Home Assistant Add-on is running"
    )

@router.get("/entities", response_model=list[HAEntity])
async def get_entities():
    """Get list of available Home Assistant entities"""
    # This would query Home Assistant in real implementation
    return []

@router.post("/service/{domain}/{service}")
async def call_service(domain: str, service: str, data: dict = None):
    """Call a Home Assistant service"""
    if not domain or not service:
        raise HTTPException(status_code=400, detail="Invalid service")
    
    # This would call Home Assistant service in real implementation
    return {
        "success": True,
        "domain": domain,
        "service": service,
        "data": data or {}
    }
