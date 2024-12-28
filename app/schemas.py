from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from enum import Enum

class ScholarshipStatus(str, Enum):
    draft = "Draft"
    purposed = "Purposed"
    under_review = "Under Review"
    open = "Open"
    jury_evaluation = "Jury Evaluation"
    closed = "Closed"

class JuryBase(BaseModel):
    pass

class JuryCreate(JuryBase):
    pass

class JuryRead(JuryBase):
    id: str

class ScientificAreaBase(BaseModel):
    name: str

class ScientificAreaCreate(ScientificAreaBase):
    pass

class ScientificArea(ScientificAreaBase):
    id: int

    class Config:
        from_attributes = True

class EdictBase(BaseModel):
    name: str
    description: Optional[str] = None
    publication_date: Optional[datetime] = None

class EdictCreate(EdictBase):
    pass

class Edict(EdictBase):
    id: int
    file_path: str

    class Config:
        from_attributes  = True

class DocumentTemplateBase(BaseModel):
    name: str
    file_path: str

class DocumentTemplateCreate(DocumentTemplateBase):
    pass

class DocumentTemplate(DocumentTemplateBase):
    id: int
    scholarship_id: int  # Linking to the scholarship it belongs to
    required: bool
    template: bool

    class Config:
        from_attributes = True

class ScholarshipBase(BaseModel):
    name: str
    description: Optional[str] = None
    publisher: str
    type: str
    deadline: Optional[date] = None
    status: ScholarshipStatus

class ScholarshipCreate(ScholarshipBase):
    jury: Optional[List[str]] = None
    documents: Optional[List[DocumentTemplateCreate]] = None
    edict_id: Optional[int] = None

class Scholarship(ScholarshipBase):
    id: int
    created_at: datetime
    approved_at: Optional[datetime] = None
    results_at: Optional[datetime] = None
    scientific_areas: List[ScientificArea]
    edict: Optional[Edict] = None
    documents: List[DocumentTemplate] = []
    jury: Optional[List[JuryRead]] = None

    class Config:
        from_attributes = True

class FilterOptionsResponse(BaseModel):
    types: List[str]
    scientific_areas: List[str]
    status: List[ScholarshipStatus]
    publishers: List[str]
    deadlines: List[date]
