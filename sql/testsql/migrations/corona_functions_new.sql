﻿/*
Smittestopp Functions:
*/



drop function if exists fngetDistance
go
Create Function [dbo].[fnGetDistance](
      @Lat1 Float(18), 
      @Long1 Float(18),
      @Lat2 Float(18),
      @Long2 Float(18)
)
Returns Float(18)
AS
Begin
      Declare @R Float(8) = 6367450; -- WGS84 mean Earth radius in meters
      Declare @dLat Float(18);
      Declare @dLon Float(18);
      Declare @a Float(18);
      Declare @c Float(18);
      Declare @d Float(18);

      Set @dLat = Radians(@lat2 - @lat1);
      Set @dLon = Radians(@long2 - @long1);

      Set @a = Sin(@dLat / 2) 
                 * Sin(@dLat / 2) 
                 + Cos(Radians(@lat1))
                 * Cos(Radians(@lat2)) 
                 * Sin(@dLon / 2) 
                 * Sin(@dLon / 2);
      Set @c = 2 * Asin(Min(Sqrt(@a)));

      Set @d = @R * @c;
      Return @d;
End

go




drop function if exists fngetDistanceT
go

Create Function [dbo].fngetDistanceT(
      @LatA decimal(9,6), 
      @LongA decimal(9,6),
      @LatB decimal(9,6),
      @LongB decimal(9,6)
)
Returns table
AS
return(
	 select 12742016 * Asin(Min(Sqrt((Sin(Radians(@LatB - @LatA) / 2) -- WGS84 mean earth radius*2 = 12742016
                 * Sin(Radians(@LatB - @LatA) / 2) 
                 + Cos(Radians(@LatA))
                 * Cos(Radians(@LatB)) -- multiply Long by the cosine of the latitude radians
                 * Sin(Radians(@LongB - @LongA) / 2) 
                 * Sin(Radians(@LongB - @LongA) / 2))))) as distancemeters
);
go

drop function if exists fngetDistanceT2
go

Create Function [dbo].fngetDistanceT2(
      @LatA decimal(9,6), 
      @LongA decimal(9,6),
      @LatB decimal(9,6),
      @LongB decimal(9,6)
)
Returns table
AS
return(
	select 111045* DEGREES(ACOS(iif(1.0<=COS(RADIANS(@LatA)),1.0,COS(RADIANS(@LatA))
                 * COS(RADIANS(@LatB))
                 * COS(RADIANS(@LongA) - RADIANS(@LongB))
                 + SIN(RADIANS(@LatA))
                 * SIN(RADIANS(@LatB))))) as distancemeters
);

go



drop function if exists getTrajectory
go

create function getTrajectory(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
	SELECT --top 100 percent 
	uuid, timefrom, timeto, latitude, longitude, accuracy
	FROM   gpsevents with(nolock)
	join uuid_id on gpsevents.id = uuid_id.id
	WHERE  uuid_id.uuid = @uuid
		   AND timefrom >= @timefrom
		   AND timeto <= @timeto
		   	and daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	--order by timefrom asc -- ORDER BY is not allowed in a TVF unless there is an TOP clause
);
go



drop function if exists getTrajectorySpeed
go

create function getTrajectorySpeed(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select distinct t.uuid, t.timefrom, t.timeto, t.latitude, t.longitude, accuracy, speed,
       round(f.distancemeters,2) as distancemeters,
       round((iif(f.distancemeters=0,0,isnull(f.distancemeters,0)))/((iif(t.diffsec=0,1,isnull(t.diffsec,1)))),2) as [m/s]
from (select uuid_id.uuid, timefrom, timeto, latitude, longitude, accuracy, speed, 
	abs(datediff(ss,
		timefrom, -- current row timefrom
		lag(timefrom)  over (order by timefrom))) as diffsec, -- previous row timeto, difference in sec between previous position and current pos
		lag(latitude)  over (order by timefrom)   as prevlat,
		lag(longitude) over (order by timefrom)   as prevlong
	from gpsevents	with(nolock)
	join uuid_id with(nolock) on gpsevents.id = uuid_id.id
	WHERE  uuid_id.uuid = @uuid
	AND timefrom >= @timefrom
	AND timeto   <= @timeto
	and daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)  -- search only within the relevant "day-segments" of the table
	) as t
cross apply dbo.fnGetDistanceT(t.latitude,t.longitude,t.prevlat,t.prevlong) as f   -- calculating distance using the function above
);
go


/****** Object:  UserDefinedFunction [dbo].[getTrajectoryV2]    Script Date: 5/25/2020 1:34:15 PM ******/
drop function if exists [dbo].[getTrajectoryV2]
GO

