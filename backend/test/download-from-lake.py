import json
import os
import pprint
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from azure.storage.filedatalake import DataLakeServiceClient
import tqdm

# avro: pip install
import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter

storage_account = os.environ.get("AZURE_STORAGE_ACCOUNT", "stsmittestoppdev")
storage_endpoint = f"https://{storage_account}.dfs.core.windows.net/"
storage_account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
lake_name = os.environ.get("AZURE_STORAGE_LAKE_NAME", "dfs-smittestopp-dev-raw")
iot_name = "iot-smittestopp-dev"

def download_one(f_client):
    """download a file"""
    path = f_client.path_name
    if os.path.exists(path):
        return 0
    if f_client.get_file_properties().metadata.get("hdi_isfolder", "") == 'true':
        if not os.path.isdir(path):
            # print(f"Creating directory {path}")
            try:
                os.makedirs(path)
            except FileExistsError:
                pass
        return 0
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        try:
            os.makedirs(parent)
        except FileExistsError:
            pass
    try:
        with open(path, "wb") as f:
            dl = f_client.download_file()
            return dl.readinto(f)
    except Exception:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        raise
    # print(f"Downloaded {path}")

def download_everything():
    """download all the files in the lake right now"""
    service_client = DataLakeServiceClient(storage_endpoint, credential=storage_account_key)
    fs_client = service_client.get_file_system_client(lake_name)

    pool = ThreadPoolExecutor(8)
    futures = []
    for f in fs_client.get_paths(f"{iot_name}"):
        f_client = fs_client.get_file_client(f.name)
        futures.append(pool.submit(partial(download_one, f_client)))
        for fut in futures:
            if fut.done() and fut.exception():
                print(fut.exception())
                # check for exceptions
                # fut.result()

    for f in tqdm.tqdm(futures):
        try:
            f.result()
        except Exception as e:
            print(e)

def process_event_data(path):
    """example stepping through all the data"""
    for parent, dirs, files in os.walk(path):
        for fname in sorted(files):
            with open(os.path.join(parent, fname), 'rb') as f:
                reader = DataFileReader(f, DatumReader())
                for reading in reader:
                    print("")
                    print(
                        f"id={reading['SystemProperties']['connectionDeviceId']}",
                        f"received={reading['EnqueuedTimeUtc']}"
                        )

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
    if len(sys.argv) < 2 or sys.argv[1] == 'download':
        download_everything()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'print':
        process_event_data(iot_name)
    else:
        print(f"Usage: {sys.argv[0]} [download|print]")
        print("`download` downloads the data from the lake")
        print("`print` iterates through the data and prints records")
