from alembic import context

from photoindex.db import get_engine
from photoindex.models import Base

target_metadata = Base.metadata

with get_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