create function [dbo].[getTrajectoryV2](
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
	SELECT top 100 percent u.uuid, timefrom, timeto, latitude, longitude, accuracy, speed
	FROM   gpsevents a with(nolock)
	join uuid_id u with(nolock) on a.id = u.id
	WHERE  u.uuid = @uuid
	       AND timefrom >= @timefrom
	       AND timeto   <= @timeto
	       AND daypart BETWEEN datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	ORDER BY timefrom asc -- ORDER BY is not allowed in a TVF unless there is an TOP clause
);
GO





drop function if exists getIntersectedTrajectories
go

create function getIntersectedTrajectories(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float = 15, -- what distance to other UUID's we are searching for
	@overlap int = 0 -- overlap in secondes to other UUID's
	)
returns table
as
return (
with filter as (
	select distinct gpsevents.id,timefrom,timeto,latitude,longitude,accuracy from gpsevents with(nolock)
		join uuid_id on gpsevents.id = uuid_id.id
	where uuid_id.uuid = @uuid
	AND timefrom >= @timefrom
	AND timeto   <= @timeto
	)
SELECT top 100 percent u1.uuid as MyUUID, 
	a.latitude as MyLocationLat,
	a.longitude as MyLocationLong,
	a.accuracy as MyAccuracy,
    u2.uuid as OtherUUID, 
	b.latitude as OtherLocationLat,
	b.longitude as OtherLocationLong,
	b.accuracy as OtherAccuracy,
	iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom) as overlapstart,
	iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) as overlapend,
    datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), 
		iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) as overlaptime,
	round(f.distancemeters,2) as dist
FROM filter a 
JOIN gpsevents b with(nolock)
	ON b.latitude BETWEEN a.latitude - (0.1 / 111.045) -- 0.1 km radius prefilter
		AND a.latitude + (0.1 / 111.045)
		and b.longitude BETWEEN a.longitude - (0.1 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (0.1 / (111.045 * COS(RADIANS(a.latitude))))  
	and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
			iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
    AND a.id <> b.id
		and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	cross apply dbo.fnGetDistanceT(a.latitude,a.longitude,b.latitude,b.longitude) f
join uuid_id u1 with(nolock) on a.id = u1.id
join uuid_id u2 with(nolock) on b.id = u2.id 
WHERE round(f.distancemeters,2) < @distance
order by iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) desc
);
go


drop function if exists getIntersectedTrajectoriesSpeed
go

create function getIntersectedTrajectoriesSpeed(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float = 15, -- what distance to other UUID's we are searching for
	@overlap int = 0 -- overlap in secondes to other UUID's
	)
returns table
as
return (
with filter as (
	select uuid,timefrom,timeto,latitude,longitude,accuracy,speed,distancemeters,[m/s] from getTrajectorySpeed(@uuid,@timefrom,@timeto)
	)
SELECT top 100 percent a.uuid as MyUUID, 
	a.latitude as MyLocationLat,
	a.longitude as MyLocationLong,
	a.accuracy as MyAccuracy,
	a.speed,
	a.distancemeters,
	a.[m/s],
	u.uuid as OtherUUID, 
	b.latitude as OtherLocationLat,
	b.longitude as OtherLocationLong,
	b.accuracy as OtherAccuracy,
	iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom) as overlapstart,
	iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) as overlapend,
    datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), 
		iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) as overlaptime,
	round(f.distancemeters,2) as dist
FROM filter a with(nolock)
JOIN gpsevents b with(nolock)
	ON b.latitude BETWEEN a.latitude - (0.1 / 111.045) -- 0.1 km radius prefilter
		AND a.latitude + (0.1 / 111.045)
		and b.longitude BETWEEN a.longitude - (0.1 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (0.1 / (111.045 * COS(RADIANS(a.latitude))))  
	and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
			iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
	and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	cross apply dbo.fnGetDistanceT(a.latitude,a.longitude,b.latitude,b.longitude) f
join uuid_id u with(nolock) on b.id = u.id AND a.uuid <> u.uuid
WHERE round(f.distancemeters,2) < @distance
order by iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) desc
);
go



drop function if exists getIntersectedTrajectories2
go

create function getIntersectedTrajectories2(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float = 15, -- what distance to other UUID's we are searching for
	@overlap int = 0 -- overlap in secondes to other UUID's
	)
returns table
as
return (
with filter as (
	select distinct u.id,timefrom,timeto,latitude,longitude,accuracy from gpsevents a with(nolock)
	join uuid_id u with(nolock) on a.id = u.id
	where u.uuid = @uuid
	AND timefrom >= @timefrom
	AND timeto   <= @timeto
	--and daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	)
SELECT top 100 percent u1.uuid as MyUUID, 
	a.latitude as MyLocationLat,
	a.longitude as MyLocationLong,
	a.accuracy as MyAccuracy,
    u2.uuid as OtherUUID, 
	b.latitude as OtherLocationLat,
	b.longitude as OtherLocationLong,
	b.accuracy as OtherAccuracy,
	iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom) as overlapstart,
	iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) as overlapend,
    datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), 
		iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) as overlaptime,
	round(dbo.fnGetDistance(a.latitude,a.longitude,b.latitude,b.longitude),2) as dist
