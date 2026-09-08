"""Add phase 4 project table updates

Revision ID: d2e5a1b890f1
Revises: c1100413160d
Create Date: 2026-09-08 16:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e5a1b890f1'
down_revision: Union[str, None] = 'c1100413160d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop legacy created_by foreign key and column from initial schema
    op.drop_constraint('projects_created_by_fkey', 'projects', type_='foreignkey')
    op.drop_column('projects', 'created_by')
    op.add_column('projects', sa.Column('owner_id', sa.String(length=255), nullable=False))
    op.create_index(op.f('ix_projects_owner_id'), 'projects', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_projects_owner_id'), table_name='projects')
    op.drop_column('projects', 'owner_id')
    op.add_column('projects', sa.Column('created_by', sa.UUID(), nullable=False))
    op.create_foreign_key('projects_created_by_fkey', 'projects', 'users', ['created_by'], ['id'])
