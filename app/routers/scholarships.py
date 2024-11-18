from datetime import date, datetime
from typing import Annotated, List, Optional
from app import schemas
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.models import Scholarship, ScholarshipStatus, ScholarshipScientificAreaLink, ScholarshipJuryLink, ScientificArea, Jury

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]

# --------------------- SCHOLARSHIPS ---------------------

# INSERT DUMMY SCHOLARSHIPS
@router.post("/scholarships/dummy", response_model=List[schemas.Scholarship])
def create_dummy_scholarships(db: SessionDep): # type: ignore
    areas_to_create = ["Computer Science", "Biology", "Physics"]
    scientific_areas = {}

    # Iterate over the areas to create or fetch them from the database
    for area_name in areas_to_create:
        statement = select(ScientificArea).where(ScientificArea.name == area_name)
        area = db.exec(statement).first()
        
        if not area:
            area = ScientificArea(name=area_name)
            db.add(area)
            db.commit()
            db.refresh(area)
        
        scientific_areas[area_name] = area

    # Create or get jury members
    jury_to_create = ["Dr. Alice", "Dr. Bob", "Dr. Carol"]
    jury = {}

    for jury_name in jury_to_create:
        juror = db.exec(select(Jury).where(Jury.name == jury_name)).first()
        if not juror:
            juror = Jury(name=jury_name)
            db.add(juror)
            db.commit()
            db.refresh(juror)
        jury[jury_name] = juror

    # Define dummy scholarships
    dummy_scholarships = [
        Scholarship(
            name="Scholarship A",
            description="A brief description of Scholarship A.",
            publisher="University of XYZ",
            scientific_areas=[scientific_areas["Biology"]],  # Change this if you have scientific area data
            type="Research Initiation Scholarship",
            jury=[jury["Dr. Alice"], jury["Dr. Bob"]],
            deadline=date(2024, 12, 31),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=ScholarshipStatus.jury_evaluation,
            edict_id=None
        ),
        Scholarship(
            name="Scholarship B",
            description="A brief description of Scholarship B.",
            publisher="Institute of ABC",
            scientific_areas=[scientific_areas["Computer Science"], scientific_areas["Physics"]],  # Change this if you have scientific area data
            type="Research Scholarship",
            jury=[jury["Dr. Carol"]],
            deadline=date(2024, 11, 15),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=ScholarshipStatus.open,
            edict_id=None
        ),
        Scholarship(
            name="Scholarship C",
            description="A brief description of Scholarship C.",
            publisher="Bla bla",
            scientific_areas=[scientific_areas["Computer Science"], scientific_areas["Physics"]],  # Change this if you have scientific area data
            type="Research Scholarship",
            jury=[jury["Dr. Alice"], jury["Dr. Carol"]],
            deadline=date(2024, 11, 15),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=ScholarshipStatus.closed,
            edict_id=None
        )
    ]

    # Insert dummy scholarships into the database
    db.add_all(dummy_scholarships)
    db.commit()
    # Refresh each scholarship individually
    for scholarship in dummy_scholarships:
        db.refresh(scholarship)

    return dummy_scholarships

# ---------- ENDPOINT TO RETRIEVE ALL SCHOLARSHIPS ----------
@router.get("/scholarships", response_model=List[schemas.Scholarship])
def get_scholarships(
    db: SessionDep,  # type: ignore
    page: int = 1, 
    limit: int = 10,
    name: Optional[str] = Query(None),
    status: Optional[List[ScholarshipStatus]] = Query(None),
    scientific_areas: Optional[List[str]] = Query(None),
    publisher: Optional[str] = Query(None),
    types: Optional[List[str]] = Query(None),
    jury_name: Optional[str] = Query(None),
    deadline_start: Optional[date] = Query(None),
    deadline_end: Optional[date] = Query(None)
    ):

    offset = (page - 1) * limit

    statement = select(Scholarship)

    if name:
        statement = statement.where(Scholarship.name.ilike(f"%{name}%"))
    if status:
        statement = statement.where(Scholarship.status.in_(status))
    if publisher:
        statement = statement.where(Scholarship.publisher == publisher)
    if types:
        statement = statement.where(Scholarship.type.in_(types))
    if deadline_start:
        statement = statement.where(Scholarship.deadline >= deadline_start)
    if deadline_end:
        statement = statement.where(Scholarship.deadline <= deadline_end)
    if scientific_areas:
        # Join with the scientific area model to filter by multiple area names
        statement = (
            statement.join(ScholarshipScientificAreaLink)
            .join(ScientificArea)
            .where(ScientificArea.name.in_(scientific_areas))
        )

    if jury_name:
        # Join with the Jury model to filter by jury name
        statement = (
            statement.join(ScholarshipJuryLink)
            .join(Jury)
            .where(Jury.name == jury_name)
        )
    statement = statement.offset(offset).limit(limit)

    results = db.exec(statement).all()

    return results

# ---------- ENDPOINT TO RETRIEVE FILTER OPTIONS ----------
@router.get("/scholarships/filters", response_model=schemas.FilterOptionsResponse)
def get_filter_options(db: SessionDep): # type: ignore
    # Retrieve distinct types of scholarships
    types = db.exec(select(Scholarship.type).distinct()).all()
    types = [t for t in types if t]  # Extract values from tuples and exclude None

    # Retrieve all scientific areas
    scientific_areas = db.exec(select(ScientificArea.name)).all()
    scientific_areas = [sa for sa in scientific_areas if sa]

    # Get all possible statuses from the ScholarshipStatus enum
    status = [schemas.ScholarshipStatus(status.value) for status in ScholarshipStatus]

    # Retrieve distinct publishers
    publishers = db.exec(select(Scholarship.publisher).distinct()).all()
    publishers = [p for p in publishers if p]

    # Retrieve distinct deadlines
    deadlines = db.exec(select(Scholarship.deadline).distinct()).all()
    deadlines = [d for d in deadlines if d]

    return schemas.FilterOptionsResponse(
        types=types,
        scientific_areas=scientific_areas,
        status=status,
        publishers=publishers,
        deadlines=deadlines,
    )

# ---------- ENDPOINT TO RETRIEVE A SCHOLARSHIP BY ID ----------
@router.get("/scholarships/{id}/details", response_model=schemas.Scholarship)
def get_scholarship(id: int, db: SessionDep): # type: ignore
    statement = select(Scholarship).where(Scholarship.id == id)
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return result