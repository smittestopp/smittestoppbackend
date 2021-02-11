# Smittestopp API

### Base URLs

- Prod: http://api-smittestopp-prod.azure-api.net  
- Dev: http://api-smittestopp-dev.azure-api.net  

## Mobile App Endpoints

### Authentication

The mobile app registration authenticates with a JWT token from Azure AD B2C.
The JWT token must contain the following claim:
- `_phonenumber`

Other endpoints authenticated with HMAC signatures,
using the IoTHub device id and signing key.

#### HMAC Authentication

The HMAC authentication middleware expects the following headers:
- `Authorization: SMST-HMAC-SHA256 deviceId;timestamp;b64digest`

where:

- deviceId is the iothub device id
- timestamp is the unix integer timestamp
- b64digest is the base64-encoded HMAC SHA256 digest of the message `{device_id}|{timestamp}|{VERB}|{endpoint}`, signed by a device key from iothub: 
  where `verb` is the HTTP verb in upper case (e.g. `GET` or `POST`)
  and `{endpoint}` is the name of the endpoint,
  excluding the first url path component,
  e.g. `/pin` for `/app/pin` or `/contentids` for `/app/contentids`.
  
When signing the HMAC message make sure that the secret (device key) is formatted as raw bytes, not e.g. base64.   

#### Authentication header

- `Authorization: Bearer <token>` for JWT

- `Authorization: SMST-HMAC-SHA256 deviceId;timestamp;digest` for HMAC

### Register New Device

Register a new device with iothub and associate it with an existing user profile. 

#### `POST /onboarding/register-device`

#### Response: 
CODE: `200 OK`

### Revoke Consent

Revokes permissions granted by a user. All data associated with the user will be deleted.

#### `POST /permissions/revoke-consent`

#### Response
CODE: `200 OK`  
BODY: `application/json`
```json
{
    "status": "Success",
    "message": "...",
}
```

### Request PIN

Authentication: HMAC, verb: `GET`, endpoint: `/pin`

Return pin codes for the given user.

#### `GET /app/pin`

#### Response

CODE: `200 OK`
BODY: `application/json`

```json
{
    "pin_codes": [
        {
            "pin_code": "123",
            "created_at": "2020-01-01T12:00:00Z"
        }
    ]
}
```

### Update birth year

Authentication: HMAC, verb: `POST`, endpoint: `/birthyear`

Update the birth year for the given user

#### `POST /app/birthyear`

BODY:

