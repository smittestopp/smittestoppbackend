"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import re
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


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
    ${upgrades if upgrades else """conn = op.get_bind()
    qry_batches = create_migration_batches("")
    for qry in qry_batches:
        conn.execute(qry)"""}


def downgrade():
    ${downgrades if downgrades else "pass"}
