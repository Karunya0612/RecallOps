from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.banks import router as banks_router
from app.api.incidents import router as incidents_router

app = FastAPI(
    title="RecallOps",
    description="Memory-first AI incident investigation and recovery assistant.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(banks_router)
app.include_router(incidents_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "RecallOps",
    }
