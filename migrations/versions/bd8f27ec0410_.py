"""empty message

Revision ID: bd8f27ec0410
Revises: 88176541e364
Create Date: 2020-07-13 23:38:01.893169

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bd8f27ec0410'
down_revision = '88176541e364'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('carpool')
    op.add_column('trips', sa.Column('car_id', sa.Integer(), nullable=False))
    op.add_column('trips', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_foreign_key(None, 'trips', 'cars', ['car_id'], ['id'])
    op.create_foreign_key(None, 'trips', 'users', ['user_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'trips', type_='foreignkey')
    op.drop_constraint(None, 'trips', type_='foreignkey')
    op.drop_column('trips', 'user_id')
    op.drop_column('trips', 'car_id')
    op.create_table('carpool',
    sa.Column('cars_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('users_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['cars_id'], ['cars.id'], name='carpool_cars_id_fkey'),
    sa.ForeignKeyConstraint(['users_id'], ['users.id'], name='carpool_users_id_fkey'),
    sa.PrimaryKeyConstraint('cars_id', 'users_id', name='carpool_pkey1')
    )
    # ### end Alembic commands ###
