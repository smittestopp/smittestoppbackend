/*

Smittestopp procedures:

*/


create proc adlsimporter(
	@partitionid tinyint
	)
as
set nocount on
declare @year int, @month tinyint, @day tinyint, @hour tinyint, @minute tinyint, @partition tinyint, @copy tinyint, @daypart tinyint;
declare @maxyear int, @maxmonth tinyint, @maxday tinyint, @maxhour tinyint;
declare @path nvarchar(2000), @errormsg nvarchar(2000);
-- Set initial variable values
select @minute = 0, @partition = @partitionid, @copy = 0;

-- Set the loop breaks to two hours ago
select @maxyear = datepart(year,dateadd(hh,-2,getdate())),
	@maxmonth = datepart(month,dateadd(hh,-2,getdate())),
	@maxday = datepart(day,dateadd(hh,-2,getdate())),
	@maxhour = datepart(hour,dateadd(hh,-2,getdate()))

-- find the latest processed day and hour in the db
select @year = datepart(year,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))), 
@month = datepart(month,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))),
@day = datepart(day,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))),
@hour = max(hourpart)+1 from dluserdatastaging with(nolock) -- max hour plus one gives us the new hour
where daypart in (select max(daypart) from dluserdatastaging with(nolock))
--and filepath like '%0' + cast(@partition as char(1)) + '.json%'
group by daypart;

while @year <= @maxyear begin
while @month <= iif(@year = @maxyear,@maxmonth,12) begin
while @day <= iif(@month=@maxmonth,@maxday,31) begin
while @hour <= iif(@day = @maxday,@maxhour,23) begin
	while @minute < 60 begin
			while @copy < 20 begin
				set @path = ''+
						cast(@year as varchar(4))
						+'/'+
						case when len(cast(@month as varchar(2)))=1 then '0'+cast(@month as varchar(2)) else cast(@month as varchar(2)) end
						+'/'+
						case when len(cast(@day as varchar(2)))=1 then '0'+cast(@day as varchar(2)) else cast(@day as varchar(2)) end
						+'/'+
						case when len(cast(@hour as varchar(2)))=1 then '0'+cast(@hour as varchar(2)) else cast(@hour as varchar(2)) end
						+'/'+
						cast(@year as varchar(4))
						+'-'+
						case when len(cast(@month as varchar(2)))=1 then '0'+cast(@month as varchar(2)) else cast(@month as varchar(2)) end
						+'-'+
						case when len(cast(@day as varchar(2)))=1 then '0'+cast(@day as varchar(2)) else cast(@day as varchar(2)) end
						+'.'+
						case when len(cast(@hour as varchar(2)))=1 then '0'+cast(@hour as varchar(2)) else cast(@hour as varchar(2)) end
						+'-'+
						case when len(cast(@minute as varchar(2)))=1 then '0'+cast(@minute as varchar(2)) else cast(@minute as varchar(2)) end
						+'.'+
						case when len(cast(@partition as varchar(2)))=1 then '0'+cast(@partition as varchar(2)) else cast(@partition as varchar(2)) end
						+'.json'+
						case when @copy = 0 then '' else '-' + cast(@copy as varchar(1)) end;

						begin try	
							set @daypart = datepart(dayofyear,cast(left(@path,10) as datetime))
							--print @path
							--print @daypart
							--print @hour
							insert into dluserdatastaging (uuid,platform,osversion,appversion,model,ev,daypart,hourpart,filepath)
							exec('SELECT distinct imp.uuid,imp.platform,imp.osversion,imp.appversion,imp.model,imp.ev,''' + @daypart +''',''' + @hour +''',''' + @path + ''' FROM OPENROWSET(BULK ''iot-smittestopp-dev-json/' + @path + ''', DATA_SOURCE = ''stsmittestoppdevsrc'', SINGLE_CLOB) AS DataFile
							cross apply openjson(''['' + replace(replace(bulkcolumn,''}}
{'',''}},{''),''}}
{'',''}},{'') +'']'') WITH (uuid   varchar(36)   ''$.SystemProperties.connectionDeviceId'',
								platform varchar(100)	''$.Body.platform'',
								osversion varchar(100)	''$.Body.osVersion'',
								appversion varchar(100)	''$.Body.appVersion'',
								model varchar(100)	''$.Body.model'',
								ev nvarchar(max) N''$.Body.events'' as JSON
							 ) as imp')
							 
						end try
						begin catch
							if @@ERROR = 4860 begin -- No problem, just no file and move to next
								set @copy = 20
							end 
							else begin
								--set @errormsg = 'Something went wrong with file ' + @path;
								declare @ErrorMessage nvarchar(max), @ErrorSeverity int, @ErrorState int;
								select @ErrorMessage = 'Something went wrong with file ' + @path + '. SQL Error: '+ ERROR_MESSAGE() + ' Line ' + cast(ERROR_LINE() as nvarchar(5)), @ErrorSeverity = ERROR_SEVERITY(), @ErrorState = ERROR_STATE();
								raiserror (@ErrorMessage, @ErrorSeverity, @ErrorState);
							end
						end catch

				set @copy = @copy + 1
			end
		select @minute = @minute + 1, @copy = 0
	end
	select @hour = @hour + 1, @minute=0
