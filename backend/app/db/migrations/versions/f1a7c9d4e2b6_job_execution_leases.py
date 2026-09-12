"""Add execution lease and claim owner columns to jobs table for Phase 10

Revision ID: f1a7c9d4e2b6
Revises: b8c4d2e1f907
Create Date: 2026-09-12 12:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a7c9d4e2b6'
down_revision: Union[str, None] = 'b8c4d2e1f907'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('execution_lease_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('execution_claim_owner', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_jobs_execution_lease_until'), 'jobs', ['execution_lease_until'], unique=False)
    op.create_index(op.f('ix_jobs_execution_claim_owner'), 'jobs', ['execution_claim_owner'], unique=False)
    op.create_index('ix_jobs_status_execution_lease_until', 'jobs', ['status', 'execution_lease_until'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_jobs_status_execution_lease_until', table_name='jobs')
    op.drop_index(op.f('ix_jobs_execution_claim_owner'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_execution_lease_until'), table_name='jobs')
    op.drop_column('jobs', 'execution_claim_owner')
    op.drop_column('jobs', 'execution_lease_until')
    op.drop_column('jobs', 'processing_started_at')
