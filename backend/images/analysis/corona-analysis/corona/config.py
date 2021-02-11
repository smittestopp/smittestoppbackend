import os
import configparser
import logging

from corona import logger

__DEFAULT_CONFG = {
    "settings": {
        "debug": False
    },
    "cache": {
        "location": "./__cache__",
        "enabled": True
    },
    "database": {
        "driver": "{ODBC Driver 17 for SQL Server}"
    },
    "nominatim": {},
    "overpass": {
        "batched": True,
        "batched_mt_threshold": 5
    },
    "features": {
        "device_info": False
    }
}



class Config(dict):

    __UNLOGGABLE_CONFG = {
        'database': ['password']
    }

    def __infer_type(self, value):
        value_type = type(value)
        if value_type == bool or value_type == int:
            return value
        try:
            return int(value)
        except ValueError:
            lc = value.lower()
            if lc == "true" or lc == "yes":
                return True
            if lc == "false" or lc == "no":
                return False
            return value

    def __init__(self, init=None):
        super().__init__()
        if init is None:
            init = {}
        for key, val in init.items():
            if type(val) is dict:
                self.__setattr__(key, Config(val))
            else:
                self.__setattr__(key, self.__infer_type(val))

    def __getstate__(self):
        return self.__dict__.items()

    def __setstate__(self, items):
        for key, val in items:
            self.__dict__[key] = val

    def __setitem__(self, key, value):
        return super(Config, self).__setitem__(key, value)

    def __getitem__(self, name):
        return super(Config, self).__getitem__(name)

    def __delitem__(self, name):
        return super(Config, self).__delitem__(name)

    def add_section(self, name, value):
        name = name.lower()
        current = self.get(name)
        config = Config(value)
        if type(current) is Config:
            current.update(config)
        else:
            self.__setattr__(name, config)

    __getattr__ = __getitem__
    __setattr__ = __setitem__

    def loggable_params(self):
        redacted_dict = dict(self.items())
        for section, unloggables in self.__UNLOGGABLE_CONFG.items():
            if section in redacted_dict and len(redacted_dict[section]):
                redacted_dict[section] = dict(redacted_dict[section].items())
                for unloggable in unloggables:
                    if unloggable in redacted_dict[section]:
                        redacted_dict[section][unloggable] = '***'
        return redacted_dict


def find_config_home():
    if "CORONA_CONFIG_HOME" in os.environ:
        return os.environ["CORONA_CONFIG_HOME"]
    elif "APPDATA" in os.environ:
        return os.environ["APPDATA"]
    elif "XDG_CONFIG_HOME" in os.environ:
        return os.environ["XDG_CONFIG_HOME"]
    return os.path.join(os.environ["HOME"], ".config")


__CONFIG__ = Config(__DEFAULT_CONFG)

__CONFIG_FILE_NAME__ = "corona.conf"
__CONFIG_PATH__ = os.path.join(find_config_home(), __CONFIG_FILE_NAME__)

if not os.path.exists(__CONFIG_PATH__):
    logger.error("Config file not found!")
    exit(1)

config = configparser.ConfigParser()
config.read(__CONFIG_PATH__)

for name, value in config._sections.items():
    __CONFIG__.add_section(name, value)

if __CONFIG__.settings.debug:
    logger.warning("You are running in DEBUG mode!")
    logger.setLevel(logging.DEBUG)
    __CONFIG__.cache.enabled = False

if __CONFIG__.cache.enabled:
    if not os.path.exists(__CONFIG__.cache.location):
        os.makedirs(__CONFIG__.cache.location)
else:
    logger.warning("Caching is disabled!")

if os.environ.get("CORONA_OVERPASS_ENDPOINT"):
    __CONFIG__.overpass.endpoint = os.environ.get("CORONA_OVERPASS_ENDPOINT")
if os.environ.get("CORONA_NOMINATIM_ENDPOINT"):
    __CONFIG__.nominatim.endpoint = os.environ.get("CORONA_NOMINATIM_ENDPOINT")

if not __CONFIG__.overpass.endpoint or not __CONFIG__.nominatim.endpoint:
    logger.error("Could not find a configuration for Nominatim and Overpass!")
    exit(1)

if __CONFIG__.overpass.endpoint.startswith("'") or __CONFIG__.overpass.endpoint.startswith('"'):
    raise ValueError(f"Overpass endpoint seems to be double-quoted: {__CONFIG__.overpass.endpoint}")

if not __CONFIG__.overpass.endpoint.endswith("/"):
    __CONFIG__.overpass.endpoint += "/"

if __CONFIG__.nominatim.endpoint.startswith("'") or __CONFIG__.nominatim.endpoint.startswith('"'):
    raise ValueError(f"Nominatim endpoint seems to be double-quoted: {__CONFIG__.nominatim.endpoint}")

if not __CONFIG__.nominatim.endpoint.endswith("/"):
    __CONFIG__.nominatim.endpoint += "/"

if os.environ.get("CORONA_DB_HOST"):
    __CONFIG__.database.host = os.environ.get("CORONA_DB_HOST")
if os.environ.get("CORONA_DB_NAME"):
    __CONFIG__.database.name = os.environ.get("CORONA_DB_NAME")
if os.environ.get("CORONA_DB_USER"):
    __CONFIG__.database.user = os.environ.get("CORONA_DB_USER")
if os.environ.get("CORONA_DB_PASSWORD"):
    __CONFIG__.database.password = os.environ.get("CORONA_DB_PASSWORD")
