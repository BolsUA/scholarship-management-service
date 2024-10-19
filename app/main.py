from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": True})

proposals_db = {}

# Sample data for demonstration
scholarships_db = [
    {
        "id": 1,
        "name": "Scholarship A",
        "scientific_area": "Computer Science",
        "type": "Full",
        "application_deadline": date(2024, 12, 31),
        "description": "A brief description of Scholarship A."
    },
    {
        "id": 2,
        "name": "Scholarship B",
        "scientific_area": "Physics",
        "type": "Partial",
        "application_deadline": date(2024, 11, 15),
        "description": "A brief description of Scholarship B."
    },
    {
        "id": 3,
        "name": "Scholarship B",
        "scientific_area": "Physics",
        "type": "Partial",
        "application_deadline": date(2024, 11, 15),
        "description": "A brief description of Scholarship B."
    },
    # Add more sample scholarships as needed
]

class Scholarship(BaseModel):
    id: int
    name: str
    scientific_area: str
    type: str
    application_deadline: date
    description: str
    publisher_id: int
    jury: List[str]
    documents: List[str]
    created_at: date
    approves_at: date
    results_at: date

# Endpoint to retrieve all scholarships
@app.get("/scholarships", response_model=List[Scholarship])
def get_scholarships(scientific_area: Optional[str] = None, type: Optional[str] = None,
                     page: int = 1, limit: int = 10):
    filtered_scholarships = scholarships_db

    # Apply filtering based on query parameters
    if scientific_area:
        filtered_scholarships = [sch for sch in filtered_scholarships if sch["scientific_area"] == scientific_area]
    if type:
        filtered_scholarships = [sch for sch in filtered_scholarships if sch["type"] == type]

    # Implement pagination
    start = (page - 1) * limit
    end = start + limit
    paginated_scholarships = filtered_scholarships[start:end]

    return paginated_scholarships

# Endpoint to retrieve a single scholarship by ID
@app.get("/scholarships/{id}", response_model=Scholarship)
def get_scholarship(id: int):
    for scholarship in scholarships_db:
        if scholarship["id"] == id:
            return scholarship
    raise HTTPException(status_code=404, detail="Scholarship not found")

# Endpoint to retrieve filter options
@app.get("/scholarships/filters")
def get_filters():
    scientific_areas = list(set(sch["scientific_area"] for sch in scholarships_db))
    types = list(set(sch["type"] for sch in scholarships_db))
    return {
        "scientific_areas": scientific_areas,
        "types": types
    }

# Endpoint to create a new scholarship proposal
@app.post("/proposals", response_model=dict)
def create_proposal(proposal: Scholarship):
    proposal_id = f"proposal-{len(proposals_db) + 1}"
    proposals_db[proposal_id] = {
        **proposal.model_dump(),
    }
    return {"message": "Proposal created successfully.", "proposal_id": proposal_id}

# Endpoint to upload required document templates for a proposal
@app.post("/proposals/{id}/documents")
def upload_document(id: str, document_name: str = Form(...), file: UploadFile = File(...)):
    if id not in proposals_db:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    proposal = proposals_db[id]
    
    # Save the uploaded file (mock implementation)
    # In a real application, you would save the file to a storage location
    file_location = f"/path/to/storage/{file.filename}"
    
    # Update proposal with the uploaded template status (resume, cover letter, etc...)
    proposal["template_uploaded"][document_name] = True
    
    return {"message": "Template uploaded successfully."}

# Endpoint to retrieve details of a specific proposal
@app.get("/proposals/{id}", response_model=Scholarship)
def get_proposal(id: str):
    if id not in proposals_db:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposals_db[id]

# Endpoint to update an existing proposal
@app.put("/proposals/{id}", response_model=dict)
def update_proposal(id: str, proposal: Scholarship):
    if id not in proposals_db:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Update the proposal in the database
    proposals_db[id] = {
        **proposal.model_dump(),
        "id": id,
        "template_uploaded": {doc.name: proposals_db[id]["template_uploaded"].get(doc.name, False) for doc in proposal.required_documents}
    }
    return {"message": "Proposal updated successfully."}

# Endpoint to submit a proposal for review
@app.post("/proposals/{id}/submit", response_model=dict)
def submit_proposal(id: str):
    if id not in proposals_db:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    proposal = proposals_db[id]
    
    # Validate that all required fields and templates are completed
    for doc in proposal["required_documents"]:
        if doc["template_required"] and not proposal["template_uploaded"][doc["name"]]:
            raise HTTPException(status_code=400, detail=f"Required document template for '{doc['name']}' is missing.")
    
    # Mark the proposal as submitted (mock implementation)
    # Update a database status and notify a reviewer
    return {"message": "Proposal submitted successfully. It will be reviewed shortly."}

