# app/main.py

from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"status": "Basketball model live"}

from app.model import predict_score

@app.get("/predict")
def predict(home: str, away: str, home_court: bool):
    return predict_score(home, away, home_court)

from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
