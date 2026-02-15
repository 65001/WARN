import re
from typing import Optional
from src.models import WarnType

def derive_warn_type(text: Optional[str]) -> Optional[WarnType]:
    if not text:
        return None
    
    text = text.lower()
    
    if "closure" in text or "closing" in text:
        return WarnType.CLOSURE
    
    if "temporary" in text:
        return WarnType.TEMPORARY_LAYOFF
    
    if "permanent" in text or "no recall" in text or "layoff" in text:
        return WarnType.PERMANENT_LAYOFF
        
    return None

def clean_impacted(val: str) -> Optional[int]:
    if not val:
        return None
    # Remove comma and non-numeric chars except digits
    digits = re.sub(r'[^\d]', '', str(val))
    if digits:
        return int(digits)
    return None
