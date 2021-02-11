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
and filepath like '%0' + cast(@partition as char(1)) + '.json%'
group by daypart;

while @year <= @maxyear begin
while @month <= iif(@year = @maxyear,@maxmonth,12) begin
while @day <= iif(@month=@maxmonth,@maxday,31) begin
while @hour <= iif(@day = @maxday,@maxhour,23) begin
	while @minute < 60 begin
	--	while @partition < 4 begin
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
							exec('SELECT distinct imp.uuid,imp.platform,imp.osversion,imp.appversion,imp.model,imp.ev,''' + @daypart +''',''' + @hour +''',''' + @path + ''' FROM OPENROWSET(BULK ''iot-smittestopp-prod-json/' + @path + ''', DATA_SOURCE = ''stsmittestoppprodsrc'', SINGLE_CLOB) AS DataFile
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
			--select @partition = @partition + 1, @copy = 0
		--end
		--select @minute = @minute + 1, @partition = 0
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

grant execute on adlsimporter to [FHI-Smittestopp-Sqlimport-Prod]



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
and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%d%')
and cast(filepath as char(13)) = @path;
		
insert into uuid_id(uuid)
select distinct js.paireddeviceid from dluserdatastaging with(nolock) 
cross apply openjson(ev)
	with (paireddeviceid varchar(36) '$.deviceId'
	) as js
where js.paireddeviceid not in (select uuid from uuid_id)
and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%d%')
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
	and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%d%')
	and cast(filepath as char(13)) = @path
)
insert into btevents (id,pairedtime,rssi,txpower,daypart,pairedid)
select u1.id, bt.pairedtime, bt.rssi, bt.txpower,datepart(dayofyear,pairedtime) as daypart, u2.id
from btextract bt 
join uuid_id u1 on bt.uuid = u1.uuid 
join uuid_id u2 on bt.paireddeviceid = u2.uuid
where bt.pairedtime between dateadd(day,-30,getdate()) and @maxdate
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
	and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%d%')
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
SELECT distinct uuid, timefrom, timeto, latitude, longitude, accuracy, speed, isnull(speedaccuracy,0) as speedaccuracy, altitude, altitudeaccuracy, daypart, min(lastupdated) as lastupdated
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
select uuid, timefrom, timeto, latitude, longitude, accuracy, speed, isnull(speedaccuracy,0), altitude, altitudeaccuracy, daypart, lastupdated from userevents_dupes;
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




create procedure deDuplicatorGPS (@daypart int)
as
set nocount on;
declare @hr int = 0, @count int;
-- Put the duplicates into a holding table
while @hr < 24 begin
	SELECT distinct id, timefrom, timeto, latitude, longitude, accuracy, speed, speedaccuracy, altitude, altitudeaccuracy, daypart
	into gpsevents_dupes
	FROM gpsevents
	where daypart = @daypart
	and datepart(hour,timeto) = @hr
	GROUP BY id, timefrom, timeto, latitude, longitude, accuracy, speed, speedaccuracy, altitude, altitudeaccuracy, daypart
	HAVING count(*) > 1;

	select @count = count(*) from gpsevents_dupes;

	print 'Hour=' + cast(@hr as varchar(20)) + ', count=' + cast(@count as varchar(20))

	-- Delete duplicates from orig table joined to holding table
	DELETE t
	FROM gpsevents t join gpsevents_dupes t2
	on t.id = t2.id 
		and t.timefrom = t2.timefrom
		and t.timeto = t2.timeto
		and t.latitude = t2.latitude
		and t.longitude = t2.longitude
		and t.accuracy = t2.accuracy
		and t.speed = t2.speed
		and t.speedaccuracy = t2.speedaccuracy
		and t.altitude = t2.altitude
		and t.altitudeaccuracy = t2.altitudeaccuracy
		and t.daypart = t2.daypart;

	-- Put back just the unique rows from holding table
	insert into gpsevents(id, timefrom, timeto, latitude, longitude, accuracy, speed, speedaccuracy, altitude, altitudeaccuracy, daypart)
	select id, timefrom, timeto, latitude, longitude, accuracy, speed, speedaccuracy, altitude, altitudeaccuracy, daypart from gpsevents_dupes;
	-- Drop holding table
	drop table gpsevents_dupes;

	set @hr = @hr + 1 
end




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




create procedure deFrequencyFierBT (@daypart int)
as
set nocount on;
declare @hr int = 0;
declare @count int;

while @hr < 24 begin
	with highfreqs as (
		select distinct id, pairedid, cast(pairedtime as varchar(18)) as smalltime, min(pairedtime) as mintime
		from btevents
		where daypart = @daypart
		and datepart(hh,pairedtime) = @hr
		group by id, pairedid, cast(pairedtime as varchar(18))
		having COUNT(*) > 2
	)
	select distinct u.id, pairedtime,rssi, txpower,daypart,u.pairedid
	into btevents_highfreq
	from btevents u
		join highfreqs h on u.id = h.id 
		and u.pairedid = h.pairedid
		and u.pairedtime = h.mintime
		and daypart = @daypart;

	select @count = count(*) from btevents_highfreq;
	print 'Hour=' + cast(@hr as varchar(2)) + ', Count=' + cast(@count as varchar(50))

	--begin tran
		DELETE t
		FROM btevents t join btevents_highfreq t2
		on t.id = t2.id 
			and t.pairedid = t2.pairedid 
			and cast(t.pairedtime as varchar(18)) = cast(t2.pairedtime as varchar(18))
			and t.daypart = @daypart;

		-- Put back just the unique rows from holding table
		insert into btevents (id, pairedtime,rssi, txpower,daypart,pairedid)
		select h.id, h.pairedtime,h.rssi, h.txpower,h.daypart,h.pairedid from btevents_highfreq h
	--commit tran

	-- Drop holding table
	drop table btevents_highfreq;	

	set @hr = @hr + 1
