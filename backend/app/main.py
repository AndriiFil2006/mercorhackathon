from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.routes import health, questions, generations, evaluations, exports, chat
app = FastAPI(title="Legal Expert Evaluation API", version="1.0.0",
              description="AI answers require human expert review. Expert approval is judgment, not proof.")
app.add_middleware(CORSMiddleware,
                   allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()],
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(health.router)
for router in (questions.router, generations.router, evaluations.router, exports.router):
    app.include_router(router, prefix="/api/v1")


app.include_router(chat.router)
