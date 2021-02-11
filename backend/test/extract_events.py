#!/usr/bin/env python3
"""
show events stored in Google Bigtable from importer REST API

needs gcloud sdk

    gcloud auth login # once, to get gcloud credentials
    pip install google-cloud-bigtable

"""
import datetime
import json
import os
import time
from pprint import pprint

from google.cloud import bigtable
from google.cloud.bigtable.row_filters import TimestampRange, TimestampRangeFilter

project_id = os.environ.get("PROJECT_ID", "simula-cov19")
instance_id = os.environ.get("BT_INSTANCE_ID", "test-bigt")
table_id = 'test'

now = datetime.datetime.now(datetime.timezone.utc)
# get events reported via api from the last day (not event timestamp)
start_time = now - datetime.timedelta(days=5)
end_time = now
ts_range = TimestampRange(start=start_time, end=end_time)
row_filter = TimestampRangeFilter(ts_range)

# connect to Bigtable
client = bigtable.Client(project=project_id)
instance = client.instance(instance_id)
table = instance.table(table_id)

# make our query

for row in table.read_rows(filter_=row_filter):
    print(row.row_key)
    for cell in row.to_dict().get(b'events:event'):
        data = json.loads(cell.value.decode('utf8'))
        pprint(data, indent=2)
