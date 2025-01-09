import boto3
import json
import os
import shutil
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Annotated, Optional, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header, UploadFile, File, Form, Query
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, SQLModel, select
from .database import engine
from . import models, schemas
from datetime import date, datetime
from contextlib import asynccontextmanager
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from apscheduler.schedulers.background import BackgroundScheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    SQLModel.metadata.create_all(engine)
    yield

QUEUE_URL = str(os.getenv("QUEUE_URL"))

DATABASE_URL = str(os.getenv("DATABASE_URL", "sqlite:///todo.db"))
SECRET_KEY = str(os.getenv("SECRET_KEY", "K%!MaoL26XQe8iGAAyDrmbkw&bqE$hCPw4hSk!Hf"))
REGION = str(os.getenv("REGION"))
USER_POOL_ID = str(os.getenv("USER_POOL_ID"))
FRONTEND_URL = str(os.getenv("FRONTEND_URL"))
COGNITO_KEYS_URL = (
    f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
)
APPLICATION_FILES_DIR = os.getenv("APPLICATION_FILES_DIR", "application_files")
EDICT_FILES_DIR = os.getenv("EDICT_FILES_DIR", "edict_files")

os.makedirs(APPLICATION_FILES_DIR, exist_ok=True)
os.makedirs(EDICT_FILES_DIR, exist_ok=True)

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": True}, lifespan=lifespan)

app.mount(
    "/scholarships/edict_files",
    StaticFiles(directory=EDICT_FILES_DIR),
    name="edict_files",
)
app.mount(
    "/scholarships/application_files",
    StaticFiles(directory=APPLICATION_FILES_DIR),
    name="application_files",
)

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

sqs = boto3.client(
    'sqs',
    region_name=REGION
)

# Dependency to get DB session
def get_session():
    with Session(engine) as session:
        yield session


oauth2_scheme = HTTPBearer()