FROM filter a with(nolock)
JOIN gpsevents b with(nolock)
	ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) 
		AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude))))  
	and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
			iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
    AND a.id <> b.id
	and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
join uuid_id u1 with(nolock) on a.id = u1.id
join uuid_id u2 with(nolock) on b.id = u2.id
order by iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) desc
);
go



drop function if exists getIntersectedTrajectoriesSpeed2
go

create function getIntersectedTrajectoriesSpeed2(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float = 15, -- what distance to other UUID's we are searching for
	@overlap int = 0 -- overlap in secondes to other UUID's
	)
returns table
as
return (
with filter as (
	select uuid,timefrom,timeto,latitude,longitude,accuracy,speed,distancemeters,[m/s] from getTrajectorySpeed(@uuid,@timefrom,@timeto)
	)
SELECT top 100 percent a.uuid as MyUUID, 
	a.latitude as MyLocationLat,
	a.longitude as MyLocationLong,
	a.accuracy as MyAccuracy,
	a.speed,
	a.distancemeters,
	a.[m/s],
    u.uuid as OtherUUID, 
	b.latitude as OtherLocationLat,
	b.longitude as OtherLocationLong,
	b.accuracy as OtherAccuracy,
	iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom) as overlapstart,
	iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) as overlapend,
    datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), 
		iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) as overlaptime,
	round(dbo.fnGetDistance(a.latitude,a.longitude,b.latitude,b.longitude),2) as dist
FROM filter a with(nolock)
JOIN gpsevents b with(nolock)
	ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) 
		AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude))))  
	and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
			iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
		and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
join uuid_id u with(nolock) on b.id = u.id AND a.uuid <> u.uuid
order by iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) desc
);
go



drop function if exists getSumIntersectedOverlaps
go

create function getSumIntersectedOverlaps(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float,
	@sumoverlaptime int = 0,
	@overlap int
	)
returns table
as
return (
with filter as (
	select distinct a.id,timefrom,timeto,latitude,longitude,accuracy from gpsevents a join uuid_id u on a.id = u.id
	where uuid = @uuid
	AND timefrom >= @timefrom
	AND timeto   <= @timeto
	)
SELECT top 100 percent u1.uuid as MyUUID, 
    u2.uuid as OtherUUID, 
	avg(dbo.fnGetDistance(a.latitude,a.longitude,b.latitude,b.longitude)) as avgdist,
	avg(a.accuracy) as avgaccuracy,
    max(datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto))) as maxoverlaptime,
    sum(datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto))) as sumoverlaptime,
	count(*) as overlapcount
FROM filter a with(nolock)
JOIN gpsevents b with(nolock)
	ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) -- radius prefilter
		AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude))))   
	and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
		iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
    AND b.id <> a.id
	and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
join uuid_id u1 with(nolock) on a.id = u1.id 
join uuid_id u2 with(nolock) on b.id = u2.id
group by u1.uuid, 
        u2.uuid
having sum(datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto))) > @sumoverlaptime
order by sumoverlaptime desc
);
go



drop function if exists getIntersectedTrajectoriesBySumoverlaptime
go

create function getIntersectedTrajectoriesBySumoverlaptime(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float,
	@sumoverlaptime int = 0,
	@overlap int
	)
returns table
as
return (
with cte1 as (
	select myuuid, otheruuid from getSumIntersectedOverlaps(@uuid,@timefrom,@timeto,@distance,@sumoverlaptime,@overlap)
)  
SELECT top 100 percent u1.uuid as MyUUID, 
	a.latitude as MyLocationLat,
	a.longitude as MyLocationLong,
	a.accuracy as MyAccuracy,
    u2.uuid as OtherUUID, 
	b.latitude as OtherLocationLat,
	b.longitude as OtherLocationLong,
	b.accuracy as OtherAccuracy,
	iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom) as overlapstart,
	iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) as overlapend,
    datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) as overlaptime,
	round(dbo.fnGetDistance(a.latitude,a.longitude,b.latitude,b.longitude),2) as dist
FROM gpsevents a with(nolock)
JOIN gpsevents b with(nolock)
	ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) -- radius prefilter
		AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
		iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
    AND a.id <> b.id
	and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
join uuid_id u1 with(nolock) on a.id = u1.id
join uuid_id u2 with(nolock) on b.id = u2.id
JOIN cte1 on u1.uuid = cte1.myuuid
	and u2.uuid = cte1.otheruuid
WHERE u1.uuid = @uuid
      AND a.timefrom >= @timefrom
      AND a.timeto   <= @timeto
order by overlapend desc
);
go


drop function if exists getIntersections
go

create function getIntersections(
	@myuuid varchar(40), 
	@otheruuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float,
	@overlap int
	)
