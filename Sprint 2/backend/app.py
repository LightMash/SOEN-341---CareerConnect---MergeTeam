"""
CareerConnect - FastAPI entry point.
Run with: uvicorn app:app --reload --port 5000
Interactive docs available at http://localhost:5000/docs
"""

#Importing a library used to load the contents of the .env file
from dotenv import load_dotenv
load_dotenv()  # reads .env before anything else imports database.py

#Standart imports for FAST API 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers.auth import router as auth_router
from routers.resume import router as resume_router

# Create all the tables from the database on startup
Base.metadata.create_all(bind=engine)

#Creates the FastAPI app
app = FastAPI(title="CareerConnect API")

# Allow the React dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#How every different routes gets integrated within
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(resume_router, prefix="/api", tags=["resume"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