end
select @day = @day + 1, @hour = 0
end
select @month = @month + 1, @day = 1
end
select @year = @year + 1, @month = 1
end


CREATE PROCEDURE dbo.applogfetch
	 @phonenumber nvarchar(20),
	 @personorrole nvarchar(200) = null,
     @personid nvarchar(200) = null,
     @personorg nvarchar(200) = null,
	 @organization nvarchar(200) = null,
  @PageNumber INT = 1,
  @PageSize   INT = 100
AS
BEGIN
  SET NOCOUNT ON;
 SELECT cast(timest as date) as timest, phonenumber, personorrole, personid, personorg, organization,legalmeans,count(*) as groupcount, count(*) over (partition by NULL) as total
    FROM dbo.applog
	where phonenumber = @phonenumber and (personorrole <> @personorrole or personid <> @personid or personorg <> @personorg or organization <> @organization)
	group by cast(timest as date), phonenumber, personorrole,personid, personorg, organization,legalmeans
    ORDER BY timest
    OFFSET @PageSize * (@PageNumber - 1) ROWS
    FETCH NEXT @PageSize ROWS ONLY OPTION (RECOMPILE);
END



CREATE PROCEDURE dbo.applogInsert(
	@timest datetime, 
	@phonenumber nvarchar(20), 
	@personorrole nvarchar(200), 
	@personid nvarchar(200),
	@personorg nvarchar(200),
	@organization nvarchar(200), 
	@legameans nvarchar(200)
)
as
	insert into applog
	select @timest, @phonenumber, @personorrole, @organization, @legameans, @personid, @personorg
;



create proc btimporter
as

set nocount on
declare @year int, @month tinyint, @day tinyint, @hour tinyint, @daypart tinyint;
declare @path nvarchar(2000), @maxdate datetime, @maxyear int;


select @maxyear = datepart(year,dateadd(hh,-1,getdate()))

-- find the latest processed day and hour in the db
select @year = datepart(year,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))), 
@month = datepart(month,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))),
@day = datepart(day,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))),
@hour = max(hourpart) from dluserdatastaging with(nolock) -- max hour plus one gives us the new hour
where daypart in (select max(daypart) from dluserdatastaging with(nolock))
group by daypart;

set @path = ''+
		cast(@year as varchar(4))
		+'/'+
		case when len(cast(@month as varchar(2)))=1 then '0'+cast(@month as varchar(2)) else cast(@month as varchar(2)) end
		+'/'+
		case when len(cast(@day as varchar(2)))=1 then '0'+cast(@day as varchar(2)) else cast(@day as varchar(2)) end
		+'/'+
		case when len(cast(@hour as varchar(2)))=1 then '0'+cast(@hour as varchar(2)) else cast(@hour as varchar(2)) end;
	set @maxdate = dateadd(hour,12,cast(cast(@path as char(10)) + ' ' + case when len(cast(@hour as varchar(2)))=1 then '0'+cast(@hour as varchar(2)) else cast(@hour as varchar(2)) end + ':00' as datetime2(0)));
	--print @maxdate
	--print @path

insert into uuid_id(uuid)
select distinct uuid from dluserdatastaging with(nolock) 
where uuid not in (select uuid from uuid_id)
--and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%.d%')
and cast(filepath as char(13)) = @path;
		
insert into uuid_id(uuid)
select distinct js.paireddeviceid from dluserdatastaging with(nolock) 
cross apply openjson(ev)
	with (paireddeviceid varchar(36) '$.deviceId'
	) as js
where js.paireddeviceid not in (select uuid from uuid_id)
--and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%.d%')
and cast(filepath as char(13)) = @path;

with btextract as (
	select uuid,js.paireddeviceid as paireddeviceid, 
		isnull(try_cast(js.pairedtime as datetime2(0)),'1900-01-01') as pairedtime, 
		js.rssi as rssi, isnull(js.txpower,0) as txpower
	from dluserdatastaging with(nolock)
	cross apply openjson(ev)
	with (paireddeviceid varchar(36) '$.deviceId',
		pairedtime varchar(20) '$.time',
		rssi smallint '$.rssi',
		txpower smallint '$.txPower'
	) as js
	where paireddeviceid is not null and paireddeviceid <> ''
	--and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%.d%')
	and cast(filepath as char(13)) = @path
)
insert into btevents (id,pairedtime,rssi,txpower,daypart,pairedid)
select u1.id, bt.pairedtime, bt.rssi, bt.txpower,datepart(dayofyear,pairedtime) as daypart, u2.id
from btextract bt 
join uuid_id u1 on bt.uuid = u1.uuid 
join uuid_id u2 on bt.paireddeviceid = u2.uuid
--where bt.pairedtime between '2020-04-16 12:00:00' and @maxdate
--option (maxdop 32)
;