end




create procedure delete30days
as
truncate table dluserdatastaging with (partitions(datepart(dayofyear,(dateadd(dayofyear,-31,getdate())))));
truncate table btevents with (partitions(datepart(dayofyear,(dateadd(dayofyear,-31,getdate())))));
truncate table gpsevents with (partitions(datepart(dayofyear,(dateadd(dayofyear,-31,getdate())))));
delete from uuid_id where uuid not in (select uuid from dluserdatastaging with(nolock))
and id not in (select pairedid from btevents with(nolock));
delete from uuid_activity where id not in (select id from uuid_id with(nolock));



create proc deletedatafordeleteduuids
as
delete from dluserdatastaging where uuid not in (select uuid from uuid_id with(nolock)) 
	and daypart < (datepart(dayofyear,getdate())-1);
delete from btevents where id not in (select id from uuid_id with(nolock)) and daypart < (datepart(dayofyear,getdate())-1);
delete from gpsevents where id not in (select id from uuid_id with(nolock)) and daypart < (datepart(dayofyear,getdate())-1);
delete from agg_gpsevents where id not in (select id from uuid_id with(nolock)) and daypart < (datepart(dayofyear,getdate())-1);
/*
REMEMBER TO RE-RUN THE PERMISSIONS GRANT STATEMETNS WHEN MAKING CHANGES
-- run at 3 AM

exec deleteforUUID N'4e3b995e80a84c4faa01fe731af0fb11'
select * from uuid_activity a join uuid_id u on a.id = u.id and u.uuid ='4e3b995e80a84c4faa01fe731af0fb11'
select * from uuid_id where uuid = '4e3b995e80a84c4faa01fe731af0fb11'
*/


create procedure deleteforUUID (
	@uuid nvarchar(36))
as
	delete a from uuid_activity a join uuid_id u on a.id = u.id and u.uuid = @uuid; 
	delete from uuid_id where uuid = @uuid;
/*
REMEMBER TO RE-RUN THE PERMISSIONS GRANT STATEMETNS WHEN MAKING CHANGES
*/


create procedure getdatabyUUIDList(
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



create procedure getLastActivityBefore(
	@earliestdate datetime2(0))
as
select uuid, lastactivity from uuid_activity 
	join uuid_id on uuid_activity.id = uuid_id.id
where lastactivity < @earliestdate
order by lastactivity asc
;



create procedure gpsevents_aggregator (@daypart int)
as

declare @hr int = 0;
declare @count int;

while @hr < 24 begin
	with highfreqs as (
		select id, 
		cast(timeto as varchar(18)) as smalltime, min(timeto) as mintime
		from gpsevents with(nolock)
		where gpsevents.daypart = @daypart and datepart(hh,timeto) = @hr
			and latitude between -90 and 90 and longitude between -180 and 180
		group by id, cast(timeto as varchar(18))
	)
	insert into agg_gpsevents
	select distinct u.id, 
		timefrom,
		timeto,
		round(latitude,2) as latitude,
		round(longitude,2) as longitude,
		round(accuracy,0) as accuracy,
		round(speed,0) as speed,
		daypart
	from gpsevents u with(nolock)
		join highfreqs h on u.id = h.id 
		and u.timeto = h.mintime
		and daypart = @daypart;

	select @count = count(*) from agg_gpsevents with(nolock);
	print 'Hour=' + cast(@hr as varchar(2)) + ', Count=' + cast(@count as varchar(50))

	set @hr = @hr + 1
end


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
			and (appversion not like '0.1.0%' and appversion not like '1.0.0%' and appversion not like '%d%')
			and cast(filepath as char(13)) = @path
		)
		insert into gpsevents (id,timefrom,timeto,latitude,longitude,accuracy,speed,speedaccuracy,altitude,altitudeaccuracy,daypart)
		select u.id,e.timefrom,
			e.timeto as timeto,
			e.latitude,e.longitude,e.accuracy,e.speed,e.speedaccuracy,e.altitude,e.altitudeaccuracy,datepart(dayofyear,e.timeto) as daypart
		from gpsextract e 
		join uuid_id u on e.uuid = u.uuid
					where timeto between dateadd(day,-30,@maxdate) and @maxdate
			and timefrom between dateadd(day,-30,@maxdate) and @maxdate
			-- and (e.latitude between -90 and 90) and (e.longitude between -180 and 180)
		



create proc latestActivityForUUID (@uuid varchar(36))
as
select uuid, lastactivity from uuid_activity 
	join uuid_id on uuid_activity.id = uuid_id.id
where uuid_id.uuid = @uuid
order by lastactivity asc
;



create proc updatemonitors
as
insert into mon.usermonitor
select cast(getdate() as datetime2(0)) as currenttime, 
	a.platform, 
	count(distinct uuid) users 
from (select platform,uuid from dluserdatastaging with(nolock)) as a
group by platform

						       
						       
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
				       
		
						       
						       
