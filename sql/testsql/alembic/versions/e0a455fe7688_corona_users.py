"""corona users

Revision ID: e0a455fe7688
Revises: d5eb753b909e
Create Date: 2020-06-23 11:43:01.250271

"""
from alembic import op
import re


# revision identifiers, used by Alembic.
revision = 'e0a455fe7688'
down_revision = 'd5eb753b909e'
branch_labels = None
depends_on = None


def create_migration_batches(path):
    batches = []
    batch_separator = re.compile("^go\s", re.IGNORECASE)
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
    qry_batches = create_migration_batches("migrations/corona_users_prod.sql")
    for qry in qry_batches:
        conn.execute(qry)


def downgrade():
    pass