MERGE INTO uuid_activity AS Target  
USING (
	select id, max(
		DATETIMEFROMPARTS(
		substring(filepath,1,4),--yy
		substring(filepath,6,2),--mm
		substring(filepath,9,2),--dd
		substring(filepath,12,2),--hh
		substring(filepath,26,2),--mm
		substring(filepath,29,2), 0)--ss, ms
	)
	from dluserdatastaging with(nolock)
	join uuid_id on dluserdatastaging.uuid = uuid_id.uuid
	where cast(filepath as char(13)) = @path
	--and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%.d%')
	group by id
	)  
       AS Source (id, lastactivity)  
ON Target.id  = Source.id  
WHEN MATCHED THEN  
	UPDATE SET lastactivity = Source.lastactivity  
WHEN NOT MATCHED BY TARGET THEN  
INSERT (id, lastactivity) VALUES (id, lastactivity); 



create proc deDuplicateTimefrom
as
with highfreqs as (
	select distinct uuid,timefrom, max(lastupdated) as lastupdated
	from userevents
	group by uuid, timefrom
	having COUNT(*) > 1 
)
select distinct u.*
into userevents_DuplicateTimefrom
from userevents u
	join highfreqs h on u.uuid = h.uuid 
	and u.timefrom = h.timefrom
	and u.lastupdated = h.lastupdated
	and u.daypart = datepart(dayofyear,h.timefrom)
-- select * from userevents_DuplicateTimefrom
DELETE t
FROM userevents t join userevents_DuplicateTimefrom t2
on t.uuid = t2.uuid 
	and t.timefrom = t2.timefrom
	and t.daypart = t2.daypart;

-- Put back just the unique rows from holding table
insert into userevents
select uuid, timefrom, timeto, latitude, longitude, accuracy, speed, speedaccuracy, altitude, altitudeaccuracy, daypart,lastupdated from userevents_DuplicateTimefrom;
-- Drop holding table
drop table userevents_DuplicateTimefrom;



create procedure deDuplicator
as
-- Put the duplicates into a holding table
SELECT uuid, timefrom, timeto, latitude, longitude, accuracy, speed, isnull(speedaccuracy,0) as speedaccuracy, altitude, altitudeaccuracy, daypart, min(lastupdated) as lastupdated
into userevents_dupes
FROM userevents
GROUP BY uuid, timefrom, timeto, latitude, longitude, accuracy, speed, isnull(speedaccuracy,0), altitude, altitudeaccuracy, daypart, lastupdated
HAVING count(*) > 1;
-- Delete duplicates from orig table joined to holding table
DELETE t
FROM userevents t join userevents_dupes t2
on t.uuid = t2.uuid 
	and t.timefrom = t2.timefrom
	and t.timeto = t2.timeto
	and t.latitude = t2.latitude
	and t.longitude = t2.longitude
	and t.accuracy = t2.accuracy
	and t.speed = t2.speed
	and isnull(t.speedaccuracy,0) = t2.speedaccuracy
	and t.altitude = t2.altitude
	and t.altitudeaccuracy = t2.altitudeaccuracy
	and t.daypart = t2.daypart;

-- Put back just the unique rows from holding table
insert into userevents
select uuid, timefrom, timeto, latitude, longitude, accuracy, speed, isnull(t.speedaccuracy,0), altitude, altitudeaccuracy, daypart, lastupdated from userevents_dupes;
-- Drop holding table
drop table userevents_dupes;

-- Some process for userevents_bluetooth
SELECT uuid, paireddeviceid, pairedtime, isnull(rssi,0) as rssi, isnull(txpower,0) as txpower, daypart, min(lastupdated) as lastupdated
into userevents_bluetooth_dupes
FROM userevents_bluetooth
GROUP BY uuid, paireddeviceid, pairedtime, isnull(rssi,0), isnull(txpower,0), daypart
HAVING count(*) > 1
--
DELETE t
FROM userevents_bluetooth t join userevents_bluetooth_dupes t2
on t.uuid = t2.uuid 
	and t.paireddeviceid = t2.paireddeviceid
	and t.pairedtime = t2.pairedtime
	and isnull(t.rssi,0) = t2.rssi
	and isnull(t.txpower,0) = t2.txpower
	and t.daypart = t2.daypart;
--
insert into userevents_bluetooth
select uuid, paireddeviceid, pairedtime, rssi, txpower, daypart, lastupdated from userevents_bluetooth_dupes;
--
drop table userevents_bluetooth_dupes;
-- 
with dupes as (
	select uuid, platform, osversion, appversion, model, count(*) as cnt
	from userdata
	group by uuid, platform, osversion, appversion, model
	having count(*) > 1
)
select distinct u.uuid, u.platform, u.osversion, u.appversion, u.model, min(u.createtime) as createtime
into userdata_dupes
from userdata u
join dupes d on u.uuid = d.uuid
	and u.platform = d.platform
	and u.osversion = d.osversion
	and u.appversion = d.appversion
	and u.model = d.model
group by u.uuid, u.platform, u.osversion, u.appversion, u.model;
--
DELETE t
FROM userdata t join userdata_dupes t2
on t.uuid = t2.uuid 
	and t.platform = t2.platform
	and t.osversion = t2.osversion
	and t.appversion = t2.appversion
	and t.model = t2.model;
--
begin tran;
	DISABLE TRIGGER userdata_insert ON userdata; 
		insert into userdata
		select uuid, platform, osversion, appversion, model, createtime from userdata_dupes;
	enable trigger userdata_insert on userdata;
