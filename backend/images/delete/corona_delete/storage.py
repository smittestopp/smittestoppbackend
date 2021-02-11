"""storage-related functionality

- find raw data for a device id
- delete raw data for a device id
- delete sql data for a device id
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from azure.storage.filedatalake import DataLakeServiceClient


storage_account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
n_threads = int(os.environ.get("STORAGE_THREADS") or "4")

iothub_data_dir = os.environ.get("IOTHUB_DATA_DIR") or "iot-smittestopp-dev-json"
storage_account = os.environ.get("AZURE_STORAGE_ENDPOINT")
fs_name = os.environ.get("AZURE_STORAGE_FILESYSTEM")

pool = ThreadPoolExecutor(n_threads)


def in_thread(f, *args, **kwargs):
    """call the given function in a thread"""
    return asyncio.wrap_future(pool.submit(f, *args, **kwargs))


def format_size(nbytes):
    """format a number of bytes nicely"""
    if nbytes < 2000:
        return f"{nbytes} B"
    elif nbytes < 2e6:
        return f"{nbytes//1024} kB"
    elif nbytes < 2e9:
        return f"{nbytes//(1024*1024)} MB"
    else:
        return f"{nbytes//(1024*1024)} GB"


class FSClientCache(dict):
    def __init__(self):
        self._service_clients = {}

    def __missing__(self, key):
        endpoint, fs_name = key
        if endpoint not in self._service_clients:
            self._service_clients[endpoint] = DataLakeServiceClient(
                endpoint, credential=storage_account_key
            )
        fs_client = self._service_clients[endpoint].get_file_system_client(fs_name)
        self[key] = fs_client
        return fs_client


fs_clients = FSClientCache()


def get_file_client(url):
    """return file client for the given url"""
    urlinfo = urlparse(url)
    storage_endpoint = urlinfo.netloc.replace(".blob.core.", ".dfs.core.")
    _, fs_name, path = urlinfo.path.split("/", 2)
    fs_client = fs_clients[(storage_endpoint, fs_name)]
    return fs_client.get_file_client(path)


def file_system_client_from_file_client(file_client):
    """Turn a file_client back into a file_system_client"""
    return fs_clients[
        (f"https://{file_client.primary_hostname}", file_client.file_system_name)
    ]
