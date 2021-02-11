# Corona backend

This is base image for the backend, and all the other images depend on some parts of this image.
The app is written using the [tornado](https://www.tornadoweb.org/en/stable/) web framework, and makes heavily use of asynchronous programming.
People that are not familiar with the `async` and `await` keywords and want to understand more what is going on, should read up on that (see e.g [Async IO in Python: A Complete Walkthrough](https://realpython.com/async-io-python/)). 

## Setting up a local development environment

Please consult the section about *Local development* in the [README file in the backend folder](../../README.md).
Alternatively, you can type `make source` in this directory.


## Running the app
If you have set up everything correctly you should be able to execute the command

```
python -m corona_backend
```

and this should that the app (alternatively you can to `make start`). Executing the command `python -m corona_backend` will run `corona_backend/__main__.py` and you can see what is happening from there. 

## Structure of the code

### Handlers

This app has three handlers: 

- The `HealthHandler` has one GET method and is defined in [`handlers.py`](corona_backend/handlers.py). This is basically just a handler for checking that the app is running. If you have the app running locally (say on port 8080), then the health handler will print "ok" if you go to the url http://localhost:8080/health

- The `RegisterDeviceHandler` has one POST method and is defined in [`app.py`](corona_backend/app.py). This has one post method which will register a new device for the current user making the post request.

- The `RevokeConsentHandler` has one POST method and is defined in [`app.py`](corona_backend/app.py). This has one post method which will remove and delete all devices associated with a user and finally delete the user.

Note that both the `RegisterDeviceHandler` and `RevokeConsentHandler` need the user to be authenticated (since the post methods are decorated with `@web.authenticated`). For testing, you can either mock the `get_current_user` method on the handlers which is what is done in the [tests](corona_backend/tests/test_handlers.py).
Alternatively you can request a token for you own phone number by visiting [this link](https://devsmittestopp.b2clogin.com/devsmittestopp.onmicrosoft.com/oauth2/v2.0/authorize?p=B2C_1A_phone_SUSI&client_id=<client_id>&nonce=defaultNonce&redirect_uri=https%3A%2F%2Fjwt.ms&scope=https%3A%2F%2Fdevsmittestopp.onmicrosoft.com%2Fbackend%2FDevice.Write&response_type=token&prompt=login)) (note that this is the same link as on the README file in the `backend` folder) and use your own phone number for testing. See e.g [`test_device.py`](../../test/test_device.py) for a working example.

## REST APIs

There are two main REST APIs used in this image; the [graph REST API](https://docs.microsoft.com/en-us/graph/api/overview?view=graph-rest-1.0) and the [IoT Hub REST API](https://docs.microsoft.com/en-us/rest/api/iothub/). 

When a new user is created, it is created using the graph REST API, and a user with an id `user_id` is stored in the endpoint `/users/user_id`. 
A GET requests to this endpoint returns a response where the key `logName` is a masked version of the users phone number.
Other useful endpoints for the graph REST API are

* `/groups/` - Endpoints for all devices
* `/groups/<group_id>` - Endpoint for a specific device 
    - A GET request returns a  response where the key with name `displayName` which is the id for the device in the IoT Hub REST API, i.e the `device_id` described below.
* `/groups/<group_id>/members/<user_id>` - User id associated with device


For the IoT Hub REST API the main endpoint is the `/devices/<device_id>`.
There is also an endpoint at `/devices/query` which is used when querying for devices. 

## Testing

The tests for this image is found in [corona_backend/tests](corona_backend/tests), and you can run the tests by executing the command `make test`. 
The tests makes use of some other third-party dependencies that you can install by executing the command `make install-dev-deps`.
We have chosen [`pytest`](https://docs.pytest.org/en/latest/) as the testing framework.

### Starting testdb container

Some tests are depending on a test database running in a docker container.
Start this container with `make build_run` inside the repository corona/sql/testsql.
N.B. it takes a few seconds before the sql server is ready after the container has been run.

The `Microsoft ODBC 17` driver is required to connect to the database. See https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server  

### Testing async code

Any test can be an async coroutine defined by `async def`.
It will be run by asyncio using the `pytest-asyncio` plugin.


```python
async def fun():
    return 5

async def test_fun():
    result = await fun()
    assert result == 5
```

One thing to note in the tests, is that we need to write some helper functions in cases when we want to make calls to async generators in order to exhaust the generator and put the elements into a list.


### Coverage report

When the test suite are done running you will see a folder called `htmlcov` appearing in this directory. This is created by the coverage plugin, [`pytest-cov`](https://pytest-cov.readthedocs.io/en/latest/). If you open `index.html` inside that directory you can see the coverage report. You can also click on each individual filename to see which lines that are covered by the tests and which that are not. You can change the settings for the coverage by editing the file [`.coveragerc`](.coveragerc).


### Other useful tools for testing

Another useful tool for testing the app is [Postman](https://www.postman.com). This tool can be used to create post requests (and other types for request) to test the API.