commit tran;
--
drop table userdata_dupes;



create procedure deFrequencyFier
as
with highfreqs as (
	select distinct uuid, cast(timeto as varchar(18)) as smalltime, min(timeto) as mintime
	from userevents
	group by uuid, cast(timeto as varchar(18))
	having COUNT(*) > 1 
)
select distinct u.*
into userevents_highfreq
from userevents u
	join highfreqs h on u.uuid = h.uuid 
	and u.timeto = h.mintime
	and daypart = datepart(dayofyear,h.mintime)

DELETE t
FROM userevents t join userevents_highfreq t2
on t.uuid = t2.uuid 
	and cast(t.timeto as varchar(18)) = cast(t2.timeto as varchar(18))
	and t.daypart = t2.daypart;

-- Put back just the unique rows from holding table
insert into userevents
select uuid, timefrom, timeto, latitude, longitude, accuracy, speed, speedaccuracy, altitude, altitudeaccuracy, daypart,lastupdated from userevents_highfreq;
-- Drop holding table
drop table userevents_highfreq;



create procedure delete30days
as
truncate table userevents with (partitions(datepart(dayofyear,(dateadd(dayofyear,-31,getdate())))))
truncate table userevents_bluetooth with (partitions(datepart(dayofyear,(dateadd(dayofyear,-31,getdate()))))) 
delete from userdata where datepart(dayofyear,createtime) = datepart(dayofyear,(dateadd(dayofyear,-31,getdate())))



create procedure deleteforUUID (
	@uuid varchar(36))
as
delete from userevents where uuid = @uuid
delete from userevents_bluetooth where uuid = @uuid
delete from userdata where uuid = @uuid
/*
REMEMBER TO RE-RUN THE PERMISSIONS GRANT STATEMETNS WHEN MAKING CHANGES
*/



CREATE procedure [dbo].[getdatabyUUIDList](
	@uuidlist nvarchar(4000), -- commaseparated list of uuids without quotation marks or spaces e.g. 'uuid,uuid'
	@timefrom datetime2(0),
	@timeto datetime2(0),
	@PageNumber INT = 1,
	@PageSize   INT = 100
)
as
declare @cleanstr nvarchar(4000);
set @cleanstr = dbo.RemoveNonASCII(@uuidlist);
select distinct --u.uuid,
platform, osversion, appversion, model,timefrom,timeto, latitude, longitude,
				accuracy, speed, speedaccuracy, altitude, altitudeaccuracy,
				count(*) over (partition by null order by u.uuid) as totalevents
			from uuid_id u with(nolock)
			cross apply (select platform, osversion, max(appversion) as appversion, model from dluserdatastaging a with(nolock) where uuid = u.uuid
				group by platform, osversion,model) t
			join gpsevents with(nolock) on u.id = gpsevents.id
			where (timefrom between @timefrom and @timeto or timeto between @timefrom and @timeto)
		and u.uuid IN (SELECT * FROM dbo.CSVToTable(@uuidlist))
ORDER BY timefrom desc
OFFSET @PageSize * (@PageNumber - 1) ROWS
FETCH NEXT @PageSize ROWS ONLY OPTION (RECOMPILE);
/*
REMEMBER TO RE-RUN THE PERMISSIONS GRANT STATEMETNS WHEN MAKING CHANGES
*/


CREATE procedure [dbo].[getdatabyUUIDListBackup](
	@uuidlist nvarchar(4000), -- commaseparated list of uuids without quotation marks or spaces e.g. 'uuid,uuid'
	@timefrom datetime2(0),
	@timeto datetime2(0),
	@PageNumber INT = 1,
	@PageSize   INT = 100
)
as
declare @cleanstr nvarchar(4000);
set @cleanstr = dbo.RemoveNonASCII(@uuidlist);

with maxdates as (select uuid, max(createtime) as maxdate from userdata with(nolock) -- There can be more than 1 UUID so we read the last one
	where uuid IN (SELECT * FROM dbo.CSVToTable(@uuidlist))
	group by uuid)
select a.platform, a.osversion, a.appversion, a.model, 
b. timefrom, b.timeto, b.latitude, b.longitude, b.accuracy, b.speed, b.speedaccuracy, b.altitude, b.altitudeaccuracy,
count(*) over (partition by null order by a.uuid) as totalevents
from userdata a with(nolock)
join userevents b with(nolock) on a.uuid = b.uuid
join maxdates t
on a.uuid = t.uuid
	and a.createtime = t.maxdate
where (@timefrom between timefrom and timeto or @timeto between timefrom and timeto)
		and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
		and a.uuid IN (SELECT * FROM dbo.CSVToTable(@uuidlist))
ORDER BY timefrom desc
OFFSET @PageSize * (@PageNumber - 1) ROWS
FETCH NEXT @PageSize ROWS ONLY OPTION (RECOMPILE);
/*
REMEMBER TO RE-RUN THE PERMISSIONS GRANT STATEMETNS WHEN MAKING CHANGES
*/




