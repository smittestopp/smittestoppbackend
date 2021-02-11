# Deletion service

## Where information is stored

1. Active Directory
2. Data Lake
3. SQL Database

## Information we have on the user

1. **phone number**: lives only on User objects in Active Directory, and is the only identifier used by our APIs
2. **device id**: the anonymous ID for the device, used in the database and IoT messages. **device id** is not part of any external interface.
3. phone number <-> device id **mapping**: lives only in Active Directory
4. IoTHub messages sent by the device are staged in the Data Lake for a short time before import to the database.

All FHI/Helse Norge endpoints access data only by phone number,
so data not associated with a phone number is inaccessible
to Varselsløsning and Innsynnsløsning.


## Causes for deletion

There are three reasons for data to be deleted:

1. max-age expiration (30 days for all data, 7 days for raw data cache)
1. Explicit user request, via `revoke-consent` REST API (implementation: `corona_backend.app.RevokeConsentHandler`)
2. Implicit request, inferred from a lack of new data for 7 days (implementation: `corona_delete.delete.delete_idle_users`)

Both are implemented the same (`corona_backend.graph.process_user_deletion`):

1. store consent-revoked metadata on User, to allow error recovery to complete deletion request after failure
2. delete device from IoTHub, so it will not accept new data
3. mark devices as to-be-deleted in Active Directory
4. dissociate device ids from the user
5. delete the User storing the phone number

At this point, we no longer have a record of the phone number or which devices were associated with the phone number.
Because all Innsynn/Varsels APIs use phone numbers,
the user is immediately "deleted" for all practical purposes of Innsynn/Varsels systems.
However, the data associated with their device id still resides in the Database and Data Lake until the nightly run of the deletion service.

## Bulk deletion operations

1. Data Lake files exist only to be imported to the database. They are deleted a short time after import, currently 7 days,
to allow for debugging/diagnosing import errors.
This is implemented in `corona_delete.delete:delete_raw_data()`,
and run nightly on AKS as part of the deletion service.
2. All database data older than 30 days is dropped,
   and the database staging table, which is a direct copy of the data lake,
   is deleted at the same age as the lake itself (7 days).
   This is implemented in a database routine, run nightly.

## Targeted deletion

Targeted deletion is implemented as procedures in SQL.
When a device ID is to be deleted,
the deletion service calls `deleteforUUID` to request deletion in the database (implementation: `corona_delete.delete.delete_everything()`).

The data lake, as a short-lived cache for import to the database,
is not considered by targeted deletion.
Instead, targeted deletion is guaranteed to run at least once
after the data lake records have expired.
**The lifetime of the data lake must be set such that this treatment is considered acceptable: currently 7 days.**

The actual deletion process is designed to be fault-tolerant, and resilient to possible re-import due to error recovery in the database,
and delayed delivery of data from the data lake (typical upper limit: 2 hours). The process:

1. ensure IoTHub device is deleted, in case of failure during deletion request
2. query database to find if there is data to be deleted
3. if there is data to be deleted, delete it from the database
4. finally, if there was nothing found to delete, and deletion as requested longer ago than the expiry of the data lake cache, delete the record of the device id from Active Directory.

The consequences of this design are:

1. a device will always be processed by the deletion service at least twice
2. devices will not be considered "deleted" until there is no possibility that their data is present in the database or the data lake


## Deletion service

The deletion service runs nightly in AKS, and processes these events:

1. delete the short-term data lake cache by bulk-deleting directories older than 7 days (there is a directory of data for each day).
2. identify implicit deletions by discovering devices not active in 7 days, and marking them for deletion (implementation: `corona_delete.delete.delete_idle_users()`)
3. consume devices marked for deletion and run the targeted deletion procedure for the device id (implementation: `corona_delete.delete.delete_everything()`)


