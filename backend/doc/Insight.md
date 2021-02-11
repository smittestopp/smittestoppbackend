# Plan for new citizen Insight solution

We want to change the Insight solution into a two-stage process. In stage one, you will order your data. In stage two, when data is ready, you will get the option to download the prepared data. 

## Endpoints for Helsenorge and FHI (manual insight)

The endpoints will be exposed similarly to how it is done today, with the same security model. Due the two-stage process, there will be some adjustments. For Helsenorge, stage one will be initiated by doing a `POST` request at `/helsenorge/egress` with the user authenticated as today. There will however not be a need for the payload including timerange and paging, as all data for the authenticated user will be prepared. The response from this call will indicate if the request was successful by returning a unique `request_id` as well as an indication of how long the request is valid. In order to retrieve data, a `GET` request should be sent to `/helsenorge/egress/{request_id}`:

- If data is not yet ready, which will be the case while the request is processed, the endpoint will return status `202` and some text-message indicating that we're still working on the request.
- When data is ready, the endpoint will return status `200` as well as the data in the body. The returned data may be chunked such that a large result-set from the request can be streamed to the enduser. The returned data will be formatted as `json` documents in a zip archive.
- If the `request_id` is expired or invalid, status `404` will be returned.

On the Helsenorge side it will be necessary to store the `request_id` for the user as preparation of the data may take some time. The frontend can however start polling for data immediately, and if the citizen has a small data set it may be delivered within minutes. For a citizen with a large data set it may however take a long time so the system should support that the user log off the system and get back later, at which point the system should again poll for the previous request.

For the manual insight solution at FHI, the new version will very closely match the implementation of the tracking-solution (`/lookup/`), so the implementation of `/fhi/fhi-egress` needs to be udpated accordingly.

## Updates on the Simula-side

We will reuse the pattern created for running the analytics pipeline initiated from `/lookup`. We will need to set up a separate redis queue, and refactor the redis integration such that it can also be used from the new endpoint. In order to serialize the request, to not cause to much load on the database, we will initially only use one worker, that will poll the redis queue for tasks and process them sequentially. The result will be posted back to redis where data can be fetched and returned when the `GET` request is received. 

The resulting data set in redis will be stored with an expiry property of some specified duration, after which the key and the associated data set will be deleted. 

Since there might be several `uuid`s connected to a single phonenumber, there might be several data sets to be returned to the end user. We suggest that we will not mark the request as fully processed and ready for retrieval, until all `uuid`s are processed. 

Initial analysis indicates that the data size for an individual `uuid` amounts to a few megabytes at max, and redis will support storing 512MB for a single key. This is thus well within limitations at least for a single `uuid`. We need more detailed planning to decide if we will store result for the individual `uuid`s in a request using separate keys in redis, and combining the results when shipping them out, or if we should combine all data in storage for a single redis key.