--CREATE PROCEDURE [dbo].[getdatabyUUIDListTopN](
CREATE PROCEDURE [dbo].[getdatabyUUIDListTopN](
	@uuidlist NVARCHAR(4000), -- comma-separated list of uuids without quotation marks or spaces e.g. 'uuid,uuid'
	@timefrom DATETIME2(0),
	@timeto DATETIME2(0),
	@N INTEGER
)
AS
SELECT TOP (@N)
platform, osversion, appversion, model,timefrom,timeto, latitude, longitude, accuracy, speed, speedaccuracy, altitude, altitudeaccuracy
FROM uuid_id u WITH(NOLOCK)
CROSS APPLY (SELECT platform, osversion, appversion, model FROM dluserdatastaging WITH(NOLOCK) WHERE uuid = u.uuid) t
JOIN gpsevents WITH(NOLOCK) ON u.id = gpsevents.id
--JOIN (SELECT value from string_split(@uuidlist,',')) AS s ON u.uuid = s.value
--JOIN dbo.CSVToTable(@uuidlist) AS c ON c.uuid = u.uuid
WHERE (timefrom BETWEEN @timefrom AND @timeto OR timeto BETWEEN @timefrom AND @timeto)
AND u.uuid IN (SELECT * FROM dbo.CSVToTable(@uuidlist))
ORDER BY timefrom DESC



create procedure getLastActivityBefore(
	@earliestdate datetime2(0))
as
select uuid, lastactivity from uuid_activity 
	join uuid_id on uuid_activity.id = uuid_id.id
where lastactivity < @earliestdate
order by lastactivity asc
;




create procedure getOtherstrajectoriesIntersectsOnly(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float = 15, -- what distance to other UUID's we are searching for
	@overlap int = 0 -- overlap in secondes to other UUID's
	)
as
set nocount on;

declare @t table (id int identity(1,1),
	otheruuid varchar(36)
);
declare @return table (uuid varchar(36),
	timefrom datetime2(0),
	timeto datetime2(0),
	latitude decimal(9,6),
	longitude decimal(9,6),
	accuracy float(24),
	speed float(24),
	distancemeters float(24),
	[m/s] float(24)
);
insert into @t
SELECT distinct b.uuid 
from userevents a
JOIN userevents b 
	ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) 
		AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude))))  
	and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
			iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
	where a.uuid = @uuid
	AND a.timefrom >= @timefrom
	AND a.timeto <= @timeto and a.uuid <> b.uuid;

select distinct t.uuid,t.timefrom,t.timeto,t.latitude,t.longitude, accuracy,speed, round(f.distancemeters,2) as distancemeters,
round((iif(f.distancemeters=0,0,isnull(f.distancemeters,0)))/((iif(t.diffsec=0,1,isnull(t.diffsec,1)))),2) as [m/s]
from (select uuid,timefrom,timeto,latitude,longitude,accuracy,speed, 
	abs(datediff(ss,
		timefrom, -- current row timefrom
		lag(timefrom) over (order by timefrom))) -- previous row timeto
			as diffsec, -- difference in sec between last position and current pos
		lag(latitude) over (order by timefrom) as prevlat,
		lag(longitude) over (order by timefrom) as prevlong
	from userevents
	where uuid in (select otheruuid from @t)
	AND timefrom >= @timefrom
	AND timeto   <= @timeto
	) as t
cross apply dbo.fnGetDistanceT(t.latitude,t.longitude,t.prevlat,t.prevlong) as f;

;




create procedure gpsevents_aggregator
as

	with highfreqs as (
		select a.id, 
		cast(a.timeto as varchar(18)) as smalltime, min(a.timeto) as mintime
		from gpsevents a with(nolock)
		left outer join agg_gpsevents ag on a.id = ag.id and cast(a.timeto as varchar(18)) = cast(ag.timeto as varchar(18))
		where ag.id is null and a.latitude between -90 and 90 and a.longitude between -180 and 180
		--and not exists (select * from agg_gpsevents where id = gpsevents.id and timefrom = gpsevents.timefrom and timeto = gpsevents.timeto)
		group by a.id, cast(a.timeto as varchar(18))
	)
	insert into agg_gpsevents
	select distinct u.id, 
		timefrom,
		timeto,
		round(latitude,2,1) as latitude,
		round(longitude,2,1) as longitude,
		b.grunnkrets_id,
		iif(round(accuracy,0)>128,128,(iif(round(accuracy,0)<0,0,round(accuracy,0)))) as accuracy,
		iif(round(speed,0)>128,128,(iif(round(speed,0)<0,0,round(speed,0)))) as speed,
		daypart
	from gpsevents u with(nolock)
	join highfreqs h on u.id = h.id 
		and u.timeto = h.mintime
		and latitude between -90 and 90 and longitude between -180 and 180
	left outer join grunnkrets b on geography::STPointFromText('POINT(' + cast(longitude as varchar(20)) + ' ' + cast(latitude as varchar(20)) + ')', 4326).STWithin(b.poly) = 1
;




create proc gpsimporter
as

set nocount on
declare @year int, @month tinyint, @day tinyint, @hour tinyint, @daypart tinyint;
declare @path nvarchar(2000), @maxdate datetime, @maxyear int;


