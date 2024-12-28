# Use an official Python runtime as the base image
FROM python:3.9-slim

RUN addgroup --system appgroup && adduser --system --group appuser

# Set the working directory
WORKDIR /scholarship_management

RUN chown -R appuser:appgroup /scholarship_management

# Set build-time arguments
ARG REGION
ARG USER_POOL_ID
ARG CLIENT_ID
ARG FRONTEND_URL

# Log build-time arguments
RUN echo "Build-time arguments:" && \
    echo "REGION=${REGION}" && \
    echo "USER_POOL_ID=${USER_POOL_ID}" && \
    echo "CLIENT_ID=${CLIENT_ID}" && \
    echo "FRONTEND_URL=${FRONTEND_URL}"

# Set environment variables
ENV REGION=${REGION}
ENV USER_POOL_ID=${USER_POOL_ID}
ENV CLIENT_ID=${CLIENT_ID}
ENV FRONTEND_URL=${FRONTEND_URL}

# Copy the requirements file
COPY ./app ./app
COPY ./requirements.txt ./
COPY ./wait_for_db.py ./

# Expose the port FastAPI runs on
EXPOSE 8000

# Install dependencies
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -r requirements.txt

USER appuser

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8001"]
# Run this command to set env variables in the docker container
# docker build --build-arg REGION=${"region"}  --build-arg USER_POOL_ID=${"user_pool_id"} --build-arg CLIENT_ID=${"user_pool_client_id"} --build-arg FRONTEND_URL=https://${"frontend_url"} -t ${container} /path/to/Dockerfile
