import os
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Annotated, Optional
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query
from sqlmodel import Session, SQLModel, select
from .database import engine
from . import models, schemas
from datetime import date, datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": True}, lifespan=lifespan)

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

    # Create or get jury members
    jury_to_create = ["Dr. Alice", "Dr. Bob", "Dr. Carol"]
    jury = {}

    for jury_name in jury_to_create:
        juror = db.exec(select(models.Jury).where(models.Jury.name == jury_name)).first()
        if not juror:
            juror = models.Jury(name=jury_name)
            db.add(juror)
            db.commit()
            db.refresh(juror)
        jury[jury_name] = juror

    # Define dummy scholarships
    dummy_scholarships = [
        models.Scholarship(
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
            status=models.ScholarshipStatus.jury_evaluation,
            edict_id=None
        ),
        models.Scholarship(
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
            status=models.ScholarshipStatus.open,
            edict_id=None
        ),
        models.Scholarship(
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
def get_scholarships(
    db: SessionDep, 
    page: int = 1, 
    limit: int = 10,
    name: Optional[str] = Query(None),
    status: Optional[List[models.ScholarshipStatus]] = Query(None),
    scientific_areas: Optional[List[str]] = Query(None),
    publisher: Optional[str] = Query(None),
    types: Optional[List[str]] = Query(None),
    jury_name: Optional[str] = Query(None),
    deadline_start: Optional[date] = Query(None),
    deadline_end: Optional[date] = Query(None)
    ):

    offset = (page - 1) * limit

    statement = select(models.Scholarship)

    if name:
        statement = statement.where(models.Scholarship.name.ilike(f"%{name}%"))
    if status:
        statement = statement.where(models.Scholarship.status.in_(status))
    if publisher:
        statement = statement.where(models.Scholarship.publisher == publisher)
    if types:
        statement = statement.where(models.Scholarship.type.in_(types))
    if deadline_start:
        statement = statement.where(models.Scholarship.deadline >= deadline_start)
    if deadline_end:
        statement = statement.where(models.Scholarship.deadline <= deadline_end)
    if scientific_areas:
        # Join with the scientific area model to filter by multiple area names
        statement = (
            statement.join(models.ScholarshipScientificAreaLink)
            .join(models.ScientificArea)
            .where(models.ScientificArea.name.in_(scientific_areas))
        )

    if jury_name:
        # Join with the Jury model to filter by jury name
        statement = (
            statement.join(models.ScholarshipJuryLink)
            .join(models.Jury)
            .where(models.Jury.name == jury_name)
        )
    statement = statement.offset(offset).limit(limit)

    results = db.exec(statement).all()

    return results

@app.get("/scholarships/filters", response_model=schemas.FilterOptionsResponse)
def get_filter_options(db: SessionDep):
    # Retrieve distinct types of scholarships
    types = db.exec(select(models.Scholarship.type).distinct()).all()
    types = [t for t in types if t]  # Extract values from tuples and exclude None

    # Retrieve all scientific areas
    scientific_areas = db.exec(select(models.ScientificArea.name)).all()
    scientific_areas = [sa for sa in scientific_areas if sa]

    # Get all possible statuses from the ScholarshipStatus enum
    status = [schemas.ScholarshipStatus(status.value) for status in models.ScholarshipStatus]

    # Retrieve distinct publishers
    publishers = db.exec(select(models.Scholarship.publisher).distinct()).all()
    publishers = [p for p in publishers if p]

    # Retrieve distinct deadlines
    deadlines = db.exec(select(models.Scholarship.deadline).distinct()).all()
    deadlines = [d for d in deadlines if d]

    return schemas.FilterOptionsResponse(
        types=types,
        scientific_areas=scientific_areas,
        status=status,
        publishers=publishers,
        deadlines=deadlines,
    )

# Endpoint to retrieve a single scholarship by ID
@app.get("/scholarships/{id}/details", response_model=schemas.Scholarship)
def get_scholarship(id: int, db: SessionDep):
    statement = select(models.Scholarship).where(models.Scholarship.id == id)
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return result

# Combined endpoint to create a proposal and upload required documents
@app.post("/proposals", response_model=schemas.Scholarship)
def create_proposal(
    db: SessionDep,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    publisher: str = Form(...),
    type: str = Form(...),
    jury: Optional[List[int]] = Form(None),
    deadline: Optional[date] = Form(None),
    scientific_areas: List[str] = Form(None),
    edict_file: UploadFile = File(...),
    file: Optional[List[UploadFile]] = File(None)
):
    print(scientific_areas)
    # Query the database for scientific areas based on the provided names
    associated_scientific_areas = []
    for area_name in scientific_areas or []:
        # Check if the scientific area already exists in the database
        area = db.exec(select(models.ScientificArea).where(models.ScientificArea.name == area_name)).first()
        if area:
            associated_scientific_areas.append(area)
        else:
            new_area = models.ScientificArea(name=area_name)
            db.add(new_area)
            db.commit()
            db.refresh(new_area)
            associated_scientific_areas.append(new_area)

    # Create an edict record
    new_edict = create_edict_record(db, edict_file)

    associated_jury = []
    for jury_id in jury or []:
        jury = db.get(models.Jury, jury_id)
        if not jury:
            raise HTTPException(status_code=404, detail=f"Jury with id {jury_id} not found")
        associated_jury.append(jury)

    # Create the proposal and associate it with the edict
    new_proposal = models.Scholarship(
        name=name,
        description=description,
        publisher=publisher,
        type=type,
        jury=associated_jury,
        deadline=deadline,
        status=models.ScholarshipStatus.draft,
        edict_id=new_edict.id,
        scientific_areas=associated_scientific_areas
    )
    db.add(new_proposal)
    db.commit()
    db.refresh(new_proposal)

    if new_proposal.id is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve proposal ID.")

    if file:
        for f in file:
            create_document(db, new_proposal.id, f)

    return new_proposal

# Endpoint to update an existing proposal
@app.put("/proposals/{proposal_id}", response_model=schemas.Scholarship)
def update_proposal(
    db: SessionDep,
    proposal_id: int,
    name: Optional[str] = Form(None),
    jury: Optional[List[int]] = Form(None),
    status: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    publisher: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    edict_file: Optional[UploadFile] = File(None),
    document_file: Optional[List[UploadFile]] = File(None),
    scientific_areas: Optional[List[str]] = Form(None)
):
    proposal = db.get(models.Scholarship, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if deadline is not None:
        try:
            # Assuming the deadline is in 'YYYY-MM-DD' format
            deadline_datetime = datetime.strptime(deadline, '%Y-%m-%d')
            proposal.deadline = deadline_datetime if deadline_datetime is not None else proposal.deadline
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format for deadline. Expected 'YYYY-MM-DD'."
            )

    # Update the proposal's fields if provided in the request
    proposal.name = name if name is not None else proposal.name
    proposal.description = description if description is not None else proposal.description
    proposal.publisher = publisher if publisher is not None else proposal.publisher
    proposal.type = type if type is not None else proposal.type
    proposal.status = models.ScholarshipStatus(status) if status is not None else proposal.status

    if scientific_areas:
        proposal.scientific_areas.clear()
        for area_name in scientific_areas:
            area = db.exec(select(models.ScientificArea).where(models.ScientificArea.name == area_name)).first()
            if not area:
                # Create new scientific area if it doesn't exist
                area = models.ScientificArea(name=area_name)
                db.add(area)
                db.commit()
                db.refresh(area)
            proposal.scientific_areas.append(area)
      
    if jury is not None:
        proposal.jury.clear()
        for jury_id in jury:
            jury = db.get(models.Jury, jury_id)
            if not jury:
                raise HTTPException(status_code=404, detail=f"Jury with id {jury_id} not found")
            proposal.jury.append(jury)

    # Update edict file if provided and not empty
    if edict_file:
        create_edict_record(db, edict_file)

    # Update document file(s) if provided and not empty
    if document_file:
        for doc in document_file:
            create_document(db, proposal.id, doc)

    db.commit()
    db.refresh(proposal)
    return proposal

# Endpoint to submit a proposal for review
@app.post("/proposals/{proposal_id}/submit", response_model=dict)
def submit_proposal(proposal_id: int, db: SessionDep):
    proposal = db.get(models.Scholarship, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if models.ScholarshipStatus(proposal.status) not in [models.ScholarshipStatus.draft, models.ScholarshipStatus.under_review]:
        raise HTTPException(status_code=400, detail="Cannot submit a proposal that is not in draft or under review status.")

    # Check if all required fields are filled before submission
    required_fields = {
        "name": proposal.name,
        "publisher": proposal.publisher,
        "type": proposal.type,
        "deadline": proposal.deadline,
        "scientific_areas": proposal.scientific_areas,
        "edict": proposal.edict
    }

    # Check if any required field is missing
    missing_fields = [field_name for field_name, value in required_fields.items() if not value]
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot submit proposal. The following required fields are missing: {', '.join(missing_fields)}"
        )

    # Validate that at least one scientific area is associated
    if not proposal.scientific_areas:
        raise HTTPException(status_code=400, detail="At least one scientific area must be associated with the proposal.")
    # Validate that at least one document is associated
    if not proposal.documents:
        raise HTTPException(status_code=400, detail="At least one document must be associated if the proposal.")

    # Update proposal status to "under_review"
    proposal.status = models.ScholarshipStatus.under_review
    db.commit()
    return {"message": "Proposal submitted successfully. It will be reviewed shortly."}

def get_filename_without_extension(file: Optional[UploadFile]) -> Optional[str]:
    if file is None or file.filename is None:
        return None
    # Split the filename into the name and extension
    filename, _ = os.path.splitext(file.filename)
    return filename

def save_file(file: UploadFile, directory: str) -> str:
    # Create the directory if it doesn't exist
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a valid filename.")

    # os.makedirs(directory, exist_ok=True)

    file_path = os.path.join(directory, file.filename)
    # with open(file_path, "wb") as f:
    #     f.write(file.file.read())
    return file_path

def create_edict_record(db: Session, edict_file: UploadFile, name: Optional[str] = None) -> models.Edict:
    # Get the filename without extension and set a default name if necessary
    edict_name = name or get_filename_without_extension(edict_file) or "default_filename"
    
    # Save the edict file
    edict_file_location = save_file(edict_file, "/edict_files")

    # Create the edict record
    new_edict = models.Edict(
        name=edict_name,
        file_path=edict_file_location
    )
    db.add(new_edict)
    db.commit()
    db.refresh(new_edict)
    return new_edict

def create_document(db: Session, proposal_id: int, file: UploadFile, required: bool = True) -> models.DocumentTemplate:
    document_name = get_filename_without_extension(file)

    if not document_name:
        raise HTTPException(status_code=400, detail="Document name could not be determined")

    # Save the document file
    file_location = save_file(file, "/docs")

    # Create the document template record
    new_document = models.DocumentTemplate(
        scholarship_id=proposal_id,
        name=document_name,
        file_path=file_location,
        required=required,
        template=True
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    return new_document
