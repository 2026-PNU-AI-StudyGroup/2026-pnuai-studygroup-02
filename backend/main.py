# [MAIN-DRAFT] 현지 담당, 이후 계속 확장됨
from fastapi import FastAPI
from backend.routers.recipes import router as recipes_router

app = FastAPI()
app.include_router(recipes_router)


@app.get("/")
def read_root():
    return {"message": "ok"}
