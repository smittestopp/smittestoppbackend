build_sql_alembic:
	docker build --tag sql_alembic_test .

run:
	docker run \
	-e 'ACCEPT_EULA=Y' \
	-e 'SA_PASSWORD=Pa55w0rd' \
 	-e "SQL_SERVER=0.0.0.0" \
 	-p 1433:1433 \
 	--name corona_test_sql_container \
 	-d sql_alembic_test \

create_test_db:
	docker exec \
	-i corona_test_sql /opt/mssql-tools/bin/sqlcmd \
	-S localhost \
	-U SA \
	-P 'Pa55w0rd' \
	-Q 'CREATE DATABASE testdb' \

build_run: build_sql_alembic run

stop_container:
	docker stop corona_test_sql_container

remove_container:
	docker rm corona_test_sql_container

stop_remove_container: stop_container remove_container

rebuild_run: stop_remove_container build_run

migrate_head:
	docker exec corona_test_sql_container alembic upgrade head

enter_container:
	docker exec -it corona_test_sql_container /bin/sh

