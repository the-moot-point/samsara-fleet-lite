from pydantic import BaseModel
from typing import Optional, List


class DriverAddPayload(BaseModel):
    externalIds: dict[str, str]
    name: str
    username: str
    password: str
    notes: str
    phone: str | None = None
    licenseState: str
    eldExempt: bool = True
    eldExemptReason: str = "Short Haul"
    locale: str = "us"
    timezone: str = "America/Chicago"
    tagIds: List[str]
    peerGroupTagId: Optional[str] = None
    usDriverRulesetOverride: dict | None = None
