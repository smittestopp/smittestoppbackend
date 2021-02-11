IF NOT EXISTS (
    SELECT 1
    FROM master.sys.server_principals
    WHERE name = 'fhi-smittestop-analytics-login'
)
BEGIN
CREATE LOGIN [fhi-smittestop-analytics-login]
    WITH PASSWORD = 'Pa55w0rd'
END

GO

IF NOT EXISTS (
    SELECT 1
    FROM master.sys.server_principals
    WHERE name = 'fhi-smittestop-sletteservice-login'
)
BEGIN
CREATE LOGIN [fhi-smittestop-sletteservice-login]
    WITH PASSWORD = 'Pa55w0rd'
END

GO

IF NOT EXISTS (
    SELECT 1
    FROM master.sys.server_principals
    WHERE name = 'fhi-smittestop-serviceapi-login'
)
BEGIN
CREATE LOGIN [fhi-smittestop-serviceapi-login]
    WITH PASSWORD = 'Pa55w0rd'
END

GO

IF NOT EXISTS (
    SELECT 1
    FROM master.sys.server_principals
    WHERE name = 'fhi-smittestop-sqlimport-login'
)
BEGIN
CREATE LOGIN [fhi-smittestop-sqlimport-login]
    WITH PASSWORD = 'Pa55w0rd'
END

GO

IF NOT EXISTS (
    SELECT 1
    FROM master.sys.server_principals
    WHERE name = 'fhi-smittestop-registration-login'
)
BEGIN
CREATE LOGIN [fhi-smittestop-registration-login]
    WITH PASSWORD = 'Pa55w0rd'
END

GO

CREATE user [FHI-Smittestopp-Analytics-Prod] FROM LOGIN [fhi-smittestop-analytics-login]
GO
CREATE user [FHI-Smittestopp-Sletteservice-Prod] FROM LOGIN [fhi-smittestop-sletteservice-login]
GO
CREATE user [FHI-Smittestopp-ServiceAPI-Prod] FROM LOGIN [fhi-smittestop-serviceapi-login]
GO
Create user [FHI-Smittestopp-Sqlimport-Prod] FROM LOGIN [fhi-smittestop-sqlimport-login]
GO
Create user [FHI-Smittestopp-Registration-Prod] FROM LOGIN [fhi-smittestop-registration-login]
GO


-- In production only give access to functions or procs
grant execute on adlsimporter to [FHI-Smittestopp-Sqlimport-Prod]
--GRANT ADMINISTER DATABASE BULK OPERATIONS TO [FHI-Smittestopp-Sqlimport-Prod];
go



grant execute on deleteforUUID to [FHI-Smittestopp-Sletteservice-Prod];
grant execute on apploginsert to [FHI-Smittestopp-Sletteservice-Prod];
grant execute on latestActivityForUUID to [FHI-Smittestopp-Sletteservice-Prod];
grant execute on getLastActivityBefore to [FHI-Smittestopp-Sletteservice-Prod];

GO
grant execute on applogfetch to [FHI-Smittestopp-ServiceAPI-Prod];
grant execute on apploginsert to [FHI-Smittestopp-ServiceAPI-Prod];
grant execute on getdatabyUUIDList to [FHI-Smittestopp-ServiceAPI-Prod];
grant execute on dbo.insertPinCode to [FHI-Smittestopp-ServiceAPI-Prod];
grant execute on dbo.getnewuuids to [FHI-Smittestopp-Registration-Prod]
grant execute on dbo.upsertBirthYear to [FHI-Smittestopp-Registration-Prod];
grant select on dbo.getPinCodesByPhoneNumber to [FHI-Smittestopp-Registration-Prod];
grant select on dbo.getPinCodeNewestEntryByThreshold to [FHI-Smittestopp-Registration-Prod];
grant select on dbo.getPinCodesByPhoneNumber to [FHI-Smittestopp-ServiceAPI-Prod];
grant select on dbo.getPinCodeNewestEntryByThreshold to [FHI-Smittestopp-ServiceAPI-Prod];
grant select on dbo.getBirthYear to [FHI-Smittestopp-ServiceAPI-Prod];


GO
grant execute on getdatabyUUIDList to [FHI-Smittestopp-Analytics-Prod];
grant select on dbo.fnGetDistanceT to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getIntersectedTrajectories] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getIntersectedTrajectories2] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getIntersectedTrajectoriesBySumoverlaptime] to [FHI-Smittestopp-Analytics-Prod];
--grant select on [dbo].[getIntersectedTrajectoriesIntersectSpeed2] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getIntersectedTrajectoriesSpeed] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getIntersectedTrajectoriesSpeed2] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getIntersections] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getSumIntersectedOverlaps] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getTrajectory] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getTrajectorySpeed] to [FHI-Smittestopp-Analytics-Prod];
grant select on [dbo].[getWithinPolygons] to [FHI-Smittestopp-Analytics-Prod];
grant select on getOthersTrajectories to [FHI-Smittestopp-Analytics-Prod];
grant select on getBluetoothPairing to [FHI-Smittestopp-Analytics-Prod];
grant select on getDeviceInformationSingle to [FHI-Smittestopp-Analytics-Prod];
grant select on getDeviceInformation to [FHI-Smittestopp-Analytics-Prod];
grant select on [getTrajectoryV2] to [FHI-Smittestopp-Analytics-Prod];
grant select on getGPSWithinGrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on getGPSWithinMultipleGrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on getBTWithinGrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on getUniqueUUIDsWithinGrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on getUniqueUUIDsWithinMultipleGrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on getBTWithinMultipleGrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on getwithinBB to [FHI-Smittestopp-Analytics-Prod];
grant select on getUniqueUUIdswithinBB to [FHI-Smittestopp-Analytics-Prod];
grant select on [getWithinBBlist] to [FHI-Smittestopp-Analytics-Prod];
grant select on [getBTpairingsWithinBB] to [FHI-Smittestopp-Analytics-Prod];
grant select on [getBTpairingsWithinPolygons] to [FHI-Smittestopp-Analytics-Prod];



