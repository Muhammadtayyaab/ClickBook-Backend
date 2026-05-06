"""add payfast support to payments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    payment_provider = sa.Enum('stripe', 'payfast', name='payment_provider')
    payment_provider.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'provider',
                sa.Enum('stripe', 'payfast', name='payment_provider'),
                nullable=False,
                server_default='stripe',
            )
        )
        batch_op.add_column(sa.Column('transaction_id', sa.String(length=120), nullable=True))
        batch_op.alter_column('stripe_session_id', existing_type=sa.String(length=300), nullable=True)
        batch_op.create_unique_constraint('uq_payments_transaction_id', ['transaction_id'])


def downgrade():
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_constraint('uq_payments_transaction_id', type_='unique')
        batch_op.alter_column('stripe_session_id', existing_type=sa.String(length=300), nullable=False)
        batch_op.drop_column('transaction_id')
        batch_op.drop_column('provider')

    sa.Enum(name='payment_provider').drop(op.get_bind(), checkfirst=True)
