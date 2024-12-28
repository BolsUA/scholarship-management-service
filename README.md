# scholarship-management-service
This service responsible for managing the submission, review, and publication of scholarship proposals as well as the browsing and application of scholarships by students

## Run the FastAPI Application

### Run the Application Using Uvicorn:

In your terminal, run the following command to start the application:

```bash
uvicorn main:app --reload
```

### Run the App in Production:

For production, you might use gunicorn with Uvicorn workers:

```bash
gunicorn -k uvicorn.workers.UvicornWorker main:app
```

## Access the Application:

Open your browser and go to [http://127.0.0.1:8000](http://127.0.0.1:8000). You should see the JSON response:

```json
{"message": "Welcome to FastAPI!"}
```

## API Documentation:

FastAPI automatically provides interactive API documentation using Swagger UI. You can access it at:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger UI)
- [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) (ReDoc UI)

For this app to work there are several env variables that need to be set:
- DATABASE_URL = str
- SECRET_KEY = str
- REGION = str
- USER_POOL_ID = str
- CLIENT_ID = str
- FRONTEND_URL = str
