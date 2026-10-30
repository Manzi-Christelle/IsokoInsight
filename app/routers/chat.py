from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..chatbot import answer
from ..db import get_db

router = APIRouter(prefix="/api/chat", tags=["chatbot"])


class ChatIn(BaseModel):
    message: str = Field(default="", max_length=500)
    context: dict | None = None  # the last forecast IsokoBot gave, so follow-up questions can refer to it


@router.post("")
def chat(body: ChatIn, db: Session = Depends(get_db)):
    """Answer a question from the app's verified data and recorded official figures only."""
    return answer(db, body.message, context=body.context)