returns table
as
return (
SELECT top 100 percent u1.uuid as MyUUID, 
	a.latitude as MyLocationLat,
	a.longitude as MyLocationLong,
	a.accuracy as MyAccuracy,
    u2.uuid as OtherUUID, 
	b.latitude as OtherLocationLat,
	b.longitude as OtherLocationLong,
	b.accuracy as OtherAccuracy,
	iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom) as overlapstart,
	iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) as overlapend,
    datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) as overlaptime,
	round(dbo.fnGetDistance(a.latitude,a.longitude,b.latitude,b.longitude),2) as dist
FROM gpsevents a with(nolock)
JOIN gpsevents b with(nolock)
	ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) 
		AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude))))   
     AND datediff(ss,iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
    AND a.id <> b.id
		and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
join uuid_id u1
	on a.id = u1.id
join uuid_id u2
	on b.id = u2.id
WHERE u1.uuid = @myuuid
	and u2.uuid = @otheruuid
      AND a.timefrom >= @timefrom
      AND a.timeto   <= @timeto
order by overlapend desc
);
go


drop function if exists getWithinPolygons
go

create function getWithinPolygons(
	@polygon varchar(4000), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select u.uuid, latitude, longitude, timefrom, timeto, accuracy
from gpsevents a with(nolock)
join uuid_id u with(nolock) on a.id = u.id
where a.timefrom >= @timefrom
      AND a.timeto   <= @timeto
      and geography::STPointFromText('POINT(' + cast(longitude as varchar(20)) + ' ' + cast(latitude as varchar(20)) + ')', 4326).STWithin(
	  geography::STPolyFromText('POLYGON((' + @polygon + '))', 4326)) = 1
      and daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
)
GO



drop function if exists getGPSWithinGrunnkrets
go

create function getGPSWithinGrunnkrets(
	@grunnkretskode char(8), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid, a.latitude, a.longitude, a.timefrom, a.timeto, a.accuracy
from gpsevents a with(nolock)
join uuid_id u with(nolock) on a.id = u.id
join agg_gpsevents ag with(nolock) on a.id = ag.id and a.timefrom = ag.timefrom and a.timeto = ag.timeto
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
where a.timefrom >= @timefrom
      AND a.timeto   <= @timeto
      and ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
      and a.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and gk.grunnkrets_kode = @grunnkretskode
)
GO

drop function if exists getGPSWithinMultipleGrunnkrets
go

create function getGPSWithinMultipleGrunnkrets(
	@grunnkretskode nvarchar(max), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid, a.latitude, a.longitude, a.timefrom, a.timeto, a.accuracy
from gpsevents a with(nolock)
join uuid_id u with(nolock) on a.id = u.id
join agg_gpsevents ag with(nolock) on a.id = ag.id and a.timefrom = ag.timefrom and a.timeto = ag.timeto
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
join (select value from string_split(@grunnkretskode,',')) as s on gk.grunnkrets_kode = s.value
where a.timefrom >= @timefrom
      AND a.timeto   <= @timeto
      and ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
      and a.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
)
GO



drop function if exists getBTWithinGrunnkrets
go

create function getBTWithinGrunnkrets(
	@grunnkretskode char(8), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid,
	ge.timefrom       AS gps_timefrom,
	ge.timeto         AS gps_timeto,
	ge.latitude       AS gps_latitude, 
	ge.longitude      AS gps_longitude,
 	ge.accuracy       AS gps_accuracy,  a.pairedtime, a.rssi, a.txpower, u2.uuid as other_uuid
from btevents a with(nolock)
join uuid_id u with(nolock) on a.id = u.id
join uuid_id u2 with(nolock) on a.pairedid = u2.id
join agg_gpsevents ag with(nolock) on a.id = ag.id and a.pairedtime between ag.timefrom and ag.timeto
join gpsevents ge with(nolock) on ag.id = ge.id and ag.timefrom = ge.timefrom and ag.timeto = ge.timeto
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
where a.pairedtime between @timefrom and @timeto
      and ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
      and a.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and gk.grunnkrets_kode = @grunnkretskode
)
GO


drop function if exists getUniqueUUIDsWithinGrunnkrets
go

