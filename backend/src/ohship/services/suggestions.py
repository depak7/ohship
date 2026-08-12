from uuid import UUID

from sqlmodel import Session

from ohship.models import Suggestion, User, utcnow


def add_suggestion(session: Session, plan_id: UUID, author: User, content: str) -> Suggestion:
    suggestion = Suggestion(
        plan_id=plan_id,
        author_id=author.id,
        content=content,
        created_at=utcnow(),
    )
    session.add(suggestion)
    session.commit()
    session.refresh(suggestion)
    return suggestion
