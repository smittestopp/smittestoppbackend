
/*
All users in the `dev` Database
*/

-- USERS and ROLES: 
CREATE USER [coronaanalyst] FOR LOGIN [coronaanalyst] WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [coronawriter] FOR LOGIN [coronawriter] WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [FHI-Smittestopp-Analytics-Dev] FROM  EXTERNAL PROVIDER  WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [FHI-Smittestopp-ServiceAPI-Dev] FROM  EXTERNAL PROVIDER  WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [FHI-Smittestopp-ServiceAPI-Prod] FROM  EXTERNAL PROVIDER  WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [FHI-Smittestopp-Sletteservice-Dev] FROM  EXTERNAL PROVIDER  WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [FHI-Smittestopp-Sletteservice-Prod] FROM  EXTERNAL PROVIDER  WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [FHI-Smittestopp-Sqlimport-Dev] FROM  EXTERNAL PROVIDER  WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [smittedbo] WITH DEFAULT_SCHEMA=[dbo]
CREATE USER [smittewriter] FOR LOGIN [smittewriter] WITH DEFAULT_SCHEMA=[dbo]

GO
sys.sp_addrolemember @rolename = N'db_datareader', @membername = N'coronaanalyst'
GO
sys.sp_addrolemember @rolename = N'db_ddladmin', @membername = N'coronawriter'
GO
sys.sp_addrolemember @rolename = N'db_datareader', @membername = N'coronawriter'
GO
sys.sp_addrolemember @rolename = N'db_datawriter', @membername = N'coronawriter'
GO
sys.sp_addrolemember @rolename = N'db_datareader', @membername = N'FHI-Smittestopp-Analytics-Dev'
GO
sys.sp_addrolemember @rolename = N'db_owner', @membername = N'smittedbo'
GO
sys.sp_addrolemember @rolename = N'db_datareader', @membername = N'smittewriter'
GO
sys.sp_addrolemember @rolename = N'db_datawriter', @membername = N'smittewriter'
GO



-- GRANTS and DENYS:
GRANT SELECT ON [dbo].[getNumBTpairingsWithinPolygons] TO [coronaanalyst]
GRANT SELECT ON [dbo].[getNumBTpairingsWithinPolygons_stats] TO [coronaanalyst]
DENY DELETE ON [dbo].[applog] TO [coronaanalyst]
DENY INSERT ON [dbo].[applog] TO [coronaanalyst]
DENY REFERENCES ON [dbo].[applog] TO [coronaanalyst]
DENY SELECT ON [dbo].[applog] TO [coronaanalyst]
DENY UPDATE ON [dbo].[applog] TO [coronaanalyst]
GRANT EXECUTE ON [dbo].[getdatabyUUIDList] TO [coronaanalyst]
GRANT EXECUTE ON [dbo].[getdatabyUUIDListTopN] TO [coronawriter]
GRANT EXECUTE ON [dbo].[getdatabyUUIDList] TO [coronawriter]
GRANT EXECUTE ON [dbo].[latestActivityForUUID] TO [FHI-Smittestopp-ServiceAPI-Dev]
GRANT EXECUTE ON [dbo].[getdatabyUUIDList] TO [FHI-Smittestopp-ServiceAPI-Dev]
GRANT EXECUTE ON [dbo].[applogInsert] TO [FHI-Smittestopp-ServiceAPI-Dev]
GRANT INSERT ON [dbo].[applog] TO [FHI-Smittestopp-ServiceAPI-Dev]
GRANT EXECUTE ON [dbo].[applogfetch] TO [FHI-Smittestopp-ServiceAPI-Dev]
GRANT EXECUTE ON [dbo].[getLastActivityBefore] TO [FHI-Smittestopp-Sletteservice-Dev]
GRANT EXECUTE ON [dbo].[latestActivityForUUID] TO [FHI-Smittestopp-Sletteservice-Dev]
GRANT EXECUTE ON [dbo].[deleteforUUID] TO [FHI-Smittestopp-Sletteservice-Dev]
GRANT EXECUTE ON [dbo].[deleteforUUID] TO [FHI-Smittestopp-Sletteservice-Prod]
GRANT EXECUTE ON [dbo].[gpsevents_aggregator] TO [FHI-Smittestopp-Sqlimport-Dev]
GRANT EXECUTE ON [dbo].[btimporter] TO [FHI-Smittestopp-Sqlimport-Dev]
GRANT EXECUTE ON [dbo].[gpsimporter] TO [FHI-Smittestopp-Sqlimport-Dev]
GRANT EXECUTE ON [dbo].[adlsimporter] TO [FHI-Smittestopp-Sqlimport-Dev]
GRANT EXECUTE ON [dbo].[getnewuuids] TO [FHI-Smittestopp-Registration-Dev]
DENY DELETE ON [dbo].[applog] TO [smittedbo]
DENY INSERT ON [dbo].[applog] TO [smittedbo]
DENY REFERENCES ON [dbo].[applog] TO [smittedbo]
DENY SELECT ON [dbo].[applog] TO [smittedbo]
DENY UPDATE ON [dbo].[applog] TO [smittedbo]
DENY DELETE ON [dbo].[applog] TO [smittewriter]
DENY INSERT ON [dbo].[applog] TO [smittewriter]
DENY REFERENCES ON [dbo].[applog] TO [smittewriter]
DENY SELECT ON [dbo].[applog] TO [smittewriter]
DENY UPDATE ON [dbo].[applog] TO [smittewriter]
