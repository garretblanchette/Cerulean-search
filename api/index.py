from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/debug")
def debug():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    return {
        "dir": current_dir,
        "parent": parent_dir,
        "parent_contents": os.listdir(parent_dir) if os.path.isdir(parent_dir) else "NOT FOUND",
    }
