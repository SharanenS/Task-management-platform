"""Database URLs are private runtime input, never migration source."""

import os

from alembic import context
from project_work.models import Base
from sqlalchemy import create_engine, pool

config = context.config
if context.is_offline_mode():
    context.configure(
        url=os.environ["PROJECT_WORK_DATABASE_URL"],
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
