"""Pydantic models for API"""

from pydantic import BaseModel
from typing import Optional, Any

class Status(BaseModel):
    """Status response model"""
    status: str
    version: str
    message: str

class HAEntity(BaseModel):
    """Home Assistant entity model"""
    entity_id: str
    state: str
    attributes: dict = {}

class HAMessage(BaseModel):
    """Home Assistant message model"""
    type: str
    payload: Optional[dict] = None

class ServiceCall(BaseModel):
    """Service call model"""
    domain: str
    service: str
    service_data: Optional[dict] = None
