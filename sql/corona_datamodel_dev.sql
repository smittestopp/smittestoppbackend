
/*
All tables in the `dev` database
*/
/****** Object:  Table [dbo].[agg_gpsevents]    Script Date: 5/27/2020 2:03:39 PM ******/
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
/****** Object:  Table [dbo].[applog]    Script Date: 5/27/2020 2:03:39 PM ******/
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
/****** Object:  Table [dbo].[btevents]    Script Date: 5/27/2020 2:03:39 PM ******/
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
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[dluserdatastaging]    Script Date: 5/27/2020 2:03:39 PM ******/
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
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[gpsevents]    Script Date: 5/27/2020 2:03:39 PM ******/
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
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[grunnkrets]    Script Date: 5/27/2020 2:03:39 PM ******/
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
/****** Object:  Table [dbo].[old_userdata]    Script Date: 5/27/2020 2:03:39 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[old_userdata](
	[uuid] [varchar](36) NOT NULL,
	[platform] [varchar](100) NULL,
	[osversion] [varchar](100) NULL,
	[appversion] [varchar](100) NULL,
	[model] [varchar](100) NULL,
	[createtime] [datetime2](0) NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[old_userevents]    Script Date: 5/27/2020 2:03:39 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[old_userevents](
	[uuid] [varchar](36) NOT NULL,
	[timefrom] [datetime2](0) NOT NULL,
	[timeto] [datetime2](0) NOT NULL,
	[latitude] [decimal](9, 6) NOT NULL,
	[longitude] [decimal](9, 6) NOT NULL,
	[accuracy] [real] NULL,
	[speed] [real] NOT NULL,
	[speedaccuracy] [real] NULL,
	[altitude] [real] NOT NULL,
	[altitudeaccuracy] [real] NULL,
	[daypart] [smallint] NOT NULL,
	[lastupdated] [datetime2](0) NULL
) ON [rangePS]([daypart])
GO
/****** Object:  Table [dbo].[old_userevents_bluetooth]    Script Date: 5/27/2020 2:03:39 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[old_userevents_bluetooth](
	[uuid] [varchar](36) NOT NULL,
	[paireddeviceid] [varchar](36) NULL,
	[pairedtime] [datetime2](0) NOT NULL,
	[rssi] [int] NULL,
	[txpower] [int] NULL,
	[daypart] [smallint] NOT NULL,
	[lastupdated] [datetime2](0) NULL
) ON [rangePS]([daypart])
GO
/****** Object:  Table [dbo].[sysdiagrams]    Script Date: 5/27/2020 2:03:39 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[sysdiagrams](
	[name] [sysname] NOT NULL,
	[principal_id] [int] NOT NULL,
	[diagram_id] [int] IDENTITY(1,1) NOT NULL,
	[version] [int] NULL,
	[definition] [varbinary](max) NULL,
PRIMARY KEY CLUSTERED 
(
	[diagram_id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UK_principal_name] UNIQUE NONCLUSTERED 
(
	[principal_id] ASC,
	[name] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[uuid_activity]    Script Date: 5/27/2020 2:03:39 PM ******/
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
/****** Object:  Table [dbo].[uuid_id]    Script Date: 5/27/2020 2:03:39 PM ******/
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
ALTER TABLE [dbo].[old_userdata] ADD  DEFAULT (CONVERT([datetime2](0),getdate())) FOR [createtime]
GO
ALTER TABLE [dbo].[old_userevents] ADD  DEFAULT ((0)) FOR [accuracy]
GO
ALTER TABLE [dbo].[old_userevents] ADD  DEFAULT ((0)) FOR [speedaccuracy]
GO
ALTER TABLE [dbo].[old_userevents] ADD  DEFAULT ((0)) FOR [altitudeaccuracy]
GO
ALTER TABLE [dbo].[old_userevents] ADD  DEFAULT (getdate()) FOR [lastupdated]
GO
ALTER TABLE [dbo].[old_userevents_bluetooth] ADD  DEFAULT (getdate()) FOR [lastupdated]
GO
