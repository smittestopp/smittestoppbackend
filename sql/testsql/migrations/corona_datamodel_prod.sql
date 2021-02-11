/* 
Smittestopp data model
*/

/*
If we want to do a change to a table, and can't just use ALTER TABLE, use this pattern:

-- 1 go and stop the Stream Analytics service in Azure portal
-- 2 copy the table content to a temp table :
select * into userevents2 from userevents
select * into userevents_bluetooth2 from userevents_bluetooth
-- 3 do the table change
-- 4 copy back from the temp table
insert into userevents
select * from userevents2
insert into userevents_bluetooth
select * from userevents_bluetooth2
-- 5 drop the temp table
drop table userevents2
drop table userevents_bluetooth2
drop table userevents_location2
-- 6 go and start the Stream Analytics service from the time it was last stopped
*/

/*
-- First create partition layout for table partitioning, need to do this first time model is created
-- Split on date DAYOFYEAR, generate partitions for every DAYOFYEAR
-- Every day we then run a job (in Azure Data Factory for example) to empty the +30 day old partition:
-- Running TRUNCATE per partition eliminates logging and per-row locks 
-- See procedure for 30day deletes for details

*/


--drop partition scheme rangePS -- If you are changing the partition scheme, need to drop tables first
go
--drop partition function rangePF
go
declare @i int = 1
declare @sql nvarchar(max) = 'CREATE PARTITION FUNCTION rangePF (smallint) 
AS RANGE LEFT FOR VALUES ('
while @i < 366 begin
	set @sql = @sql + cast(@i as varchar(3)) + ','
	set @i = @i + 1
end 
set @sql = @sql + '366)'
--print @sql
exec sp_executesql @sql;
GO
CREATE PARTITION SCHEME rangePS  
AS PARTITION rangePF  
ALL TO ( [PRIMARY] );  
GO

-- userdata table
-- For this table we are using a PK clustered index, partitined and compressed
-- If you are dropping the table for temp changes, drop trigger first and apply trigger after changes!!
--drop TABLE [dbo].[userdata]
GO

CREATE TABLE [dbo].[userdata](
	[uuid] varchar(36) NOT NULL,
	[platform] [varchar](100) NULL,
	[osversion] [varchar](100) NULL,
	[appversion] [varchar](100) NULL,
	model varchar(100) null,
	createtime datetime2(0) default cast(getdate() as datetime2(0))
) ON [PRIMARY]
GO

create clustered index cix_userdata on userdata(uuid) with (data_compression=row);
go


-- INSTEAD OF Trigger for insert from stream analytics, to stop duplicated rows to enter
--drop trigger userdata_insert
go
create trigger userdata_insert 
on dbo.userdata instead of insert
as
set nocount on
insert into userdata(uuid,platform,osversion,appversion,model, createtime)
select distinct i.uuid, 
	dbo.RemoveNonASCII(i.platform) as platform, 
	dbo.RemoveNonASCII(i.osversion) as osversion,
	dbo.RemoveNonASCII(i.appversion) as appversion,
	dbo.RemoveNonASCII(i.model) as model,
	i.createtime
from inserted i
join userdata u on i.uuid <> u.uuid
	and dbo.RemoveNonASCII(i.platform) <> u.platform
	and dbo.RemoveNonASCII(i.osversion) <> u.osversion
	and dbo.RemoveNonASCII(i.appversion) <> u.appversion
	and dbo.RemoveNonASCII(i.model) <> u.model 
go

-- this is the main events table for GPS data, we are keeping the lat/long data here 
--drop TABLE [dbo].[userevents]
GO

CREATE TABLE [dbo].[userevents](
	[uuid] varchar(36) NOT NULL,
	[timefrom] datetime2(0) NOT NULL,
	[timeto] datetime2(0) NOT NULL,
	latitude decimal(9,6) NOT NULL,
	longitude decimal(9,6) NOT NULL,
	[accuracy] float(24) default 0,
	speed float(24) NOT NULL,
	speedaccuracy float(24) default 0,
	altitude float(24) NOT NULL,
	altitudeaccuracy float(24) default 0,
	daypart smallint not null
) ON rangePS(daypart)
GO

-- this table will benefit from a single, covering, partitioned columnstore index
create clustered columnstore index cix_userevents on userevents on rangePS(daypart)
GO

/*
Currently testing shows that the above index is sufficient, but we'll keep these indexes on hand in case
*/
CREATE NONCLUSTERED INDEX [nix_userevents] ON [dbo].[userevents]
([timefrom] ASC,[timeto] ASC) INCLUDE([uuid],[latitude],[longitude]) WITH (STATISTICS_NORECOMPUTE = OFF, Data_compression=row, DROP_EXISTING = OFF, ONLINE = OFF)
GO
CREATE NONCLUSTERED INDEX [nix2_userevents] ON [dbo].[userevents]
(uuid asc, [timefrom] ASC,[timeto] ASC) INCLUDE([latitude],[longitude]) WITH (STATISTICS_NORECOMPUTE = OFF, Data_compression=row, DROP_EXISTING = OFF, ONLINE = OFF)
GO

-- Bluetooth events table
--drop TABLE [dbo].[userevents_bluetooth]
GO

CREATE TABLE [dbo].[userevents_bluetooth](
	[uuid] varchar(36) NOT NULL,
	[paireddeviceid] varchar(36) NULL,
	[pairedtime] datetime2(0) NOT NULL,
	[rssi] int not NULL,
	[txpower] int not NULL default 0,
	daypart smallint NOT NULL
) ON rangePS(daypart)
GO
-- this table will benefit from a single, covering, partitioned columnstore index
create clustered columnstore index cix_userevents_bluetooth on userevents_bluetooth on rangePS(daypart)
GO

-- This table is for analysts storing query results, we might not need it
drop TABLE IF EXISTS smittestopp.contact_graph;
go
CREATE TABLE contact_graph(
userID_infected varchar(50) NOT NULL,
userID_susceptible varchar(50) NOT NULL,
time_contact_from datetime NOT NULL,
time_contact_to datetime NOT NULL,
contact_start_long decimal(25,20) NULL,
contact_start_lat decimal(25,20) NULL,
PoI varchar(50) NULL,
transport_mode varchar(50) NULL,
aver_distance float NULL,
SD_distance float NULL,
cumulative_time_contact float NULL,
PRIMARY KEY (userID_infected,userID_susceptible,time_contact_from,time_contact_to)
);
go

			     
-- Adding all tables in PROD from script 
			     
/****** Object:  Table [dbo].[agg_gpsevents]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[agg_gpsevents](
	[id] [int] NULL,
	[timefrom] [datetime2](0) NULL,
	[timeto] [datetime2](0) NULL,
	[latitude] [decimal](8, 2) NULL,
	[longitude] [decimal](8, 2) NULL,
	[grunnkrets_id] [smallint] NULL,
	[accuracy] [tinyint] NULL,
	[speed] [tinyint] NULL,
	[daypart] [smallint] NULL
) ON [rangePS]([daypart])
GO
/****** Object:  Table [dbo].[applog]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[applog](
	[timest] [datetime] NOT NULL,
	[phoneNumber] [nvarchar](20) NULL,
	[personorrole] [nvarchar](200) NULL,
	[organization] [nvarchar](200) NULL,
	[legalmeans] [nvarchar](200) NULL,
	[personid] [nvarchar](200) NULL,
	[personorg] [nvarchar](200) NULL
) ON [PRIMARY]
GO

CREATE CLUSTERED INDEX [clix_applog] ON [dbo].[applog]
(
	[timest] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF) ON [PRIMARY]
GO


/****** Object:  Table [dbo].[btevents]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[btevents](
	[id] [int] NOT NULL,
	[pairedtime] [datetime2](0) NOT NULL,
	[rssi] [smallint] NOT NULL,
	[txpower] [smallint] NOT NULL,
	[daypart] [smallint] NOT NULL,
	[pairedid] [int] NULL
) ON [rangePS]([daypart])
GO

CREATE CLUSTERED COLUMNSTORE INDEX [cix_btevents] ON [dbo].[btevents] WITH (DROP_EXISTING = OFF, COMPRESSION_DELAY = 10)
GO

CREATE NONCLUSTERED INDEX [nix2_btevents] ON [dbo].[btevents]
(
	[pairedid] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF)
GO



/****** Object:  Table [dbo].[btevents_old]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[btevents_old](
	[id] [int] NOT NULL,
	[pairedtime] [datetime2](0) NOT NULL,
	[rssi] [smallint] NOT NULL,
	[txpower] [smallint] NOT NULL,
	[daypart] [smallint] NOT NULL,
	[pairedid] [int] NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[btevents_old2]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[btevents_old2](
	[id] [int] NOT NULL,
	[pairedtime] [datetime2](0) NOT NULL,
	[rssi] [smallint] NOT NULL,
	[txpower] [smallint] NOT NULL,
	[daypart] [smallint] NOT NULL,
	[pairedid] [int] NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[dluserdatastaging]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[dluserdatastaging](
	[uuid] [varchar](36) NOT NULL,
	[platform] [varchar](100) NULL,
	[osversion] [varchar](100) NULL,
	[appversion] [varchar](100) NULL,
	[model] [varchar](100) NULL,
	[ev] [varchar](max) NULL,
	[daypart] [smallint] NULL,
	[hourpart] [tinyint] NULL,
	[filepath] [varchar](2000) NULL,
	[isgps] [bit] NULL
) ON [rangePS]([daypart])
GO

CREATE CLUSTERED COLUMNSTORE INDEX [cix_dluserdatastaging] ON [dbo].[dluserdatastaging] WITH (DROP_EXISTING = OFF, COMPRESSION_DELAY = 15)
GO

CREATE NONCLUSTERED INDEX [nix_dluserdatastaging] ON [dbo].[dluserdatastaging]
(
	[uuid] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF)
GO



/****** Object:  Table [dbo].[dluserdatastaging_old]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[dluserdatastaging_old](
	[uuid] [varchar](36) NOT NULL,
	[platform] [varchar](100) NULL,
	[osversion] [varchar](100) NULL,
	[appversion] [varchar](100) NULL,
	[model] [varchar](100) NULL,
	[ev] [varchar](max) NULL,
	[daypart] [smallint] NULL,
	[hourpart] [tinyint] NULL,
	[filepath] [varchar](2000) NULL,
	[isgps] [bit] NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[dluserdatastaging_old2]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[dluserdatastaging_old2](
	[uuid] [varchar](36) NOT NULL,
	[platform] [varchar](100) NULL,
	[osversion] [varchar](100) NULL,
	[appversion] [varchar](100) NULL,
	[model] [varchar](100) NULL,
	[ev] [varchar](max) NULL,
	[daypart] [smallint] NULL,
	[hourpart] [tinyint] NULL,
	[filepath] [varchar](2000) NULL,
	[isgps] [bit] NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[gpsevents]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[gpsevents](
	[id] [int] NOT NULL,
	[timefrom] [datetime2](0) NOT NULL,
	[timeto] [datetime2](0) NOT NULL,
	[latitude] [decimal](9, 6) NOT NULL,
	[longitude] [decimal](9, 6) NOT NULL,
	[accuracy] [real] NOT NULL,
	[speed] [real] NOT NULL,
	[speedaccuracy] [real] NOT NULL,
	[altitude] [real] NOT NULL,
	[altitudeaccuracy] [real] NOT NULL,
	[daypart] [smallint] NOT NULL,
	[mps] [real] NULL
) ON [rangePS]([daypart])
GO

CREATE CLUSTERED COLUMNSTORE INDEX [cix_gpsevents] ON [dbo].[gpsevents] WITH (DROP_EXISTING = OFF, COMPRESSION_DELAY = 10)
GO

CREATE NONCLUSTERED INDEX [nix_btevents] ON [dbo].[gpsevents]
(
	[id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF)
GO

/****** Object:  Table [dbo].[gpsevents_old2]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[gpsevents_old2](
	[id] [int] NOT NULL,
	[timefrom] [datetime2](0) NOT NULL,
	[timeto] [datetime2](0) NOT NULL,
	[latitude] [decimal](9, 6) NOT NULL,
	[longitude] [decimal](9, 6) NOT NULL,
	[accuracy] [real] NOT NULL,
	[speed] [real] NOT NULL,
	[speedaccuracy] [real] NOT NULL,
	[altitude] [real] NOT NULL,
	[altitudeaccuracy] [real] NOT NULL,
	[daypart] [smallint] NOT NULL,
	[mps] [real] NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[grunnkrets]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[grunnkrets](
	[grunnkrets_id] [smallint] IDENTITY(1,1) NOT NULL,
	[grunnkrets_kode] [char](8) NULL,
	[poly] [geography] NULL,
PRIMARY KEY CLUSTERED 
(
	[grunnkrets_id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

SET ARITHABORT ON
SET CONCAT_NULL_YIELDS_NULL ON
SET QUOTED_IDENTIFIER ON
SET ANSI_NULLS ON
SET ANSI_PADDING ON
SET ANSI_WARNINGS ON
SET NUMERIC_ROUNDABORT OFF
GO

CREATE SPATIAL INDEX [sip_grunnkrets] ON [dbo].[grunnkrets]
(
	[poly]
)USING  GEOGRAPHY_AUTO_GRID 
WITH (
CELLS_PER_OBJECT = 12, STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF) ON [PRIMARY]
GO



/****** Object:  Table [dbo].[stats_gpsevents]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[stats_gpsevents](
	[daypart] [smallint] NULL,
	[hourpart] [tinyint] NULL,
	[gpscount] [int] NULL,
	[btcount] [int] NULL,
	[latitude] [decimal](8, 2) NULL,
	[longitude] [decimal](8, 2) NULL
) ON [PRIMARY]
GO

CREATE CLUSTERED COLUMNSTORE INDEX [cix_stats_gpsevents] ON [dbo].[stats_gpsevents] WITH (DROP_EXISTING = OFF, COMPRESSION_DELAY = 0) ON [PRIMARY]
GO


/****** Object:  Table [dbo].[uuid_activity]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[uuid_activity](
	[id] [int] NOT NULL,
	[lastactivity] [datetime2](0) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[uuid_id]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[uuid_id](
	[uuid] [varchar](36) NOT NULL,
	[id] [int] IDENTITY(1,1) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[uuid] ASC,
	[id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO

CREATE NONCLUSTERED INDEX [nix_uuid_id] ON [dbo].[uuid_id]
(
	[id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF) ON [PRIMARY]
GO


CREATE SCHEMA mon
GO

/****** Object:  Table [mon].[usermonitor]    Script Date: 5/27/2020 2:05:59 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [mon].[usermonitor](
	[currenttime] [datetime2](0) NULL,
	[platform] [varchar](100) NULL,
	[users] [int] NULL
) ON [PRIMARY]
GO
ALTER TABLE [dbo].[dluserdatastaging] ADD  DEFAULT (datepart(dayofyear,getdate())) FOR [daypart]
GO
ALTER TABLE [dbo].[dluserdatastaging] ADD  DEFAULT (datepart(hour,getdate())) FOR [hourpart]
GO
ALTER TABLE [dbo].[gpsevents] ADD  DEFAULT ((0)) FOR [accuracy]
GO
ALTER TABLE [dbo].[gpsevents] ADD  DEFAULT ((0)) FOR [speedaccuracy]
GO
ALTER TABLE [dbo].[gpsevents] ADD  DEFAULT ((0)) FOR [altitudeaccuracy]
GO

			     
CREATE CLUSTERED COLUMNSTORE INDEX [cix_usermonitor] ON [mon].[usermonitor] WITH (DROP_EXISTING = OFF, COMPRESSION_DELAY = 0) ON [PRIMARY]
GO			     
			     
create table dbo.PINcodes (
    id int primary key identity(1,1) not null,
    msisdn char(16) not null,
    pin char(10) not null,
    created_at datetime2(0) not null
)

GO

CREATE TABLE [dbo].[uuid_rotating](
	[uuid] [varchar](36) NULL,
	[new_uuid] [char](32) NOT NULL,
	[created] [datetime2](0) NULL
) ON [PRIMARY]

GO

ALTER TABLE [dbo].[uuid_rotating] ADD  DEFAULT (getdate()) FOR [created]
GO

create table dbo.BirthYear(
    uuid varchar(36) primary key,
    birthyear smallint not null,
)


			     