select @maxyear = datepart(year,dateadd(hh,-1,getdate()))

-- find the latest processed day and hour in the db
select @year = datepart(year,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))), 
@month = datepart(month,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))),
@day = datepart(day,dateadd(dd,daypart-1,cast(cast(@maxyear as char(4)) as datetime))),
@hour = max(hourpart) from dluserdatastaging with(nolock) -- max hour plus one gives us the new hour
where daypart in (select max(daypart) from dluserdatastaging with(nolock))
group by daypart;

set @path = ''+
		cast(@year as varchar(4))
		+'/'+
		case when len(cast(@month as varchar(2)))=1 then '0'+cast(@month as varchar(2)) else cast(@month as varchar(2)) end
		+'/'+
		case when len(cast(@day as varchar(2)))=1 then '0'+cast(@day as varchar(2)) else cast(@day as varchar(2)) end
		+'/'+
		case when len(cast(@hour as varchar(2)))=1 then '0'+cast(@hour as varchar(2)) else cast(@hour as varchar(2)) end;
	set @maxdate = dateadd(hour,12,cast(cast(@path as char(10)) + ' ' + case when len(cast(@hour as varchar(2)))=1 then '0'+cast(@hour as varchar(2)) else cast(@hour as varchar(2)) end + ':00' as datetime2(0)));
	--print @maxdate
	--print @path
	with gpsextract as (
			select uuid,
				isnull(try_cast(js.timefrom as datetime2(0)),'1900-01-01') as timefrom,
				isnull(try_cast(js.timeto as datetime2(0)),'1900-01-01') as timeto, 
				isnull(try_cast(js.latitude as decimal(9,5)),0) as latitude, 
				isnull(try_cast(js.longitude as decimal(9,5)),0) as longitude, 
				isnull(round(try_cast(js.accuracy as float(24)),3),0) as accuracy, 
				isnull(round(try_cast(js.speed as float(24)),3),0) as speed, 
				isnull(round(try_cast(js.speedaccuracy as float(24)),1),0) as speedaccuracy, 
				isnull(round(try_cast(js.altitude as float(24)),1),0) as altitude, 
				isnull(round(try_cast(js.altitudeaccuracy as float(24)),1),0) as altitudeaccuracy
			from dluserdatastaging with(nolock)
			cross apply openjson(ev)
			with (timeto varchar(20) '$.timeTo',
				timefrom varchar(20) '$.timeFrom',
				latitude varchar(20) '$.latitude',
				longitude varchar(20) '$.longitude',
				accuracy float(24) '$.accuracy',
				speed float(24) '$.speed',
				speedaccuracy float(24) '$.speedAccuracy',
				altitude float(24) '$.altitude',
				altitudeaccuracy float(24) '$.altitudeAccuracy'
			) as js
			where latitude is not null and latitude <> ''
			--and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%.d%')
			and cast(filepath as char(13)) = @path
		)
		insert into gpsevents (id,timefrom,timeto,latitude,longitude,accuracy,speed,speedaccuracy,altitude,altitudeaccuracy,daypart)
		select u.id,e.timefrom,
			e.timeto as timeto,
			e.latitude,e.longitude,e.accuracy,e.speed,e.speedaccuracy,e.altitude,e.altitudeaccuracy,datepart(dayofyear,e.timeto) as daypart
		from gpsextract e 
		join uuid_id u on e.uuid = u.uuid
					--where timeto between '2020-04-16 12:00:00' and @maxdate
			--and timefrom between '2020-04-16 12:00:00' and @maxdate
		
		
		
		
create proc latestActivityForUUID (@uuid varchar(36))
as
select max(a.lastupdated) as lastupdated from (
	select top 1 lastupdated from userevents with(nolock) where uuid = @uuid order by lastupdated desc
	union
	select top 1 lastupdated from userevents_bluetooth with(nolock) where uuid = @uuid order by lastupdated desc
) as a;




CREATE PROCEDURE dbo.sp_alterdiagram
	(
		@diagramname 	sysname,
		@owner_id	int	= null,
		@version 	int,
		@definition 	varbinary(max)
	)
	WITH EXECUTE AS 'dbo'
	AS
	BEGIN
		set nocount on
	
		declare @theId 			int
		declare @retval 		int
		declare @IsDbo 			int
		
		declare @UIDFound 		int
		declare @DiagId			int
		declare @ShouldChangeUID	int
	
		if(@diagramname is null)
		begin
			RAISERROR ('Invalid ARG', 16, 1)
			return -1
		end
	
		execute as caller;
		select @theId = DATABASE_PRINCIPAL_ID();	 
		select @IsDbo = IS_MEMBER(N'db_owner'); 
		if(@owner_id is null)
			select @owner_id = @theId;
		revert;
	
		select @ShouldChangeUID = 0
		select @DiagId = diagram_id, @UIDFound = principal_id from dbo.sysdiagrams where principal_id = @owner_id and name = @diagramname 
		
		if(@DiagId IS NULL or (@IsDbo = 0 and @theId <> @UIDFound))
		begin
			RAISERROR ('Diagram does not exist or you do not have permission.', 16, 1);
			return -3
		end
	
		if(@IsDbo <> 0)
		begin
			if(@UIDFound is null or USER_NAME(@UIDFound) is null) -- invalid principal_id
			begin
				select @ShouldChangeUID = 1 ;
			end
		end

		-- update dds data			
		update dbo.sysdiagrams set definition = @definition where diagram_id = @DiagId ;

		-- change owner
		if(@ShouldChangeUID = 1)
			update dbo.sysdiagrams set principal_id = @theId where diagram_id = @DiagId ;

		-- update dds version
		if(@version is not null)
			update dbo.sysdiagrams set version = @version where diagram_id = @DiagId ;

		return 0
	END
	
	
	

