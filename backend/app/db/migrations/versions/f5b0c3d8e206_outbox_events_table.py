"""Add outbox_events table for phase 7

Revision ID: f5b0c3d8e206
Revises: e4a9b2c7f105
Create Date: 2026-09-10 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5b0c3d8e206'
down_revision: Union[str, None] = 'e4a9b2c7f105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('aggregate_type', sa.String(length=100), nullable=False),
        sa.Column('aggregate_id', sa.UUID(), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outbox_events_aggregate_type'), 'outbox_events', ['aggregate_type'], unique=False)
    op.create_index(op.f('ix_outbox_events_aggregate_id'), 'outbox_events', ['aggregate_id'], unique=False)
    op.create_index(op.f('ix_outbox_events_status'), 'outbox_events', ['status'], unique=False)
    op.create_index(op.f('ix_outbox_events_available_at'), 'outbox_events', ['available_at'], unique=False)
    op.create_index('ix_outbox_events_status_available_at', 'outbox_events', ['status', 'available_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_outbox_events_status_available_at', table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_available_at'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_status'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_aggregate_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_aggregate_type'), table_name='outbox_events')
    op.drop_table('outbox_events')
