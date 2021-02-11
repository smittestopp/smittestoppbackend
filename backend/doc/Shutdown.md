# Plan for shutdown of data collection

## Outline

We need to temporarily stop collecting data. We want to do this is in a way that makes it relatively easy to restart the system. The main steps we need to take are

1. Disable device-registration in B2C and the onboarding service
2. Disable data-collection in IOT hub
3. Stop the jobs that import data from Lake to SQL, and stop all data aggregation tasks
4. Delete all data from data lake
5. Delete all the registered devices/phonenumbers in Azure AD
6. Drop and recreate all tables in SQL

## Plan in a few more details

### B2C 

We want to keep B2C running, but denying any new registrations. Then we can display a meaningful message about the system being closed temporarily. 

### AD

Run a script for deleting all phonenumbers and associations to device id's. `IOT_ONLY` must be set `False` in the script to enable AD deletion.

We experimented with the bulk-delete option in Azure portal, but in the end it was probably slower than just running our own script.

### IOT hub

Delete all the device ids and keys from IOT hub.  When all the device keys have been removed, and all users have been removed from AD in the previous step, no device should be able to send data through IOT hub. This is part of the same script that delete AD user/groups. 

### SQL and data lake

The import job from lake to data base, as well as the different tasks in the SQL server it self, needs to be stopped by someone with necessary permissions. 

Delete all data from the lake. Deleting the top-level lake folder in the Azure UI will achieve this.

We like to drop all the tables from production SQL. After tables and indecies are dropped, we like to recreate the table schemas and the indecies such that the system easily can be re-enabled should FHI request this. When all data is gone from the data lake, and it is confirmed that no new data is coming in, the import jobs should also be enabled again such that the system is ready to start again. But part-2 of this (recreating tables) is not urgent.
