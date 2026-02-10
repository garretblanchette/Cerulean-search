from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"hello": "world"}
```

And make sure `api/requirements.txt` contains just:
```
fastapi==0.115.6