```json
{
    "birthyear": 1975
}
````

#### Response

CODE: `200 OK`

### Request new bluetooth contact ids

Authentication: HMAC, verb: `POST`, endpoint: `/contactids`

Allocate and return 10 new ids for use as bluetooth contact ids.

#### `POST /app/contactids`

#### Response

CODE: `200 OK`
BODY: `application/json`

```json
{
    "contact_ids": ["123", "456"],
}
```

--------------------------------

## FHI Endpoints

#### Authentication

FHI endpoints are authenticated by SSL client certificates

- SSL Certificate

 

### Lookup phone number

Auth: SSL

Requests a contact analysis to be performed for the given phone number.

####`POST /fhi/lookup`  
BODY: application/json
``` 
{
    "phone_number": "+47...",  (required)
    "time_from": "2019-12-04", (optional)
    "time_to": "2019-12-04",   (optional)
}
```
#### RESPONSE
CODE: `202 Accepted`  
BODY: `application/json` 
``` 
{
    "request_id": "1337",
    "result_url": "https://{host}/fhi/lookup/{request_id}",
    "results_expires": "2019-12-04"
}
```

### Lookup result

Auth: SSL

Checks results from the contact analysis for a given phone number. 
Returns results if the analysis is ready.

#### `GET /fhi/lookup/{request_id}`  

#### RESPONSE: 
If analysis pending: 

CODE: `202 Accepted`  
BODY: `application/json`
```json
{"message": "Not finished processing (completed 2/7 tasks)"}
```
  
If analysis complete:  

CODE: `200 OK`  
BODY: `applicaton/json`
```json
{
    "phone_number": "+47...",
    "found_in_system": true,
    "last_activity": "2020-03-20",
    "contacts": [
        {
            "+0012341234": {
                "pin_code": "pin_code",
                ...,
            }        
        }       
    ]
}
``` 

TODO: The above payload is not fully documented

### Access Log

Auth: SSL

Returns the access log for a given user. 

#### `POST /fhi/fhi-access-log`
  
BODY: `application/json` 
```json
{
    "phone_number": "+47...",   (required)
    "person_name": "Test Name", (required)
    "person_id": "123...",      (optional)
    "page_number": "1",         (optional)
    "per_page": "30",           (optional)
}
```
#### RESPONSE
CODE: `200 OK`   
BODY:  `application/json` 
```json
{
    "phone_number": "+47...",
    "found_in_system": true,
    "events":[
        {
            "timestamp": "2019-12-04",
            "phone_number": "+47...",
            "person_name": "Test name",
            "person_organization": "Test Org",
            "person_id": "123...",
            "technical_organization": "Norsk Helsenett",
            "legal_means": "Oppslag...",
            "count": 2,
        },
    ],
    "total": 42,
    "per_page": 30,
    "page_number": 1,
}
```

### Egress

Auth: SSL

Returns the GPS events for a given user.

#### `POST /fhi/fhi-egress \`
BODY: `application/json`   
```json 
{
    "phone_number": "+47...",          (required)
    "legal_means": "Innsyn i ...",     (required)
    "person_name": "Test Name",        (required)
    "person_id": "123...",             (optional)
    "person_organization": "Test Org"  (optional)
    "page_number": "1",                (optional)
    "per_page": "30",                  (optional)
    "time_from": "2019-12-04",         (optional)
    "time_to": "2019-12-04"            (optional)
}
```
#### RESPONSE: 
CODE: `200 OK`  
BODY: `application/json` 
```json
{
    "phone_number": "+47...",
    "found_in_system": true,
    "events":[
        {
            "timestamp": "2019-12-04",
            "phone_number": "+47...",
            "person_name": "Test name",
            "person_organization": "Test Org",
            "person_id": "123...",
            "technical_organization": "Norsk Helsenett",
            "legal_means": "Oppslag...",
            "count": 2,
        },
    ],
    "total": 42,
    "per_page": 30,
    "page_number": 1,
    "next": {
        "page_number": 2,
        "per_page": 30,  
    },
    "time_from": "2019-12-04", 
    "time_to": "2019-12-04" 
}
```

### Lookup deleted numbers

Auth: SSL

Takes a list of phone number and returns those not registered in our system.

#### `POST /fhi/deletions`  
BODY: `application/json`
```json
{
    "phone_numbers": [
        "+47123...",
        "+47126...",
        ...    
    ] 
}
```
#### Response
CODE: `200 OK`  
BODY: `application/json`  

```json
{
    "deleted_phone_numbers": [
        "+47123...",
        ...
    ] 
}
```

--------------------------------

## Helsenorge.no endpoints

#### Authentication

Request are authenticated with a SSL certificate in addition to a JWT token.
The JWT token must contain the following claims:
 
 - `sub` The user's person ID (personnummer)
 - `sub_given_name` ... first name 
 - `sub_middle_name`... middle name 
 - `sub_last_name`   ... last name 

#### Authentication header

`Authorization: Bearer <token>`

###  Access Log
  
Returns the access log for a given user. (Same data as the FHI endpoint with the same name). 

#### `POST /helsenorge/access-log`
  
BODY: `application/json` 
```json
{
    "person_id": "123...", (optional)
    "page_number": "1",    (optional)
    "per_page": "30",      (optional)
}
```
#### RESPONSE
CODE: `200 OK`   
BODY:  `application/json` 
```json
{
    "phone_number": "+47...",
    "found_in_system": true,
    "events":[
        {
            "timestamp": "2019-12-04",
            "phone_number": "+47...",
            "person_name": "Test name",
            "person_organization": "Test Org",
            "person_id": "123...",
            "technical_organization": "Norsk Helsenett",
            "legal_means": "Oppslag...",
            "count": 2,
        },
    ],
    "total": 42,
    "per_page": 30,
    "page_number": 1,
}
```

### Egress

Returns the GPS events for a given user. (Same data as the FHI endpoint with the same name). 

#### `POST /helsenorge/egress \`
BODY: `application/json`   
```json 
{
    "page_number": "1",        (optional)
    "per_page": "30",          (optional)
    "time_from": "2019-12-04", (optional)
    "time_to": "2019-12-04"    (optional)
}
```
#### RESPONSE: 
CODE: `200 OK`  
BODY: `application/json` 
```json
{
    "phone_number": "+47...",
    "found_in_system": true,
    "events":[
        {
            "timestamp": "2019-12-04",
            "phone_number": "+47...",
            "person_name": "Test name",
            "person_organization": "Test Org",
            "person_id": "123...",
            "technical_organization": "Norsk Helsenett",
            "legal_means": "Oppslag...",
            "count": 2,
        },
    ],
    "total": 42,
    "per_page": 30,
    "page_number": 1,
    "next": {
        "page_number": 2,
        "per_page": 30,  
    },
    "time_from": "2019-12-04", 
    "time_to": "2019-12-04" 
}
```

### Revoke consent

Revokes permissions granted by a user. All data associated with the user will be deleted.

#### POST /permissions/revoke-consent  

#### Response
CODE: `200 OK`  
BODY: `application json`

```json
{
    "status": "Success",
    "message": "...",
}
```
