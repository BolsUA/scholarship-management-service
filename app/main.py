from typing import List, Annotated
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session, SQLModel, select
from .database import engine
from . import models, schemas
from datetime import date, datetime

# Create all tables in the database (if they don't exist already)
SQLModel.metadata.create_all(engine)

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": True})

# Dependency to get DB session
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

@app.post("/scholarships/dummy", response_model=List[schemas.Scholarship])
def create_dummy_scholarships(db: SessionDep):
    statement = select(models.ScientificArea).where(models.ScientificArea.name == "Computer Science")
    computer_science_area = db.exec(statement).first()
    
    if not computer_science_area:
        computer_science_area = models.ScientificArea(name="Computer Science")
        db.add(computer_science_area)
        db.commit()
        db.refresh(computer_science_area)

    statement = select(models.ScientificArea).where(models.ScientificArea.name == "Biology")
    biology = db.exec(statement).first()
    
    if not biology:
        biology_area = models.ScientificArea(name="Biology")
        db.add(biology_area)
        db.commit()
        db.refresh(biology_area)

    statement = select(models.ScientificArea).where(models.ScientificArea.name == "Physics")
    physics_area = db.exec(statement).first()
    
    if not physics_area:
        physics_area = models.ScientificArea(name="Physics")
        db.add(physics_area)
        db.commit()
        db.refresh(physics_area)

    # Define dummy scholarships
    dummy_scholarships = [
        models.Scholarship(
            name="Scholarship A",
            description="A brief description of Scholarship A.",
            publisher="University of XYZ",
            scientific_areas=[biology],  # Change this if you have scientific area data
            type="Research Initiation Scholarship",
            deadline=date(2024, 12, 31),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=models.ScholarshipStatus.draft,
            edict_id=None
        ),
        models.Scholarship(
            name="Scholarship B",
            description="A brief description of Scholarship B.",
            publisher="Institute of ABC",
            scientific_areas=[computer_science_area, physics_area],  # Change this if you have scientific area data
            type="Research Scholarship",
            deadline=date(2024, 11, 15),
            created_at=datetime.today(),
            approved_at=None,
            results_at=None,
            status=models.ScholarshipStatus.purposed,
            edict_id=None
        )
    ]

    # Insert dummy scholarships into the database
    db.add_all(dummy_scholarships)
    db.commit()
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