create function getUniqueUUIDsWithinGrunnkrets(
	@grunnkretskode char(8), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (select count(distinct ag.id) as uuids
from agg_gpsevents ag with(nolock) 
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
where ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and gk.grunnkrets_kode = @grunnkretskode
)
GO

drop function if exists getUniqueUUIDsWithinMultipleGrunnkrets
go

create function getUniqueUUIDsWithinMultipleGrunnkrets(
	@grunnkretskode nvarchar(max), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (select count(distinct ag.id) as uuids
from agg_gpsevents ag with(nolock) 
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
join (select value from string_split(@grunnkretskode,',')) as s on gk.grunnkrets_kode = s.value
where ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
)
GO




drop function if exists getBTWithinMultipleGrunnkrets
go

create function getBTWithinMultipleGrunnkrets(
	@grunnkretskode char(8), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid,
	ge.timefrom       AS gps_timefrom,
	ge.timeto         AS gps_timeto,
	ge.latitude       AS gps_latitude, 
	ge.longitude      AS gps_longitude,
 	ge.accuracy       AS gps_accuracy, 
	a.pairedtime, a.rssi, a.txpower, u2.uuid as other_uuid
from btevents a with(nolock)
join uuid_id u with(nolock) on a.id = u.id
join uuid_id u2 with(nolock) on a.pairedid = u2.id
join agg_gpsevents ag with(nolock) on a.id = ag.id and a.pairedtime between ag.timefrom and ag.timeto
join gpsevents ge with(nolock) on ag.id = ge.id and ag.timefrom = ge.timefrom and ag.timeto = ge.timeto
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
join (select value from string_split(@grunnkretskode,',')) as s on gk.grunnkrets_kode = s.value
where a.pairedtime between @timefrom and @timeto
      and ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
      and a.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
)
GO


/****** Object:  UserDefinedFunction [dbo].[getWithinBB]    Script Date: 5/24/2020 11:15:45 PM ******/
drop function if exists getwithinBB
go

create function [dbo].[getWithinBB](
       	@longmin  decimal(9,6), 
      	@latmin   decimal(9,6),
      	@longmax  decimal(9,6),
      	@latmax   decimal(9,6),
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
	SELECT DISTINCT u.uuid , a.timefrom , a.timeto , a.latitude , a.longitude , a.accuracy, a.speed 
	FROM gpsevents a with(nolock)
	join uuid_id u with(nolock) on a.id = u.id
	join agg_gpsevents ag with(nolock) on a.id = ag.id and a.timefrom = ag.timefrom and a.timeto = ag.timeto
	WHERE ag.longitude BETWEEN @longmin and @longmax
		AND ag.latitude BETWEEN @latmin  and @latmax
		AND ag.timefrom >= @timefrom
		AND ag.timeto <= @timeto
		AND a.daypart >= datepart(dayofyear,@timefrom) 
		AND a.daypart <= datepart(dayofyear,@timeto)
		AND ag.daypart >= datepart(dayofyear,@timefrom) 
		AND ag.daypart <= datepart(dayofyear,@timeto)
)
GO

drop function if exists getUniqueUUIdswithinBB
go

create function getUniqueUUIdswithinBB(
	@longmin  decimal(9,6), 
      	@latmin   decimal(9,6),
      	@longmax  decimal(9,6),
      	@latmax   decimal(9,6),
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
	SELECT count(distinct a.id) as uuids
	FROM gpsevents a with(nolock)
	join agg_gpsevents ag with(nolock) on a.id = ag.id and a.timefrom = ag.timefrom and a.timeto = ag.timeto
	WHERE ag.longitude BETWEEN @longmin and @longmax
		AND ag.latitude BETWEEN @latmin  and @latmax
		AND ag.timefrom >= @timefrom
		AND ag.timeto <= @timeto
		AND a.daypart >= datepart(dayofyear,@timefrom) 
		AND a.daypart <= datepart(dayofyear,@timeto)
		AND ag.daypart >= datepart(dayofyear,@timefrom) 
		AND ag.daypart <= datepart(dayofyear,@timeto)
)
GO


drop function if exists [getWithinBBlist]
go

create function [dbo].[getWithinBBlist](
       	@longminA decimal(9,6), @latminA decimal(9,6), @longmaxA decimal(9,6), @latmaxA decimal(9,6), @timefromA datetime2(0), @timetoA datetime2(0),
       	@longminB decimal(9,6), @latminB decimal(9,6), @longmaxB decimal(9,6), @latmaxB decimal(9,6), @timefromB datetime2(0), @timetoB datetime2(0),
       	@longminC decimal(9,6), @latminC decimal(9,6), @longmaxC decimal(9,6), @latmaxC decimal(9,6), @timefromC datetime2(0), @timetoC datetime2(0),
       	@longminD decimal(9,6), @latminD decimal(9,6), @longmaxD decimal(9,6), @latmaxD decimal(9,6), @timefromD datetime2(0), @timetoD datetime2(0),
       	@longminE decimal(9,6), @latminE decimal(9,6), @longmaxE decimal(9,6), @latmaxE decimal(9,6), @timefromE datetime2(0), @timetoE datetime2(0)
	)
returns table
as
return (
	SELECT DISTINCT u.uuid , a.timefrom , a.timeto , a.latitude , a.longitude , a.accuracy, a.speed 
	FROM gpsevents a with(nolock)
	join uuid_id u with(nolock) on a.id = u.id
	join agg_gpsevents ag with(nolock) on a.id = ag.id and a.timefrom = ag.timefrom and a.timeto = ag.timeto
	WHERE (ag.longitude BETWEEN @longminA and @longmaxA AND ag.latitude BETWEEN @latminA and @latmaxA
		AND ag.timefrom >= @timefromA AND ag.timeto <= @timetoA
		AND ag.daypart >= datepart(dayofyear,@timefromA) AND ag.daypart <= datepart(dayofyear,@timetoA))
	      OR
	      (ag.longitude BETWEEN @longminB and @longmaxB AND ag.latitude BETWEEN @latminB and @latmaxB
		AND ag.timefrom >= @timefromB AND ag.timeto <= @timetoB
		AND ag.daypart >= datepart(dayofyear,@timefromB) AND ag.daypart <= datepart(dayofyear,@timetoB))
	      OR
	      (ag.longitude BETWEEN @longminC and @longmaxC AND ag.latitude BETWEEN @latminC and @latmaxC
		AND ag.timefrom >= @timefromC AND ag.timeto <= @timetoC
		AND ag.daypart >= datepart(dayofyear,@timefromC) AND ag.daypart <= datepart(dayofyear,@timetoC))
	      OR
	      (ag.longitude BETWEEN @longminD and @longmaxD AND ag.latitude BETWEEN @latminD and @latmaxD
		AND ag.timefrom >= @timefromD AND ag.timeto <= @timetoD
		AND ag.daypart >= datepart(dayofyear,@timefromD) AND ag.daypart <= datepart(dayofyear,@timetoD))
	      OR
	      (ag.longitude BETWEEN @longminE and @longmaxE AND ag.latitude BETWEEN @latminE and @latmaxE
		AND ag.timefrom >= @timefromE AND ag.timeto <= @timetoE
		AND ag.daypart >= datepart(dayofyear,@timefromE) AND ag.daypart <= datepart(dayofyear,@timetoE))
)
GO

/****** Object:  UserDefinedFunction [dbo].[getBTpairingsWithinBB]    Script Date: 5/25/2020 6:12:40 AM ******/
drop function if exists [dbo].[getBTpairingsWithinBB]
GO

create function [dbo].[getBTpairingsWithinBB](
       	@longmin  decimal(9,6), 
      	@latmin   decimal(9,6),
      	@longmax  decimal(9,6),
      	@latmax   decimal(9,6),
	@dateday datetime2(0),
	@timeslack_before int,
	@timeslack_after int		
	)
returns table
as
return (
with filter as 
(
	SELECT DISTINCT id , timefrom , timeto , latitude , longitude , accuracy 
	FROM agg_gpsevents with(nolock)
	WHERE daypart = datepart(dayofyear, @dateday)
	AND longitude BETWEEN @longmin and @longmax
	AND latitude  BETWEEN @latmin  and @latmax
)
SELECT top 100 percent 
	u.uuid           AS gps_uuid, 
	a0.timefrom       AS gps_timefrom,
	a0.timeto         AS gps_timeto,
	a0.latitude       AS gps_latitude, 
	a0.longitude      AS gps_longitude,
 	a0.accuracy       AS gps_accuracy, 
	u2.uuid AS by_uuid,
        b.pairedtime     AS bt_pairedtime, 
	b.rssi		 AS bt_rssi,
	b.txpower	 AS bt_txpower

FROM filter a 
join gpsevents a0 with(nolock) on a.id = a0.id and a.timefrom = a0.timefrom and a.timeto = a0.timeto
join uuid_id u with(nolock) on a.id = u.id
INNER JOIN btevents b with(nolock)
ON a.id = b.id
   AND b.daypart = datepart(dayofyear, @dateday)
   AND b.pairedtime BETWEEN dateadd(ss, @timeslack_before , a.timefrom) AND dateadd(ss , @timeslack_after , a.timeto) 
join uuid_id u2 with(nolock) on b.pairedid = u2.id
ORDER BY u.uuid, u2.uuid, a.timefrom, b.pairedtime
)
GO


/****** Object:  UserDefinedFunction [dbo].[getBTpairingsWithinPolygons]    Script Date: 5/25/2020 6:21:06 AM ******/
drop function if exists [dbo].[getBTpairingsWithinPolygons]
GO

create function [dbo].[getBTpairingsWithinPolygons](
	@polygon varchar(4000), 
	@dateday datetime2(0),
	@timeslack_before int,
	@timeslack_after int		
	)
returns table
as
return (
SELECT top 100 percent
	u.uuid           AS gps_uuid, 
	a.timefrom       AS gps_timefrom,
	a.timeto         AS gps_timeto,
	a.latitude       AS gps_latitude, 
	a.longitude      AS gps_longitude,
 	a.accuracy       AS gps_accuracy, 
	u2.uuid AS by_uuid,
        b.pairedtime     AS bt_pairedtime, 
	b.rssi		 AS bt_rssi,
	b.txpower	 AS bt_txpower
FROM agg_gpsevents ag
join gpsevents a on ag.id = a.id and ag.timefrom = a.timefrom and ag.timeto = a.timeto
join uuid_id u on a.id = u.id
INNER JOIN btevents b
ON a.id = b.id
   AND a.daypart = datepart(dayofyear, @dateday) 
   AND b.daypart = datepart(dayofyear, @dateday)
   AND b.pairedtime BETWEEN dateadd(ss, @timeslack_before , a.timefrom) AND dateadd(ss , @timeslack_after , a.timeto) 
join uuid_id u2 on b.pairedid = u2.id
WHERE geography::STPointFromText('POINT(' + cast(ag.longitude as varchar(20)) + ' ' + cast(ag.latitude as varchar(20)) + ')', 4326).STWithin(
      geography::STPolyFromText('POLYGON((' + @polygon + '))', 4326)) = 1
ORDER BY u.uuid, u2.uuid, a.timefrom, b.pairedtime
)

GO



drop function if exists getOtherstrajectories
go

create function getOtherstrajectories(
	@uuid varchar(40), 
	@timefrom datetime2(0), 
	@timeto datetime2(0),
	@distance float = 15,      -- what distance to other UUID's we are searching for
	@overlap int = 0,          -- overlap in secondes to other UUID's, should be 0 to catch overlapping events in speed 
	@minoverlaptime int = 1000 -- minumum sum overlaptime
	)
returns table 
as return (
with myt as (SELECT distinct u1.id,
		min(b.timefrom) as startoverlap,
		max(b.timeto)  as endoverlap 
	from gpsevents a with (readuncommitted)
		join uuid_id u1 on a.id = u1.id
	JOIN gpsevents b with (readuncommitted)
		ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) 
			AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
			AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude))))  
		and datediff(ss,
			iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
			iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)
			) >= @overlap
	join uuid_id u2 on b.id = u2.id
		where u1.uuid = @uuid
		AND a.timefrom >= @timefrom
		AND a.timeto <= @timeto
		and u1.uuid <> u2.uuid
		and a.daypart >= datepart(dayofyear,@timefrom) -- search data only from relevant day partitions
		and a.daypart <= datepart(dayofyear,@timeto)
	group by u1.id
	-- spesify that the total intersection time must be over the @minoverlaptime threashold, minimum 10 sec per event
	-- probably more efficient ways to express this, but the query optimizer is efficient 
	having sum(iif(datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) < 10, 
		   10, datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto))
		   )) > @minoverlaptime) 
