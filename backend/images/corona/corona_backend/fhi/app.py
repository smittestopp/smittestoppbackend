#!/usr/bin/env python3
"""
FHI- and HelseNorge- facing entrypoint for accessing the data
"""

import asyncio
import os

import tornado.options
from tornado.log import app_log

from corona_backend import graph, sql, utils
from corona_backend.handlers import start_app

from .handlers.endpoints import endpoints


def main(port):
    tornado.options.parse_command_line()
    # first-thing, check the database connection
    test_number = "+0010101011"
    for i in range(2):
        # perform an initial connect and query to validate our connection and permissions
        app_log.info("Checking access log routines")
        asyncio.run(
            sql.log_access(
                phone_numbers=[test_number],
                timestamp=utils.now_at_utc(),
                person_name="Smittestopp Backend",
                person_id="",
                person_organization="Simula Research Laboratory",
                organization="Simula Research Laboratory",
                legal_means="Vedlikehold",
            )
        )
        asyncio.run(sql.get_access_log(test_number, per_page=2))
        # app_log.info("Checking gps log routine")
        # asyncio.run(sql.get_gps_events([device_id]), per_page=1)

    # after calling run, there's no loop!
    asyncio.set_event_loop(asyncio.new_event_loop())

    app_log.info("Database connection okay!")

    graph.keep_jwt_keys_updated()
    start_app(
        endpoints(), port,
    )


if __name__ == "__main__":
    main(int(os.environ.get("PORT", "8080")))
