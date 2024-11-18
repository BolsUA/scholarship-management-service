import os
from sqlmodel import create_engine, Session

DATABASE_URL = str(os.getenv("DATABASE_URL"))

engine = create_engine(DATABASE_URL)

# Dependency to get DB session
def get_session():
    with Session(engine) as session:
        yield session