select top 100 percent uuid_id.uuid, t.timefrom, t.timeto, t.latitude, t.longitude, accuracy, speed,
       round(f.distancemeters,2) as distancemeters,
       round((iif(f.distancemeters=0, 0, isnull(f.distancemeters,0)))/((iif(t.diffsec=0, 1, isnull(t.diffsec,1)))),2) as [m/s]
from (select distinct gpsevents.id, timefrom, timeto, latitude, longitude, accuracy, speed, 
		abs(datediff(ss,
			timefrom,                                -- current row timefrom
			lag(timefrom) over (partition by gpsevents.id order by timefrom))) -- previous row timeto
				as diffsec,                      -- difference in sec between last position and current pos
		lag(latitude) over (partition by gpsevents.id order by timefrom) as prevlat,
		lag(longitude) over (partition by gpsevents.id order by timefrom) as prevlong
	from gpsevents with (readuncommitted)
	join myt on gpsevents.id = myt.id 
		and gpsevents.timefrom >= myt.startoverlap
		and gpsevents.timeto <= myt.endoverlap
	where timefrom >= @timefrom  -- possibly redundant, but counting on optimizer 
	AND timeto     <= @timeto
	and daypart >= datepart(dayofyear,@timefrom) -- search only within the relevant "day-segments" of the table
	and daypart <= datepart(dayofyear,@timeto)
	) as t
