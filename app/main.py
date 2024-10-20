from fastapi.middleware.cors import CORSMiddleware
from typing import List, Annotated
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session, SQLModel, select
from .database import engine
from . import models, schemas
from datetime import date, datetime

# Create all tables in the database (if they don't exist already)
SQLModel.metadata.create_all(engine)

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": True})

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

@app.post("/scholarships/dummy", response_model=List[schemas.Scholarship])
def create_dummy_scholarships(db: SessionDep):
    areas_to_create = ["Computer Science", "Biology", "Physics"]
    scientific_areas = {}

    # Iterate over the areas to create or fetch them from the database
    for area_name in areas_to_create:
        statement = select(models.ScientificArea).where(models.ScientificArea.name == area_name)
        area = db.exec(statement).first()
        
        if not area:
            area = models.ScientificArea(name=area_name)
            db.add(area)
            db.commit()
            db.refresh(area)
        
        scientific_areas[area_name] = area

    # Define dummy scholarships
    dummy_scholarships = [
        models.Scholarship(
            name="Scholarship A",
            description="A brief description of Scholarship A.",
            publisher="University of XYZ",
            scientific_areas=[scientific_areas["Biology"]],  # Change this if you have scientific area data
            type="Research Initiation Scholarship",
            deadline=date(2024, 12, 31),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=models.ScholarshipStatus.jury_evaluation,
            edict_id=None
        ),
        models.Scholarship(
            name="Scholarship B",
            description="A brief description of Scholarship B.",
            publisher="Institute of ABC",
            scientific_areas=[scientific_areas["Computer Science"], scientific_areas["Physics"]],  # Change this if you have scientific area data
            type="Research Scholarship",
            deadline=date(2024, 11, 15),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=models.ScholarshipStatus.open,
            edict_id=None
        ),
        models.Scholarship(
            name="Scholarship C",
            description="A brief description of Scholarship C.",
            publisher="Bla bla",
            scientific_areas=[scientific_areas["Computer Science"], scientific_areas["Physics"]],  # Change this if you have scientific area data
            type="Research Scholarship",
            deadline=date(2024, 11, 15),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=models.ScholarshipStatus.closed,
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

# Endpoint to retrieve all scholarships
@app.get("/scholarships", response_model=List[schemas.Scholarship])
def get_scholarships(db: SessionDep, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    statement = select(models.Scholarship).offset(offset).limit(limit)
    results = db.exec(statement).all()
    return results

# Endpoint to retrieve a single scholarship by ID
@app.get("/scholarships/{id}", response_model=schemas.Scholarship)
def get_scholarship(id: int, db: SessionDep):
    statement = select(models.Scholarship).where(models.Scholarship.id == id)
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return result
