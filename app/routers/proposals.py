import shutil
from datetime import date, datetime
from typing import Annotated, List, Optional
from app import schemas
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter, HTTPException, Depends, Form, UploadFile, File
from sqlmodel import Session, select
from app.database import get_session
from app.models.models import Edict, DocumentTemplate, Jury, Scholarship, ScientificArea, ScholarshipStatus
import os


router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]

APPLICATION_FILES_DIR = os.getenv("APPLICATION_FILES_DIR", "application_files")
EDICT_FILES_DIR = os.getenv("EDICT_FILES_DIR", "edict_files")
os.makedirs(APPLICATION_FILES_DIR, exist_ok=True)
os.makedirs(EDICT_FILES_DIR, exist_ok=True)

router.mount("/edict_files", StaticFiles(directory=EDICT_FILES_DIR), name="edict_files")
router.mount("/application_files", StaticFiles(directory=APPLICATION_FILES_DIR), name="application_files")


# --------------------------- Auxiliar Functions ---------------------------

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

    os.makedirs(directory, exist_ok=True)

    # Sanitize the filename to prevent directory traversal attacks
    filename = os.path.basename(file.filename)
    if filename != file.filename or '..' in filename or filename.startswith('/'):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = os.path.join(directory, filename)

    print(filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not save file.")

    file_path = os.path.join(directory, file.filename)
    # with open(file_path, "wb") as f:
    #     f.write(file.file.read())
    return file_path

def create_edict_record(db: Session, edict_file: UploadFile, name: Optional[str] = None) -> Edict:
    # Get the filename without extension and set a default name if necessary
    edict_name = name or get_filename_without_extension(edict_file) or "default_filename"
    
    # Save the edict file
    edict_file_location = save_file(edict_file, "edict_files")

    # Create the edict record
    new_edict = Edict(
        name=edict_name,
        file_path=edict_file_location
    )
    db.add(new_edict)
    db.commit()
    db.refresh(new_edict)
    return new_edict

def create_document(db: Session, proposal_id: int, file: UploadFile, required: bool = True, template: bool = True) -> DocumentTemplate:
    document_name = get_filename_without_extension(file)

    if not document_name:
        raise HTTPException(status_code=400, detail="Document name could not be determined")

    # Save the document file
    file_location = ""
    if template:
        file_location = save_file(file, "application_files")

    # Create the document template record
    new_document = DocumentTemplate(
        scholarship_id=proposal_id,
        name=document_name,
        file_path=file_location,
        required=required,
        template=template
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    return new_document

# --------------------------- PROPOSALS ---------------------------

# Combined endpoint to create a proposal and upload required documents
@router.post("/proposals", response_model=schemas.Scholarship)
def create_proposal(
    db: SessionDep, # type: ignore
    name: str = Form(...),
    description: Optional[str] = Form(None),
    publisher: str = Form(...),
    type: str = Form(...),
    jury: Optional[List[int]] = Form(None),
    deadline: Optional[date] = Form(None),
    scientific_areas: List[str] = Form(None),
    edict_file: UploadFile = File(...),
    document_file: Optional[List[UploadFile]] = File(None),
    document_template: Optional[List[bool]] = Form(None),
    document_required: Optional[List[bool]] = Form(None)
):
    # Query the database for scientific areas based on the provided names
    associated_scientific_areas = []
    for area_name in scientific_areas or []:
        # Check if the scientific area already exists in the database
        area = db.exec(select(ScientificArea).where(ScientificArea.name == area_name)).first()
        if area:
            associated_scientific_areas.append(area)
        else:
            new_area = ScientificArea(name=area_name)
            db.add(new_area)
            db.commit()
            db.refresh(new_area)
            associated_scientific_areas.append(new_area)

    if document_file:
        num_files = len(document_file)
        print(num_files) 
        # Provide default values if flags are None
        document_template = document_template or [False] * num_files
        document_required = document_required or [False] * num_files
        print(document_file) 
        print(document_template) 
        print(document_required) 

        if document_template and len(document_template) != num_files:
            raise HTTPException(status_code=400, detail="Number of 'template' flags must match number of documents.")
        if document_required and len(document_required) != num_files:
            raise HTTPException(status_code=400, detail="Number of 'required' flags must match number of documents.")

    # Create an edict record
    new_edict = create_edict_record(db, edict_file)

    associated_jury = []
    for jury_id in jury or []:
        jury = db.get(Jury, jury_id)
        if not jury:
            raise HTTPException(status_code=404, detail=f"Jury with id {jury_id} not found")
        associated_jury.append(jury)

    # Create the proposal and associate it with the edict
    new_proposal = Scholarship(
        name=name,
        description=description,
        publisher=publisher,
        type=type,
        jury=associated_jury,
        deadline=deadline,
        status=ScholarshipStatus.draft,
        edict_id=new_edict.id,
        scientific_areas=associated_scientific_areas
    )
    db.add(new_proposal)
    db.commit()
    db.refresh(new_proposal)

    if new_proposal.id is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve proposal ID.")

    # Update document file(s) if provided and not empty
    for idx, file in enumerate(document_file or []):
        required_flag = document_required[idx] if document_required else False  # Default to False if not provided
        template_flag = document_template[idx] if document_template else False  # Default to False if not provided
        create_document(db, new_proposal.id, file, required_flag, template_flag)

    return new_proposal

# ---------- ENDPOINT TO UPLOAD A PROPOSAL ----------
@router.put("/proposals/{proposal_id}", response_model=schemas.Scholarship)
def update_proposal(
    db: SessionDep, # type: ignore
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
    document_template: Optional[List[bool]] = Form(None),
    document_required: Optional[List[bool]] = Form(None),
    scientific_areas: Optional[List[str]] = Form(None)
):
    proposal = db.get(Scholarship, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if document_file:
        num_files = len(document_file)
        
        # Provide default values if flags are None
        document_template = document_template or [False] * num_files
        document_required = document_required or [False] * num_files

        if document_template and len(document_template) != num_files:
            raise HTTPException(status_code=400, detail="Number of 'template' flags must match number of documents.")
        if document_required and len(document_required) != num_files:
            raise HTTPException(status_code=400, detail="Number of 'required' flags must match number of documents.")

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
    proposal.status = ScholarshipStatus(status) if status is not None else proposal.status

    if scientific_areas:
        proposal.scientific_areas.clear()
        for area_name in scientific_areas:
            area = db.exec(select(ScientificArea).where(ScientificArea.name == area_name)).first()
            if not area:
                # Create new scientific area if it doesn't exist
                area = ScientificArea(name=area_name)
                db.add(area)
                db.commit()
                db.refresh(area)
            proposal.scientific_areas.append(area)
      
    if jury is not None:
        proposal.jury.clear()
        for jury_id in jury:
            jury = db.get(Jury, jury_id)
            if not jury:
                raise HTTPException(status_code=404, detail=f"Jury with id {jury_id} not found")
            proposal.jury.append(jury)

    # Update edict file if provided and not empty
    if edict_file:
        create_edict_record(db, edict_file)

    # Update document file(s) if provided and not empty
    for idx, file in enumerate(document_file or []):
        required_flag = document_required[idx] if document_required else False  # Default to False if not provided
        template_flag = document_template[idx] if document_template else False  # Default to False if not provided
        create_document(db, proposal.id, file, required_flag, template_flag)

    db.commit()
    db.refresh(proposal)
    return proposal

# ---------- ENDPOINT TO SUBMIT A PROPOSAL FOR REVIEW ----------
@router.post("/proposals/{proposal_id}/submit", response_model=dict)
def submit_proposal(proposal_id: int, db: SessionDep): # type: ignore
    proposal = db.get(Scholarship, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if ScholarshipStatus(proposal.status) not in [ScholarshipStatus.draft, ScholarshipStatus.under_review]:
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
    proposal.status = ScholarshipStatus.under_review
    db.commit()
    return {"message": "Proposal submitted successfully. It will be reviewed shortly."}