join uuid_id on t.id = uuid_id.id
cross apply dbo.fnGetDistanceT(t.latitude,t.longitude,t.prevlat,t.prevlong) as f
order by 1 asc
)
;
go

--grant select on getOtherstrajectories to coronapipeline
--grant select on getOthersTrajectories to [FHI-Smittestopp-Analytics-Prod];

GO



drop function if exists [getBluetoothPairing]
go
create function [dbo].[getBluetoothPairing] (@uuid varchar(36),
	@timefrom datetime2(0),
	@timeto datetime2(0))
returns table
as 
return (
SELECT distinct top 100 percent u1.uuid as uuid,u2.uuid as paireddeviceid,
	t1.platform as uuid_platform, 
	isnull(t2.platform,'ios') as pair_platform,
	bt.pairedtime,
	DATEDIFF(SECOND,'1970-01-01', bt.pairedtime) pairedtime_ut,
	bt.rssi 
from btevents bt with(nolock)
join uuid_id u1  with(nolock) on bt.id = u1.id
join uuid_id u2  with(nolock) on bt.pairedid = u2.id
cross apply (select top 1 uuid, platform from dluserdatastaging with(nolock) where uuid = u1.uuid) t1 --on u1.uuid = t1.uuid
outer apply (select top 1 uuid, platform from dluserdatastaging with(nolock) where uuid = u2.uuid) t2 --on u2.uuid = t2.uuid 
where (u1.uuid=@uuid or u2.uuid = @uuid) 
	--and bt.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	and bt.pairedtime between @timefrom and @timeto 
	and	bt.rssi < 0
order by bt.pairedtime asc);
GO
--grant select on getBluetoothPairing to [FHI-Smittestopp-Analytics-Prod];
--grant select on getBluetoothPairing to coronapipeline;
go


