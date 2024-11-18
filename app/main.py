from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .models.models import Scholarship, ScholarshipStatus
from datetime import datetime
from sqlmodel import Session, SQLModel, select
from contextlib import asynccontextmanager
from .routers import scholarships, proposals

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": True}, lifespan=lifespan)

app.include_router(scholarships.router)
app.include_router(proposals.router)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Scheduler for deadline detection mecanism
scheduler = BackgroundScheduler()

def update_scholarship_status():
    with Session(engine) as session:
        today = datetime.today().date()
        scholarships = session.exec(select(Scholarship).where(
            Scholarship.status == ScholarshipStatus.open, 
            Scholarship.deadline < today
        )).all()
        
        for scholarship in scholarships:
            scholarship.status = ScholarshipStatus.jury_evaluation
            session.add(scholarship)
        
        session.commit()

scheduler.add_job(update_scholarship_status, "interval", seconds=60) # updates every minute
scheduler.start()