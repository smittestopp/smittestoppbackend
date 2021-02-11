
# Alembic (test) database migration setup

This is the test database image. Create a docker container (corona_test_sql_container)
with mssql and Alembic by executing `make build_run`. This container must be running when executing
the tests in the _corona_ _image_. 

This image should contain database migration scripts that makes it possible to mirror the production
database in tests.  

-----------

[alembic](https://alembic.sqlalchemy.org) is a Python database-migration tool.
Check its docs for available operations.

You can test with `pip install alembic`,
but there is also a Dockerfile with all the requirements,
including the necessary mssql odbc driver.


Run alembic commands in the `sql` directory (containing `alembic.ini`).
Generally you issue a subcommand like `alembic revision` to generate a new upgrade/downgrade script or `alembic upgrade` to upgrade the database to a new version.

Revisions are scripts in the `alembic/versions` directory
containing an `upgrade()` and `downgrade()` function.
You can create new revisions with:

    alembic revision -m "brief summary of change"

and then edit the newly created file,
defining the `upgrade()` and `downgrade()` functions.

If you perform an upgrade manually, you can generate **a starting point** for the upgrade script by letting alembic compare the database with the schema:

    alembic revision --autogenerate -m "message"


See `alembic --help` for commands:

```
usage: alembic [-h] [-c CONFIG] [-n NAME] [-x X] [--raiseerr]
               {branches,current,downgrade,edit,heads,history,init,list_templates,merge,revision,show,stamp,upgrade}
               ...

positional arguments:
  {branches,current,downgrade,edit,heads,history,init,list_templates,merge,revision,show,stamp,upgrade}
    branches            Show current branch points.
    current             Display the current revision for a database.
    downgrade           Revert to a previous version.
    edit                Edit revision script(s) using $EDITOR.
    heads               Show current available heads in the script directory.
    history             List changeset scripts in chronological order.
    init                Initialize a new scripts directory.
    list_templates      List available templates.
    merge               Merge two revisions together. Creates a new migration
                        file.
    revision            Create a new revision file.
    show                Show the revision(s) denoted by the given symbol.
    stamp               'stamp' the revision table with the given revision;
                        don't run any migrations.
    upgrade             Upgrade to a later version.