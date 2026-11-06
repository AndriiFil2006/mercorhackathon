from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.export_service import export_evaluations
router = APIRouter(prefix="/exports", tags=["exports"])
@router.get("/evaluations", response_class=StreamingResponse)
def download_evaluations(db: Session = Depends(get_db)):
    return StreamingResponse(export_evaluations(db), media_type="application/x-ndjson",
                             headers={"Content-Disposition": 'attachment; filename="evaluations.jsonl"'})