CREATE PROCEDURE dbo.sp_creatediagram
	(
		@diagramname 	sysname,
		@owner_id		int	= null, 	
		@version 		int,
		@definition 	varbinary(max)
	)
	WITH EXECUTE AS 'dbo'
	AS
	BEGIN
		set nocount on
	
		declare @theId int
		declare @retval int
		declare @IsDbo	int
		declare @userName sysname
		if(@version is null or @diagramname is null)
		begin
			RAISERROR (N'E_INVALIDARG', 16, 1);
			return -1
		end
	
		execute as caller;
		select @theId = DATABASE_PRINCIPAL_ID(); 
		select @IsDbo = IS_MEMBER(N'db_owner');
		revert; 
		
		if @owner_id is null
		begin
			select @owner_id = @theId;
		end
		else
		begin
			if @theId <> @owner_id
			begin
				if @IsDbo = 0
				begin
					RAISERROR (N'E_INVALIDARG', 16, 1);
					return -1
				end
				select @theId = @owner_id
			end
		end
		-- next 2 line only for test, will be removed after define name unique
		if EXISTS(select diagram_id from dbo.sysdiagrams where principal_id = @theId and name = @diagramname)
		begin
			RAISERROR ('The name is already used.', 16, 1);
			return -2
		end
	
		insert into dbo.sysdiagrams(name, principal_id , version, definition)
				VALUES(@diagramname, @theId, @version, @definition) ;
		
		select @retval = @@IDENTITY 
		return @retval
	END
	




CREATE PROCEDURE dbo.sp_dropdiagram
	(
		@diagramname 	sysname,
		@owner_id	int	= null
	)
	WITH EXECUTE AS 'dbo'
	AS
	BEGIN
		set nocount on
		declare @theId 			int
		declare @IsDbo 			int
		
		declare @UIDFound 		int
		declare @DiagId			int
	
		if(@diagramname is null)
		begin
			RAISERROR ('Invalid value', 16, 1);
			return -1
		end
	
		EXECUTE AS CALLER;
		select @theId = DATABASE_PRINCIPAL_ID();
		select @IsDbo = IS_MEMBER(N'db_owner'); 
		if(@owner_id is null)
			select @owner_id = @theId;
		REVERT; 
		
		select @DiagId = diagram_id, @UIDFound = principal_id from dbo.sysdiagrams where principal_id = @owner_id and name = @diagramname 
		if(@DiagId IS NULL or (@IsDbo = 0 and @UIDFound <> @theId))
		begin
			RAISERROR ('Diagram does not exist or you do not have permission.', 16, 1)
			return -3
		end
	
		delete from dbo.sysdiagrams where diagram_id = @DiagId;
	
		return 0;
	END
	



CREATE PROCEDURE dbo.sp_helpdiagramdefinition
	(
		@diagramname 	sysname,
		@owner_id	int	= null 		
	)
	WITH EXECUTE AS N'dbo'
	AS
	BEGIN
		set nocount on

		declare @theId 		int
		declare @IsDbo 		int
		declare @DiagId		int
		declare @UIDFound	int
	
		if(@diagramname is null)
		begin
			RAISERROR (N'E_INVALIDARG', 16, 1);
			return -1
		end
	
		execute as caller;
		select @theId = DATABASE_PRINCIPAL_ID();
		select @IsDbo = IS_MEMBER(N'db_owner');
		if(@owner_id is null)
			select @owner_id = @theId;
		revert; 
	
		select @DiagId = diagram_id, @UIDFound = principal_id from dbo.sysdiagrams where principal_id = @owner_id and name = @diagramname;
		if(@DiagId IS NULL or (@IsDbo = 0 and @UIDFound <> @theId ))
		begin
			RAISERROR ('Diagram does not exist or you do not have permission.', 16, 1);
			return -3
		end

		select version, definition FROM dbo.sysdiagrams where diagram_id = @DiagId ; 
		return 0
	END
	



CREATE PROCEDURE dbo.sp_helpdiagrams
	(
		@diagramname sysname = NULL,
		@owner_id int = NULL
	)
	WITH EXECUTE AS N'dbo'
	AS
	BEGIN
		DECLARE @user sysname
		DECLARE @dboLogin bit
		EXECUTE AS CALLER;
			SET @user = USER_NAME();
			SET @dboLogin = CONVERT(bit,IS_MEMBER('db_owner'));
		REVERT;
		SELECT
			[Database] = DB_NAME(),
			[Name] = name,
			[ID] = diagram_id,
			[Owner] = USER_NAME(principal_id),
			[OwnerID] = principal_id
		FROM
			sysdiagrams
		WHERE
			(@dboLogin = 1 OR USER_NAME(principal_id) = @user) AND
			(@diagramname IS NULL OR name = @diagramname) AND
			(@owner_id IS NULL OR principal_id = @owner_id)
		ORDER BY
			4, 5, 1
	END
	
	
	

