from fastapi import FastAPI

# Minimal FastAPI entrypoint for Vercel detection
app = FastAPI(title="Cerulean API", version="0.1.0")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
