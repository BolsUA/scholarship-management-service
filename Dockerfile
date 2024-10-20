# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /scholarship_management

# Copy the requirements file
COPY ./ ./

# Expose the port FastAPI runs on
EXPOSE 8000

# Install dependencies
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -r requirements.txt

CMD ["sh", "-c", "python3 wait_for_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
