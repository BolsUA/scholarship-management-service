# tests/test_main.py
import os

def test_create_dummy_scholarships(client):
    response = client.post("/scholarships/dummy")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3  # Assuming three dummy scholarships are created

    # Verify the names of the scholarships
    names = [scholarship["name"] for scholarship in data]
    assert "Scholarship A" in names
    assert "Scholarship B" in names
    assert "Scholarship C" in names

def test_get_scholarships_without_filters(client):
    response = client.get("/scholarships")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

def test_get_scholarships_with_name_filter(client):
    response = client.get("/scholarships", params={"name": "Scholarship A"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Scholarship A"

def test_get_scholarships_with_status_filter(client):
    response = client.get("/scholarships", params={"status": "Open"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "Open"

def test_get_scholarships_with_scientific_area_filter(client):
    response = client.get("/scholarships", params={"scientific_areas": "Biology"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    areas = [area["name"] for area in data[0]["scientific_areas"]]
    assert "Biology" in areas

def test_get_scholarships_filters(client):
    response = client.get("/scholarships/filters")
    assert response.status_code == 200
    data = response.json()
    assert "types" in data
    assert "scientific_areas" in data
    assert "status" in data
    assert "publishers" in data
    assert "deadlines" in data

def test_get_scholarship_by_id(client):
    # Create dummy scholarships
    response = client.post("/scholarships/dummy")
    scholarships = response.json()
    scholarship_id = scholarships[0]["id"]

    response = client.get(f"/scholarships/{scholarship_id}/details")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == scholarship_id
    assert data["name"] == scholarships[0]["name"]

def test_get_scholarship_by_invalid_id(client):
    response = client.get("/scholarships/9999/details")  # Assuming this ID doesn't exist
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Scholarship not found"

def test_create_proposal(client):
    # Prepare form data
    form_data = {
        "name": "Test Proposal",
        "publisher": "Test Publisher",
        "type": "Research Scholarship",
        "scientific_areas": ["Computer Science", "Biology"],
        "document_template": "true",
        "document_required": "true"
    }
    files = {
        "edict_file": ("edict.pdf", b"dummy content", "application/pdf"),
        "file": ("document.pdf", b"dummy content", "application/pdf"),
    }

    response = client.post("/proposals", data=form_data, files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Proposal"
    assert data["publisher"] == "Test Publisher"
    assert len(data["scientific_areas"]) == 2
    areas = [area["name"] for area in data["scientific_areas"]]
    assert "Computer Science" in areas
    assert "Biology" in areas

def test_create_proposal_with_multiple_scientific_areas_and_jury(client):
    # Create some scientific areas in the database
    area_names = ["Informatica", "Ciencia de dados"]

    # Prepare the form data
    form_data = {
        "name": "Test Proposal with Multiple Scientific Areas",
        "publisher": "Test Publisher",
        "type": "Research",
        "scientific_areas": area_names
    }
    files = {
        "edict_file": ("edict.pdf", b"edict content", "application/pdf")
    }

    # Send the POST request to create the proposal
    response = client.post(
        "/proposals",
        data=form_data,
        files=files,
    )

    assert response.status_code == 200
    proposal = response.json()

    response = client.post("/scholarships/dummy")
    assert response.status_code == 200
    dummy_scholarships = response.json()

    jury_ids = set()
    for scholarship in dummy_scholarships:
        for jury in scholarship.get("jury", []):
            jury_ids.add(jury["id"])

    jury_ids = list(jury_ids)  # Convert the set to a list

    # Prepare the form data for updating the proposal
    update_form_data = {
        "jury": jury_ids,  # List of jury IDs
    }

    proposal_id = proposal["id"]
    update_response = client.put(
        f"/proposals/{proposal_id}",
        data=update_form_data,
    )

    assert update_response.status_code == 200
    updated_proposal = update_response.json()

    # Check that the proposal has been created with the correct scientific areas
    assert proposal["name"] == "Test Proposal with Multiple Scientific Areas"
    assert len(proposal["scientific_areas"]) == 2
    retrieved_area_names = [area["name"] for area in proposal["scientific_areas"]]
    assert set(retrieved_area_names) == set(area_names)

    assert len(updated_proposal["jury"]) == len(jury_ids)
    updated_jury_ids = [jury["id"] for jury in updated_proposal["jury"]]
    assert set(updated_jury_ids) == set(jury_ids)

def test_create_proposal_missing_fields(client):
    form_data = {
        "publisher": "Test Publisher",  # Missing 'name'
        "type": "Research Scholarship",
        "scientific_areas": ["Computer Science"]
    }
    files = {
        "edict_file": ("edict.pdf", b"dummy content", "application/pdf")
    }

    response = client.post("/proposals", data=form_data, files=files)
    assert response.status_code == 422  # Unprocessable Entity

def test_update_proposal(client):
    # Create a proposal
    form_data = {
        "name": "Original Proposal",
        "publisher": "Original Publisher",
        "type": "Research Scholarship",
        "scientific_areas": ["Physics"],
    }
    files = {
        "edict_file": ("edict.pdf", b"dummy content", "application/pdf"),
    }
    create_response = client.post("/proposals", data=form_data, files=files)
    assert create_response.status_code == 200
    proposal = create_response.json()
    proposal_id = proposal["id"]

    # Update the proposal
    updated_data = {
        "name": "Updated Proposal",
        "publisher": "Updated Publisher",
        "scientific_areas": ["Informatics"]
    }

    update_response = client.put(
        f"/proposals/{proposal_id}",
        data=updated_data,
    )

    assert update_response.status_code == 200
    updated_proposal = update_response.json()
    assert updated_proposal["name"] == "Updated Proposal"
    assert updated_proposal["publisher"] == "Updated Publisher"
    assert len(updated_proposal["scientific_areas"]) == 1
    assert updated_proposal["scientific_areas"][0]["name"] == "Informatics"

def test_update_proposal_with_files(client):
    # Create a proposal
    form_data = {
        "name": "Original Proposal",
        "publisher": "Original Publisher",
        "type": "Research Scholarship",
        "scientific_areas": ["Physics"]
    }
    files = {
        "edict_file": ("edict.pdf", b"dummy content", "application/pdf")
    }
    create_response = client.post("/proposals", data=form_data, files=files)
    assert create_response.status_code == 200
    proposal = create_response.json()
    proposal_id = proposal["id"]

    # Update the proposal
    updated_data = {
        "name": "Updated Proposal",
        "publisher": "Updated Publisher",
        "scientific_areas": ["Biology"]
    }
    files = {
        "edict_file": ("updated_edict.pdf", b"new content", "application/pdf"),
        "document_file": ("updated_document.pdf", b"new content", "application/pdf")
    }

    update_response = client.put(
        f"/proposals/{proposal_id}",
        data=updated_data,
        files=files,
    )
    assert update_response.status_code == 200
    updated_proposal = update_response.json()
    assert updated_proposal["name"] == "Updated Proposal"
    assert updated_proposal["publisher"] == "Updated Publisher"
    assert len(updated_proposal["scientific_areas"]) == 1
    assert updated_proposal["scientific_areas"][0]["name"] == "Biology"

def test_update_proposal_invalid_id(client):
    updated_data = {
        "name": "Updated Proposal",
    }
    response = client.put("/proposals/9999", data=updated_data)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Proposal not found"

def test_submit_proposal(client):
    # Create a proposal
    form_data = {
        "name": "Proposal to Submit",
        "publisher": "Test Publisher",
        "type": "Research Scholarship",
        "scientific_areas": ["Computer Science"],
        "document_template": "true",
        "document_required": "true"
    }
    files = {
        "edict_file": ("edict.pdf", b"edict content", "application/pdf"),
        "document_file": ("document.pdf", b"document content", "application/pdf")
    }
    create_response = client.post("/proposals", data=form_data, files=files)
    assert create_response.status_code == 200
    proposal = create_response.json()
    proposal_id = proposal["id"]

    update_response = client.put(
        f"/proposals/{proposal_id}",
        data={"deadline": "2023-10-31"},
    )
    assert update_response.status_code == 200

    # Submit the proposal
    response = client.post(f"/proposals/{proposal_id}/submit")
    data = response.json()
    assert response.status_code == 200
    assert data["message"] == "Proposal submitted successfully. It will be reviewed shortly."

def test_submit_proposal_missing_fields(client):
    # Create a proposal with missing required fields
    form_data = {
        "name": "Incomplete Proposal",
        "publisher": "Publisher 1",
        "type": "Research Scholarship",
        "scientific_areas": ["Computer Science"]
    }
    files = {
        "edict_file": ("edict.pdf", b"edict content", "application/pdf")
        # Missing 'file'
    }
    create_response = client.post("/proposals", data=form_data, files=files)
    assert create_response.status_code == 200
    proposal = create_response.json()
    proposal_id = proposal["id"]

    # Attempt to submit the incomplete proposal
    response = client.post(f"/proposals/{proposal_id}/submit")
    assert response.status_code == 400
    data = response.json()
    assert "Cannot submit proposal" in data["detail"]

def test_submit_proposal_invalid_status(client):
    # Create a proposal and set its status to 'closed'
    form_data = {
        "name": "Proposal with Closed Status",
        "publisher": "Test Publisher",
        "type": "Research Scholarship",
        "scientific_areas": ["Physics"],
        "deadline": "2023-10-31"
    }
    files = {
        "edict_file": ("edict.pdf", b"edict content", "application/pdf"),
        "document_file": ("document.pdf", b"document content", "application/pdf")
    }
    create_response = client.post("/proposals", data=form_data, files=files)
    assert create_response.status_code == 200
    proposal = create_response.json()
    proposal_id = proposal["id"]

    # Manually update the status to 'closed'
    update_response = client.put(
        f"/proposals/{proposal_id}",
        data={"status": "Closed"},
    )
    assert update_response.status_code == 200

    # Attempt to submit the proposal
    response = client.post(f"/proposals/{proposal_id}/submit")
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Cannot submit a proposal that is not in draft or under review status."

def test_upload_edict_file(client):
    # Create a test edict file
    edict_content = b"This is a test edict file."
    edict_filename = "test_edict.txt"

    data = {
        'name': 'Test Scholarship',
        'publisher': 'Test Publisher',
        'type': 'Research Scholarship',
    }

    files = {
        'edict_file': (edict_filename, edict_content, 'text/plain'),
    }

    response = client.post("/proposals", data=data, files=files)
    assert response.status_code == 200, response.text

    edict_files_dir = os.getenv("EDICT_FILES_DIR", "edict_files/")
    edict_file_path = os.path.join(os.getcwd(), edict_files_dir, edict_filename)

    for root, dirs, files in os.walk(os.getcwd()):
        # Exclude hidden directories and files if necessary
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        
        # Calculate the level of indentation
        level = root.replace(os.getcwd(), '').count(os.sep)
        indent = ' ' * 4 * level
        # Print the directory name
        print(f"{indent}{os.path.basename(root)}/")
        # Print the file names
        for f in files:
            subindent = ' ' * 4 * (level + 1)
            print(f"{subindent}{f}")

    assert os.path.exists(edict_file_path)
    with open(edict_file_path, 'rb') as f:
        content = f.read()
    assert content == edict_content

def test_upload_document_files(client):
    # Create test document files
    document_content1 = b"This is the first test document file."
    document_filename1 = "test_document1.txt"

    document_content2 = b"This is the second test document file."
    document_filename2 = "test_document2.txt"

    data = {
        'name': 'Test Scholarship with Documents',
        'publisher': 'Test Publisher',
        'type': 'Research Scholarship',
        'document_template': 'true',
        'document_template': 'false',
        'document_required': 'true',
        'document_required': 'false',
    }

    files = {
        'edict_file': ('edict.txt', b"Edict content", 'text/plain'),
        'document_file': (document_filename1, document_content1, 'text/plain'),
        'document_file': (document_filename2, document_content2, 'text/plain'),
    }

    response = client.post("/proposals", data=data, files=files)
    assert response.status_code == 200, response.text

    for filename, content in [
        (document_filename1, document_content1),
        (document_filename2, document_content2),
    ]:
        document_file_dir = os.getenv("APPLICATION_FILES_DIR", "application_files/")
        document_file_path = os.path.join(os.getcwd(), document_file_dir, filename)
        print(document_file_path)
        print(os.getcwd())
        assert os.path.exists(document_file_path)
        with open(document_file_path, 'rb') as f:
            file_content = f.read()
        assert file_content == content

def test_upload_invalid_file(client):
    data = {
        'name': 'Invalid File Test',
        'publisher': 'Test Publisher',
        'type': 'Research Scholarship',
    }

    files = {
        'edict_file': ('../file.txt', b"This is a test edict file.", 'text/plain'),
    }

    response = client.post("/proposals", data=data, files=files)
    data = response.json()
    assert response.status_code == 400
    assert "Invalid filename." in data["detail"]
