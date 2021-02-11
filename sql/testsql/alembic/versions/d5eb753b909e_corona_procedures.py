"""corona procedures

Revision ID: d5eb753b909e
Revises: e45b202ec02b
Create Date: 2020-06-22 13:12:15.082725

"""
from alembic import op
import re


# revision identifiers, used by Alembic.
revision = 'd5eb753b909e'
down_revision = 'e45b202ec02b'
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
    qry_batches = create_migration_batches("migrations/corona_procedures_prod.sql")
    for qry in qry_batches:
        conn.execute(qry)


def downgrade():
    pass
