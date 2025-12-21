# app/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from app.model import predict_score

app = FastAPI()

class PredictionInput(BaseModel):
    home: str
    away: str
    home_court: bool

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/predict")
def predict(data: PredictionInput):
    return predict_score(
        data.home,
        data.away,
        data.home_court
    )

from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
