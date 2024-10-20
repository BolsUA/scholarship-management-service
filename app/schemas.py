from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from enum import Enum

class ScholarshipStatus(str, Enum):
    draft = "draft"
    purposed = "purposed"
    review = "review"
    open = "open"
    jury_evaluation = "jury_evaluation"
    closed = "closed"

class ScientificAreaBase(BaseModel):
    name: str

class ScientificAreaCreate(ScientificAreaBase):
    pass

class ScientificArea(ScientificAreaBase):
    id: int

    class Config:
        orm_mode = True

class EdictBase(BaseModel):
    name: str
    description: Optional[str] = None
    publication_date: Optional[date] = None

class EdictCreate(EdictBase):
    pass

class Edict(EdictBase):
    id: int

    class Config:
        orm_mode = True

class DocumentTemplateBase(BaseModel):
    name: str
    file_path: str

class DocumentTemplateCreate(DocumentTemplateBase):
    pass

class DocumentTemplate(DocumentTemplateBase):
    id: int
    scholarship_id: int  # Linking to the scholarship it belongs to

    class Config:
        orm_mode = True

class ScholarshipBase(BaseModel):
    name: str
    description: Optional[str] = None
    publisher: str
    type: str
    jury: Optional[str] = None
    deadline: Optional[date] = None
    status: ScholarshipStatus

class ScholarshipCreate(ScholarshipBase):
    documents: Optional[List[DocumentTemplateCreate]] = None  # Optional templates when creating
    edict_id: Optional[int] = None  # Optional edict reference when creating

class Scholarship(ScholarshipBase):
    id: int
    created_at: datetime
    approved_at: Optional[datetime] = None
    results_at: Optional[datetime] = None
    scientific_areas: List[ScientificArea]
    edict: Optional[Edict] = None
    documents: List[DocumentTemplate] = []

    class Config:
        orm_mode = True
