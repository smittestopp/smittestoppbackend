-- run in master
select newid()

-- run in db
/*
create user smittewriter from login smittewriter
GO
EXEC sp_addrolemember N'db_datareader', smittewriter
GO
EXEC sp_addrolemember N'db_datawriter', smittewriter
GO
deny all on applog to smittewriter
*/

-- Production
CREATE LOGIN coronaanalyst1
	WITH PASSWORD = '' 
GO
CREATE LOGIN coronaanalyst2
	WITH PASSWORD = '' 
GO
CREATE LOGIN coronapipeline
	WITH PASSWORD = '' 
GO
-- run in db
drop user coronaanalyst1
drop login coronaanalyst1
go
drop user coronaanalyst2
drop login coronaanalyst2
go
drop user coronapipeline
drop login coronapipeline
go
create user coronaanalyst1 from login coronaanalyst1
GO
create user coronaanalyst2 from login coronaanalyst2
GO
create user coronapipeline from login coronapipeline
GO
-- May need to disconnect and reconnect to get new access token if expired
CREATE user [FHI-Smittestopp-Analytics-Prod] FROM EXTERNAL PROVIDER
GO
CREATE user [FHI-Smittestopp-Sletteservice-Prod] FROM EXTERNAL PROVIDER
GO
CREATE user [FHI-Smittestopp-ServiceAPI-Prod] FROM EXTERNAL PROVIDER
GO
Create user [FHI-Smittestopp-Sqlimport-Prod] FROM EXTERNAL PROVIDER
GO


-- In production only give access to functions or procs
grant execute on adlsimporter to [FHI-Smittestopp-Sqlimport-Prod]
GRANT ADMINISTER DATABASE BULK OPERATIONS TO [FHI-Smittestopp-Sqlimport-Prod];
go
/*
deny all on applog to coronaanalyst1
grant execute on getdatabyUUIDList to coronaanalyst1
grant select on dbo.fnGetDistanceT to coronaanalyst1
grant select on [dbo].[getIntersectedTrajectories] to coronaanalyst1
grant select on [dbo].[getIntersectedTrajectories2] to coronaanalyst1
grant select on [dbo].[getIntersectedTrajectoriesBySumoverlaptime] to coronaanalyst1
grant select on [dbo].[getIntersectedTrajectoriesIntersectSpeed2] to coronaanalyst1
grant select on [dbo].[getIntersectedTrajectoriesSpeed] to coronaanalyst1
grant select on [dbo].[getIntersectedTrajectoriesSpeed2] to coronaanalyst1
grant select on [dbo].[getIntersections] to coronaanalyst1
grant select on [dbo].[getSumIntersectedOverlaps] to coronaanalyst1
grant select on [dbo].[getTrajectory] to coronaanalyst1
grant select on [dbo].[getTrajectorySpeed] to coronaanalyst1
grant select on [dbo].[getWithinPolygons] to coronaanalyst1
grant select on getOthersTrajectories to coronaanalyst1
grant select on getBluetoothPairing to coronaanalyst1;




GO
deny all on applog to coronaanalyst2
grant execute on getdatabyUUIDList to coronaanalyst2
grant select on dbo.fnGetDistanceT to coronaanalyst2
grant select on [dbo].[getIntersectedTrajectories] to coronaanalyst2
grant select on [dbo].[getIntersectedTrajectories2] to coronaanalyst2
grant select on [dbo].[getIntersectedTrajectoriesBySumoverlaptime] to coronaanalyst2
grant select on [dbo].[getIntersectedTrajectoriesIntersectSpeed2] to coronaanalyst2
grant select on [dbo].[getIntersectedTrajectoriesSpeed] to coronaanalyst2
grant select on [dbo].[getIntersectedTrajectoriesSpeed2] to coronaanalyst2
grant select on [dbo].[getIntersections] to coronaanalyst2
grant select on [dbo].[getSumIntersectedOverlaps] to coronaanalyst2
grant select on [dbo].[getTrajectory] to coronaanalyst2
grant select on [dbo].[getTrajectorySpeed] to coronaanalyst2
grant select on [dbo].[getWithinPolygons] to coronaanalyst2
grant select on getOthersTrajectories to coronaanalyst2
grant select on getBluetoothPairing to coronaanalyst2;


GO
deny all on applog to coronapipeline
grant execute on getdatabyUUIDList to coronapipeline
grant select on dbo.fnGetDistanceT to coronapipeline
grant select on [dbo].[getIntersectedTrajectories] to coronapipeline
grant select on [dbo].[getIntersectedTrajectories2] to coronapipeline
grant select on [dbo].[getIntersectedTrajectoriesBySumoverlaptime] to coronapipeline
--grant select on [dbo].[getIntersectedTrajectoriesIntersectSpeed2] to coronapipeline
grant select on [dbo].[getIntersectedTrajectoriesSpeed] to coronapipeline
grant select on [dbo].[getIntersectedTrajectoriesSpeed2] to coronapipeline
grant select on [dbo].[getIntersections] to coronapipeline
grant select on [dbo].[getSumIntersectedOverlaps] to coronapipeline
grant select on [dbo].[getTrajectory] to coronapipeline
grant select on [dbo].[getTrajectorySpeed] to coronapipeline
grant select on [dbo].[getWithinPolygons] to coronapipeline
grant select on getOthersTrajectories to coronapipeline
grant select on getBluetoothPairing to coronapipeline;
grant select on getDeviceInformationSingle to coronapipeline;
*/
GO
grant execute on deleteforUUID to [FHI-Smittestopp-Sletteservice-Prod];
grant execute on apploginsert to [FHI-Smittestopp-Sletteservice-Prod];
grant execute on latestActivityForUUID to [FHI-Smittestopp-Sletteservice-Prod];
grant execute on getLastActivityBefore to [FHI-Smittestopp-Sletteservice-Prod];

GO
grant execute on applogfetch to [FHI-Smittestopp-ServiceAPI-Prod];
grant execute on apploginsert to [FHI-Smittestopp-ServiceAPI-Prod];
grant execute on getdatabyUUIDList to [FHI-Smittestopp-ServiceAPI-Prod];
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



GO
--revoke execute on latestActivityForUUID to [FHI-Smittestopp-Sletteservice-Prod];

--check permissions on a object
SELECT
  (
    dp.state_desc + ' ' +
    dp.permission_name collate latin1_general_cs_as + 
    ' ON ' + '[' + s.name + ']' + '.' + '[' + o.name + ']' +
    ' TO ' + '[' + dpr.name + ']'
  ) AS GRANT_STMT
FROM sys.database_permissions AS dp
  INNER JOIN sys.objects AS o ON dp.major_id=o.object_id
  INNER JOIN sys.schemas AS s ON o.schema_id = s.schema_id
  INNER JOIN sys.database_principals AS dpr ON dp.grantee_principal_id=dpr.principal_id
WHERE 1=1
    AND o.name IN ('getLastActivityBefore')      -- Uncomment to filter to specific object(s)
--  AND dp.permission_name='EXECUTE'    -- Uncomment to filter to just the EXECUTEs
ORDER BY dpr.name
