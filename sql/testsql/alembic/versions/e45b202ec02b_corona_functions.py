"""corona functions

Revision ID: e45b202ec02b
Revises: 4b1816e0a324
Create Date: 2020-06-22 13:09:57.501347

"""
from alembic import op
import re


# revision identifiers, used by Alembic.
revision = 'e45b202ec02b'
down_revision = '4b1816e0a324'
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
    qry_batches = create_migration_batches("migrations/corona_functions_new.sql")
    for qry in qry_batches:
        conn.execute(qry)


def downgrade():
    pass
