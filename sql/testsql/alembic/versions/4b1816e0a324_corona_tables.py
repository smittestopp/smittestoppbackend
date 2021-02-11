"""corona tables

Revision ID: 4b1816e0a324
Revises: 
Create Date: 2020-06-22 13:08:15.887120

"""
from alembic import op
import re


# revision identifiers, used by Alembic.
revision = '4b1816e0a324'
down_revision = None
branch_labels = None
depends_on = None


def create_migration_batches(path):
    batches = []
    batch_separator = re.compile("^go\s|^GO\s")
    with open(path, mode='r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        batch = ""
        for line in lines:
            if batch_separator.match(line):
                batches.append(batch)
                batch = ""
            else:
                batch += line

        if batch != "":
            batches.append(batch)

    return batches


def upgrade():
    conn = op.get_bind()
    qry_batches = create_migration_batches("migrations/corona_datamodel_prod.sql")
    for qry in qry_batches:
        conn.execute(qry)


def downgrade():
    pass
