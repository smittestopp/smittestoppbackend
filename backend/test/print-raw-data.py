"""
parse data files from the lake
"""

import json
import os
import pprint
import sys

# avro: pip install avro-python3
import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter


def yield_events(path, limit=100):
    """yield just the actual event bodies"""
    yielded = 0
    for parent, dirs, files in os.walk(path):
        for fname in sorted(files):
            with open(os.path.join(parent, fname), 'rb') as f:
                # this is how you open an avro file
                reader = DataFileReader(f, DatumReader())
                # an avro file provides an iterable of events
                for reading in reader:
                    event_uuid = reading['SystemProperties']['connectionDeviceId']
                    try:
                        body = json.loads(reading['Body'].decode('utf8'))
                    except ValueError:
                        print(f"not a json message: {reading['Body']}")
                        continue
                    for event in body.get("events", []):
                        yield (event_uuid, event)
                        yielded += 1
                        if limit and yielded >= limit:
                            print("...")
                            return

def print_all_events(path, limit=10):
    """example stepping through all the data files and parsing them

    1. iterate through all data files
    2. open files with avro
    3. parse event JSON
    4. pretty-print events
    """
    printed = 0
    for parent, dirs, files in os.walk(path):
        for fname in sorted(files):
            printed += 1
            if printed >= limit:
                print("...")
                return
            with open(os.path.join(parent, fname), 'rb') as f:
                # this is how you open an avro file
                reader = DataFileReader(f, DatumReader())
                # an avro file provides an iterable of events
                for reading in reader:
                    # the uuid we want to use is reading.SystemProperties.connectionDeviceId
                    print(f"uuid={reading['SystemProperties']['connectionDeviceId']}")

                    # the actual payload from the app is the json body (as a bytestring)
                    try:
                        # parse it out so it looks nicer when we print:
                        reading['Body'] = json.loads(reading['Body'].decode('utf8'))
                    except ValueError:
                        # leave not json as bytes. This shouldn't happen!
                        pass
                    pprint.pprint(reading)
                    # pprint.pprint(body, indent=2)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("Please provide a path containing downloaded data files (e.g. with download-from-lake.py)")

    path = sys.argv[1]

    print("# RAW PUBLICATION DATA")
    print_all_events(path)

    print("\n# INDIVIDUAL EVENTS")
    for event_uuid, event in yield_events(path):
        print(f"uuid={event_uuid}, event={event}")