CREATE PROCEDURE dbo.sp_renamediagram
	(
		@diagramname 		sysname,
		@owner_id		int	= null,
		@new_diagramname	sysname
	
	)
	WITH EXECUTE AS 'dbo'
	AS
	BEGIN
		set nocount on
		declare @theId 			int
		declare @IsDbo 			int
		
		declare @UIDFound 		int
		declare @DiagId			int
		declare @DiagIdTarg		int
		declare @u_name			sysname
		if((@diagramname is null) or (@new_diagramname is null))
		begin
			RAISERROR ('Invalid value', 16, 1);
			return -1
		end
	
		EXECUTE AS CALLER;
		select @theId = DATABASE_PRINCIPAL_ID();
		select @IsDbo = IS_MEMBER(N'db_owner'); 
		if(@owner_id is null)
			select @owner_id = @theId;
		REVERT;
	
		select @u_name = USER_NAME(@owner_id)
	
		select @DiagId = diagram_id, @UIDFound = principal_id from dbo.sysdiagrams where principal_id = @owner_id and name = @diagramname 
		if(@DiagId IS NULL or (@IsDbo = 0 and @UIDFound <> @theId))
		begin
			RAISERROR ('Diagram does not exist or you do not have permission.', 16, 1)
			return -3
		end
	
		-- if((@u_name is not null) and (@new_diagramname = @diagramname))	-- nothing will change
		--	return 0;
	
		if(@u_name is null)
			select @DiagIdTarg = diagram_id from dbo.sysdiagrams where principal_id = @theId and name = @new_diagramname
		else
			select @DiagIdTarg = diagram_id from dbo.sysdiagrams where principal_id = @owner_id and name = @new_diagramname
	
		if((@DiagIdTarg is not null) and  @DiagId <> @DiagIdTarg)
		begin
			RAISERROR ('The name is already used.', 16, 1);
			return -2
		end		
	
		if(@u_name is null)
			update dbo.sysdiagrams set [name] = @new_diagramname, principal_id = @theId where diagram_id = @DiagId
		else
			update dbo.sysdiagrams set [name] = @new_diagramname where diagram_id = @DiagId
		return 0
	END
	



CREATE PROCEDURE dbo.sp_upgraddiagrams
	AS
	BEGIN
		IF OBJECT_ID(N'dbo.sysdiagrams') IS NOT NULL
			return 0;
	
		CREATE TABLE dbo.sysdiagrams
		(
			name sysname NOT NULL,
			principal_id int NOT NULL,	-- we may change it to varbinary(85)
			diagram_id int PRIMARY KEY IDENTITY,
			version int,
	
			definition varbinary(max)
			CONSTRAINT UK_principal_name UNIQUE
			(
				principal_id,
				name
			)
		);


		/* Add this if we need to have some form of extended properties for diagrams */
		/*
		IF OBJECT_ID(N'dbo.sysdiagram_properties') IS NULL
		BEGIN
			CREATE TABLE dbo.sysdiagram_properties
			(
				diagram_id int,
				name sysname,
				value varbinary(max) NOT NULL
			)
		END
		*/

		IF OBJECT_ID(N'dbo.dtproperties') IS NOT NULL
		begin
			insert into dbo.sysdiagrams
			(
				[name],
				[principal_id],
				[version],
				[definition]
			)
			select	 
				convert(sysname, dgnm.[uvalue]),
				DATABASE_PRINCIPAL_ID(N'dbo'),			-- will change to the sid of sa
				0,							-- zero for old format, dgdef.[version],
				dgdef.[lvalue]
			from dbo.[dtproperties] dgnm
				inner join dbo.[dtproperties] dggd on dggd.[property] = 'DtgSchemaGUID' and dggd.[objectid] = dgnm.[objectid]	
				inner join dbo.[dtproperties] dgdef on dgdef.[property] = 'DtgSchemaDATA' and dgdef.[objectid] = dgnm.[objectid]
				
			where dgnm.[property] = 'DtgSchemaNAME' and dggd.[uvalue] like N'_EA3E6268-D998-11CE-9454-00AA00A3F36E_' 
			return 2;
		end
		return 1;
	END
	
						       

CREATE proc [dbo].[getnewuuids](@uuid varchar(36),
	@howmany int=100)
as
	set nocount on
	declare @i int = 0, @created datetime2(0) = getdate()
	declare @t table(new_uuid char(32))

	while @i < @howmany begin
		insert into @t
		select replace(newid(),'-','')
		set @i = @i + 1
	end

	insert into uuid_rotating(uuid,new_uuid,created)
	select @uuid, new_uuid, @created
	from @t;

	select uuid, new_uuid, created
	from uuid_rotating where uuid = @uuid and created = @created
				       
				       
				       