cognito_client = boto3.client('cognito-idp',
    region_name=REGION
)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)):
    token = credentials.credentials

    try:
        # Fetch public keys from AWS Cognito
        jwks_client = PyJWKClient(COGNITO_KEYS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate the token
        payload = jwt.decode(token, signing_key.key, algorithms=["RS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    
def verify_token_string(token: str):
    if not token.startswith('Bearer '):
        return False, "Invalid token format"
    
    token = token.split(' ')[1]

    try:
        # Fetch public keys from AWS Cognito
        jwks_client = PyJWKClient(COGNITO_KEYS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate the token
        payload = jwt.decode(token, signing_key.key, algorithms=["RS256"])
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, "Token expired"
    except Exception:
        return False, "Invalid token"


TokenDep = Annotated[Dict, Depends(verify_token)]
SessionDep = Annotated[Session, Depends(get_session)]

# Scheduler for deadline detection mecanism
scheduler = BackgroundScheduler()
backgroundTasks = BackgroundTasks()

async def get_user_groups(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    
    valid, token = verify_token_string(authorization)

    if not valid:
        raise HTTPException(status_code=401, detail=token)
    
    try:
        # Get user's groups
        groups_response = cognito_client.admin_list_groups_for_user(
            UserPoolId=os.getenv('USER_POOL_ID'),
            Username=token['username']
        )
        
        return [group['GroupName'] for group in groups_response['Groups']]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token or user not found")

def update_scholarship_status():
    with Session(engine) as session:
        today = datetime.today().date()
        scholarships = session.exec(
            select(models.Scholarship).where(
                models.Scholarship.status == models.ScholarshipStatus.open,
                models.Scholarship.deadline < today,
            )
        ).all()

        for scholarship in scholarships:
            message = {
                "scholarship_id": scholarship.id,
                "spots": scholarship.spots,
                "jury_ids": [jury.id for jury in scholarship.jury],
                "closed_at": scholarship.deadline.isoformat(),
            }
            send_to_sqs(message)
            scholarship.status = models.ScholarshipStatus.jury_evaluation
            session.add(scholarship)

        session.commit()


scheduler.add_job(
    update_scholarship_status, "interval", seconds=10
) 
scheduler.start()

def send_to_sqs(message: dict):
    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message),
    )
    print(f"Message sent to SQS: {response['MessageId']}")
    return response

def read_sqs():
    response = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=5,
    )
    messages = response.get('Messages', [])
    for message in messages:
        body = json.loads(message['Body'])
        print(f"Scholarship ID: {body.get('scholarship_id')}, Timestamp: {body.get('timestamp')}")
    return response

@app.get("/sqsTestSend")
def testSend_sqs():
    message = { 
        "scholarship_id": 1,
        "timestamp": datetime.now().timestamp()
    }
    send_to_sqs(message)
    return {"status": "ok"}

@app.get("/sqsTestRead")
def testRead_sqs():
    return read_sqs()


@app.get("/scholarships/health")
def health_check():
    return {"status": "ok"}

@app.get("/scholarships/jury-members", response_model=List[schemas.UserBasic])
async def get_jury_members(groups: List[str] = Depends(get_user_groups)):
    """Get all jury members - only accessible by users in the 'proposals' group"""
    
    if 'proposers' not in groups:
        raise HTTPException(
            status_code=403,
            detail="Only users in the proposers group can access this endpoint"
        )
    
    try:
        # List users with the 'jury' group filter
        response = cognito_client.list_users_in_group(
            UserPoolId=os.getenv('USER_POOL_ID'),
            GroupName='jury'
        )

        jury_members = []
        for user in response['Users']:
            attributes = {
                attr['Name']: attr['Value']
                for attr in user['Attributes']
            }
            
            jury_members.append(schemas.UserBasic(
                id=user['Username'],
                name=attributes.get('name', user['Username'])
            ))
            
        return jury_members
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching jury members")

@app.put("/scholarships/{scholarship_id}/status/jury_evaluation")
def update_scholarship_status_to_jury_evaluation(scholarship_id: int, db: SessionDep):
    # test function to update scholarship status to jury evaluation
    scholarship = db.get(models.Scholarship, scholarship_id)
    if not scholarship:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    
    scholarship.status = models.ScholarshipStatus.jury_evaluation
    db.commit()
    db.refresh(scholarship)
    return {"message": "Scholarship status updated to jury evaluation", "scholarship": scholarship}

@app.get("/scholarships/jury/{user_id}", response_model=List[schemas.Scholarship])
def get_scholarships_for_jury_member(
        db: SessionDep,
        token: TokenDep,
        user_id: str
    ):
    # Retrieve scholarships that are currently under jury evaluation and assigned to the user
    statement = (
        select(models.Scholarship)
        .join(models.ScholarshipJuryLink)
        .join(models.Jury)
        .where(
            models.Jury.id == user_id,
            models.Scholarship.status == models.ScholarshipStatus.jury_evaluation,
        )
    )
    scholarships = db.exec(statement).all()
    return scholarships


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
    deadline_end: Optional[date] = Query(None),
):

    offset = (page - 1) * limit

    statement = select(models.Scholarship)

    if status:
        statement = statement.where(models.Scholarship.status.in_(status))
    elif not publisher:  # If no status filter and no publisher, apply default status filter
        default_statuses = [
            models.ScholarshipStatus.open,
            models.ScholarshipStatus.jury_evaluation,
            models.ScholarshipStatus.closed
        ]
        statement = statement.where(models.Scholarship.status.in_(default_statuses))

    if name:
        statement = statement.where(models.Scholarship.name.ilike(f"%{name}%"))
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

    unique_scholarships = []

    for scholarship in results:
        if scholarship not in unique_scholarships:
            unique_scholarships.append(scholarship)

    return unique_scholarships


@app.get("/scholarships/filters", response_model=schemas.FilterOptionsResponse)
def get_filter_options(db: SessionDep):
    # Retrieve distinct types of scholarships
    types = db.exec(select(models.Scholarship.type).distinct()).all()
    types = [t for t in types if t]  # Extract values from tuples and exclude None

    # Retrieve all scientific areas
    scientific_areas = db.exec(select(models.ScientificArea.name)).all()
    scientific_areas = [sa for sa in scientific_areas if sa]

    # Get all possible statuses from the ScholarshipStatus enum
    status = [
        schemas.ScholarshipStatus(status.value) for status in models.ScholarshipStatus
    ]

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
@app.post("/scholarships/proposals", response_model=schemas.Scholarship)
def create_proposal(
    db: SessionDep,
    token: TokenDep,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    publisher: str = Form(...),
    type: str = Form(...),
    spots: int = Form(...),
    jury: Optional[List[str]] = Form(None),
    deadline: Optional[date] = Form(None),
    scientific_areas: List[str] = Form(None),
    edict_file: UploadFile = File(...),
    document_file: Optional[List[UploadFile]] = File(None),
    document_name: Optional[List[str]] = Form(None),
    document_template: Optional[List[bool]] = Form(None),
    document_required: Optional[List[bool]] = Form(None),
):
    # Query the database for scientific areas based on the provided names
    associated_scientific_areas = []
    for area_name in scientific_areas or []:
        # Check if the scientific area already exists in the database
        area = db.exec(
            select(models.ScientificArea).where(models.ScientificArea.name == area_name)
        ).first()
        if area:
            associated_scientific_areas.append(area)
        else:
            new_area = models.ScientificArea(name=area_name)
            db.add(new_area)
            db.commit()
            db.refresh(new_area)
            associated_scientific_areas.append(new_area)

    if document_name:
        num_files = len(document_name)
        # Provide default values if flags are None
        document_template = document_template or [False] * num_files
        document_required = document_required or [False] * num_files

        if document_template and len(document_template) != num_files:
            raise HTTPException(
                status_code=400,
                detail="Number of 'template' flags must match number of documents.",
            )
        if document_required and len(document_required) != num_files:
            raise HTTPException(
                status_code=400,
                detail="Number of 'required' flags must match number of documents.",
            )

    # Create an edict record
    new_edict = create_edict_record(db, edict_file)

    associated_jury = []

    for juror in jury or []:
        juror = json.loads(juror)
        jury = db.get(models.Jury, juror.get("id"))

        if not jury:
            jury = models.Jury(id=juror.get("id"), name=juror["name"])
            db.add(jury)
            db.commit()
            db.refresh(jury)

        associated_jury.append(jury)

    # Create the proposal and associate it with the edict
    new_proposal = models.Scholarship(
        name=name,
        description=description,
        publisher=publisher,
        type=type,
        spots=spots,
        jury=associated_jury,
        deadline=deadline,
        status=models.ScholarshipStatus.under_review,
        edict_id=new_edict.id,
        scientific_areas=associated_scientific_areas,
    )
    db.add(new_proposal)
    db.commit()
    db.refresh(new_proposal)

    if new_proposal.id is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve proposal ID.")

    # Update document file(s) if provided and not empty
    for idx, name in enumerate(document_name or []):
        file = document_file[idx] if document_file else None
        required_flag = (
            document_required[idx] if document_required else False
        )  # Default to False if not provided
        template_flag = (
            document_template[idx] if document_template else False
        )  # Default to False if not provided
        create_document(db, new_proposal.id, file, name, required_flag, template_flag)

    return new_proposal


# Endpoint to update an existing proposal
@app.put("/scholarships/proposals/{proposal_id}", response_model=schemas.Scholarship)
def update_proposal(
    db: SessionDep,
    token: TokenDep,
    proposal_id: int,
    name: Optional[str] = Form(None),
    jury: Optional[List[str]] = Form(None),
    status: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    publisher: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    edict_file: Optional[UploadFile] = File(None),
    document_file: Optional[List[UploadFile]] = File(None),
    document_name: Optional[List[str]] = Form(None),
    document_template: Optional[List[bool]] = Form(None),
    document_required: Optional[List[bool]] = Form(None),
    scientific_areas: Optional[List[str]] = Form(None),
):
    proposal = db.get(models.Scholarship, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if document_name:
        num_files = len(document_name)

        # Provide default values if flags are None
        document_template = document_template or [False] * num_files
        document_required = document_required or [False] * num_files

        if document_template and len(document_template) != num_files:
            raise HTTPException(
                status_code=400,
                detail="Number of 'template' flags must match number of documents.",
            )
        if document_required and len(document_required) != num_files:
            raise HTTPException(
                status_code=400,
                detail="Number of 'required' flags must match number of documents.",
            )

    if deadline is not None:
        try:
            # Assuming the deadline is in 'YYYY-MM-DD' format
            deadline_datetime = datetime.strptime(deadline, "%Y-%m-%d")
            proposal.deadline = (
                deadline_datetime
                if deadline_datetime is not None
                else proposal.deadline
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format for deadline. Expected 'YYYY-MM-DD'.",
            )

    # Update the proposal's fields if provided in the request
    proposal.name = name if name is not None else proposal.name
    proposal.description = (
        description if description is not None else proposal.description
    )
    proposal.publisher = publisher if publisher is not None else proposal.publisher
    proposal.type = type if type is not None else proposal.type
    proposal.status = (
        models.ScholarshipStatus(status) if status is not None else proposal.status
    )

    if scientific_areas:
        proposal.scientific_areas.clear()
        for area_name in scientific_areas:
            area = db.exec(
                select(models.ScientificArea).where(
                    models.ScientificArea.name == area_name
                )
            ).first()
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
                raise HTTPException(
                    status_code=404, detail=f"Jury with id {jury_id} not found"
                )
            proposal.jury.append(jury)

    # Update edict file if provided and not empty
    if edict_file:
        create_edict_record(db, edict_file)

    # Update document file(s) if provided and not empty
    for idx, name in enumerate(document_name or []):
        file = document_file[idx] if document_file else None
        required_flag = (
            document_required[idx] if document_required else False
        )  # Default to False if not provided
        template_flag = (
            document_template[idx] if document_template else False
        )  # Default to False if not provided
        create_document(db, proposal.id, file, name, required_flag, template_flag)

    db.commit()
    db.refresh(proposal)
    return proposal


# Endpoint to submit a proposal for review
@app.post("/scholarships/proposals/{proposal_id}/submit", response_model=dict)
def submit_proposal(proposal_id: int, db: SessionDep, token: TokenDep):
    proposal = db.get(models.Scholarship, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if models.ScholarshipStatus(proposal.status) not in [
        models.ScholarshipStatus.draft,
        models.ScholarshipStatus.under_review,
    ]:
        raise HTTPException(
            status_code=400,
            detail="Cannot submit a proposal that is not in draft or under review status.",
        )

    # Check if all required fields are filled before submission
    required_fields = {
        "name": proposal.name,
        "publisher": proposal.publisher,
        "type": proposal.type,
        "deadline": proposal.deadline,
        "scientific_areas": proposal.scientific_areas,
        "edict": proposal.edict,
    }

    # Check if any required field is missing
    missing_fields = [
        field_name for field_name, value in required_fields.items() if not value
    ]
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit proposal. The following required fields are missing: {', '.join(missing_fields)}",
        )

    # Validate that at least one scientific area is associated
    if not proposal.scientific_areas:
        raise HTTPException(
            status_code=400,
            detail="At least one scientific area must be associated with the proposal.",
        )
    # Validate that at least one document is associated
    if not proposal.documents:
        raise HTTPException(
            status_code=400,
            detail="At least one document must be associated if the proposal.",
        )

    proposal.status = models.ScholarshipStatus.under_review
    db.commit()
    return {"message": "Proposal submitted successfully. It will be reviewed shortly."}

@app.put("/scholarships/secretary/status")
def accept_sholarship_proposal(scholarship_id: int, accepted: bool, db: SessionDep, token: TokenDep):
    # update scholarship status to under review
    scholarship = db.get(models.Scholarship, scholarship_id)
    if not scholarship:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    
    if accepted:
        scholarship.status = models.ScholarshipStatus.open
    else:
        scholarship.status = models.ScholarshipStatus.draft

    db.commit()
    db.refresh(scholarship)
    return {"message": "Scholarship status updated to under evalution (secretary)", "scholarship": scholarship}

@app.get("/scholarships/secretary/under_review", response_model=List[schemas.Scholarship])
def get_scholarships_under_review(db: SessionDep, token: TokenDep):
    # Query the database for scholarships with the status 'under_review'
    scholarships = (
        db.exec(select(models.Scholarship)
        .where(models.Scholarship.status == models.ScholarshipStatus.under_review))
    )
    return scholarships

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
    if filename != file.filename or ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = os.path.join(directory, filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not save file.")

    file_path = os.path.join(directory, file.filename)
    return file_path


def create_edict_record(
    db: Session, edict_file: UploadFile, name: Optional[str] = None
) -> models.Edict:
    # Get the filename without extension and set a default name if necessary
    edict_name = (
        name or get_filename_without_extension(edict_file) or "default_filename"
    )

    # Save the edict file
    edict_file_location = save_file(edict_file, "edict_files")

    # Create the edict record
    new_edict = models.Edict(name=edict_name, file_path=edict_file_location)
    db.add(new_edict)
    db.commit()
    db.refresh(new_edict)
    return new_edict


def create_document(
    db: Session,
    proposal_id: int,
    file: UploadFile,
    name: str,
    required: bool = True,
    template: bool = True,
) -> models.DocumentTemplate:
    # Save the document file
    file_location = ""
    if template:
        file_location = save_file(file, "application_files")

    # Create the document template record
    new_document = models.DocumentTemplate(
        scholarship_id=proposal_id,
        name=name,
        file_path=file_location,
        required=required,
        template=template,
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    return new_document
