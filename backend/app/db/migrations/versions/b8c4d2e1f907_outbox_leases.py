"""Add lease and claim columns to outbox_events for Phase 8

Revision ID: b8c4d2e1f907
Revises: f5b0c3d8e206
Create Date: 2026-09-10 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8c4d2e1f907'
down_revision: Union[str, None] = 'f5b0c3d8e206'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('outbox_events', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('outbox_events', sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('outbox_events', sa.Column('claim_owner', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_outbox_events_lease_until'), 'outbox_events', ['lease_until'], unique=False)
    op.create_index('ix_outbox_events_status_lease_until', 'outbox_events', ['status', 'lease_until'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_outbox_events_status_lease_until', table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_lease_until'), table_name='outbox_events')
    op.drop_column('outbox_events', 'claim_owner')
    op.drop_column('outbox_events', 'lease_until')
    op.drop_column('outbox_events', 'claimed_at')
