from enum import Enum
from typing import Optional
from datetime import date
from pydantic import BaseModel, HttpUrl

class WarnType(str, Enum):
    CLOSURE = "Closure"
    PERMANENT_LAYOFF = "PermanentLayoff"
    TEMPORARY_LAYOFF = "TemporaryLayoff"

class Address(BaseModel):
    street: Optional[str] = None
    municipality: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

class Employee(BaseModel):
    name: Optional[str] = None
    address: Optional[Address] = None

class Contact(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None

class WarnRecord(BaseModel):
    employer: Employee
    location: Address
    union: Optional[Employee] = None
    contact: Optional[Contact] = None
    warn_date: Optional[date] = None
    layoff_date: Optional[date] = None
    type: Optional[WarnType] = None
    impacted: Optional[int] = None
    notes: Optional[str] = None
    link: Optional[HttpUrl] = None
