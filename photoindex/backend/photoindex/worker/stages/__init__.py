from sqlalchemy import text
from sqlalchemy.orm import Session


def claim(session: Session, status_col: str, where: str, limit: int) -> list[tuple[int, str]]:
    """Atomically move up to `limit` pending rows to 'running' and return (id, path_lower).
    SKIP LOCKED lets several workers run the same stage without double-processing."""
    rows = session.execute(
        text(f"""
            UPDATE photos SET {status_col} = 'running', updated_at = now()
            WHERE id IN (
                SELECT id FROM photos
                WHERE {status_col} = 'pending' AND NOT deleted AND ({where})
                ORDER BY id LIMIT :limit FOR UPDATE SKIP LOCKED
            )
            RETURNING id, path_lower
        """),
        {"limit": limit},
    ).all()
    session.commit()
    return [(r.id, r.path_lower) for r in rows]


def reset_stale(session: Session, status_col: str, minutes: int = 30) -> None:
    """Return rows abandoned by a crashed worker to the queue."""
    session.execute(
        text(f"UPDATE photos SET {status_col} = 'pending' "
             f"WHERE {status_col} = 'running' AND updated_at < now() - make_interval(mins => :m)"),
        {"m": minutes},
    )
    session.commit()
