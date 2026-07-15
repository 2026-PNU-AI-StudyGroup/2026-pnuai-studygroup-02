# [MAIN-DRAFT] 현지 담당, 이후 계속 확장됨
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "ok"}
