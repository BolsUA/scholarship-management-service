from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, date
import enum

# Enum for scholarship status
class ScholarshipStatus(enum.Enum):
    draft = "Draft"
    under_review = "Under Review"
    open = "Open"
    jury_evaluation = "Jury Evaluation"
    closed = "Closed"

class ScholarshipJuryLink(SQLModel, table=True):
    scholarship_id: Optional[int] = Field(
        default=None, foreign_key="scholarship.id", primary_key=True
    )
    jury_id: Optional[str] = Field(
        default=None, foreign_key="jury.id", primary_key=True
    )

class Jury(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)

    scholarships: List["Scholarship"] = Relationship(
        back_populates="jury", link_model=ScholarshipJuryLink
    )

class ScholarshipScientificAreaLink(SQLModel, table=True):
    scholarship_id: Optional[int] = Field(default=None, foreign_key="scholarship.id", primary_key=True)
    scientific_area_id: Optional[int] = Field(default=None, foreign_key="scientificarea.id", primary_key=True)

class ScientificArea(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    name: str = Field(nullable=False, unique=True)

    scholarships: List["Scholarship"] = Relationship(back_populates="scientific_areas", link_model=ScholarshipScientificAreaLink)

class Edict(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    name: str = Field(nullable=False)
    file_path: str = Field(nullable=False)
    publication_date: datetime = Field(default_factory=datetime.now, nullable=False)

    scholarships: List["Scholarship"] = Relationship(back_populates="edict")

class Scholarship(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None)
    publisher: str = Field(nullable=False)
    type: str = Field(nullable=False)
    jury: List[Jury] = Relationship(
        back_populates="scholarships", link_model=ScholarshipJuryLink
    )
    deadline: Optional[date] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    approved_at: Optional[datetime] = Field(default=None)
    results_at: Optional[datetime] = Field(default=None)
    edict_id: Optional[int] = Field(foreign_key="edict.id")
    status: ScholarshipStatus = Field(default=ScholarshipStatus.draft, nullable=False)

    scientific_areas: List[ScientificArea] = Relationship(back_populates="scholarships", link_model=ScholarshipScientificAreaLink)
    edict: Optional[Edict] = Relationship(back_populates="scholarships")
    documents: List["DocumentTemplate"] = Relationship(back_populates="scholarship")

class DocumentTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    scholarship_id: Optional[int] = Field(foreign_key="scholarship.id")
    name: str = Field(nullable=False)
    file_path: str = Field(nullable=False)
    required: bool = Field(nullable=False)
    template: bool = Field(nullable=False)

    scholarship: Optional[Scholarship] = Relationship(back_populates="documents")