drop function if exists [UNIXToDateTime]
go
CREATE FUNCTION [dbo].[UNIXToDateTime] (@timestamp int)
        RETURNS datetime
AS
BEGIN
        DECLARE @ret datetime = DATEADD(second, @timestamp, '1970/01/01 00:00:00')
        RETURN @ret
END
GO

drop function if exists [DateTimeToUNIX]
go
CREATE FUNCTION [dbo].[DateTimeToUNIX] (@date datetime)
        RETURNS int
AS
BEGIN
        DECLARE @ret int= DATEDIFF(second, '1970/01/01 00:00:00', @date)
        RETURN @ret
END
GO


drop function if exists CSVToTable
go

CREATE FUNCTION [dbo].[CSVToTable] (@InStr VARCHAR(MAX))
RETURNS @TempTab TABLE
   (uuid varchar(36) not null)
AS
BEGIN
    ;-- Ensure input ends with comma
	SET @InStr = REPLACE(@InStr + ',', ',,', ',')
	DECLARE @SP INT
DECLARE @VALUE VARCHAR(36)
WHILE PATINDEX('%,%', @INSTR ) <> 0 
BEGIN
   SELECT  @SP = PATINDEX('%,%',@INSTR)
   SELECT  @VALUE = LEFT(@INSTR , @SP - 1)
   SELECT  @INSTR = STUFF(@INSTR, 1, @SP, '')
   INSERT INTO @TempTab(uuid) VALUES (@VALUE)
END
	RETURN
END
GO


drop function if exists RemoveNonASCII
go

CREATE FUNCTION RemoveNonASCII(
	@nstring nvarchar(255)
)
RETURNS varchar(255)
AS
BEGIN
	DECLARE @Result varchar(255)
	SET @Result = ''
	DECLARE @nchar nvarchar(1)
	DECLARE @position int
	SET @position = 1
	WHILE @position <= LEN(@nstring)
	BEGIN
		SET @nchar = SUBSTRING(@nstring, @position, 1)
		--Unicode & ASCII are the same from 1 to 255.
		--Only Unicode goes beyond 255
		--0 to 31 are non-printable characters
		IF (UNICODE(@nchar) between 48 and 57 -- numbers
			or UNICODE(@nchar) between 65 and 90 -- small letter
			or UNICODE(@nchar) between 97 and 122 -- large letters
			or UNICODE(@nchar) between 44 and 46) -- bindestrek
			SET @Result = @Result + @nchar
		SET @position = @position + 1
	END
	RETURN @Result
END
GO


drop function if exists getDeviceInformation
go
CREATE FUNCTION getDeviceInformation(    
@uuid_list VARCHAR(1000)    
)
RETURNS TABLE AS
RETURN(SELECT distinct uuid,platform,model,appversion
FROM dluserdatastaging with(nolock)
join (select value from string_split(@uuid_list,',')) as s on s.value = dluserdatastaging.uuid)
GO
		  
		  

		  
drop function if exists getDeviceInformationSingle
GO
CREATE FUNCTION getDeviceInformationSingle(
    @uuid VARCHAR(100)
)
RETURNS TABLE AS
RETURN(
    SELECT distinct uuid,platform,model,appversion
    FROM dluserdatastaging with(nolock)
    WHERE @uuid=uuid
)
GO

-- Create function for getting pin codes by phone number (msisdn)
create function dbo.getPinCodesByPhoneNumber
(
        @msisdn char(16)
)
returns table
as
return
(select pin, created_at from PINcodes where msisdn = @msisdn)

GO

-- Create function for getting the newest entry, newer than a given threshold, if any
create function dbo.getPinCodeNewestEntryByThreshold
(
        @msisdn char(16),
        @threshold datetime2(0)
)
returns table
as
return
(select top(1) pin, created_at from PINcodes where msisdn = @msisdn and created_at > @threshold order by created_at desc)

GO

create function [dbo].[getBirthYear]
(
    @uuid varchar(36)
)
returns table
as
return
(select birthyear from dbo.birthyear where uuid = @uuid)
