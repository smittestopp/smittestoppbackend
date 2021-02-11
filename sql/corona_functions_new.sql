/*
Smittestopp Functions
*/

/******
​
The below function is an INTERNAL "light-weight Haversine formula" function to speed lookup up 
compared to using the GEO-type intersection operations ;-) 
Look up Haversine formula on Wikipedia for detailed explanation of the calculations.
​
****/

drop function fngetDistance
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


/******
​
The below function is an INTERNAL "light-weight Haversine formula" function to speed lookup up 
compared to using the GEO-type intersection operations ;-) 
Look up Haversine formula on Wikipedia for detailed explanation of the calculations.

This is an inline table-valued function doing the same as above. We'll use this the most I guess.

*******/


drop function fngetDistanceT
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
/*
Another version, a little simplified, but not faster (not conclusive, so we keep it for now)
*/
go

drop function fngetDistanceT2
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


/*********
Given the @uuid of a patient P, find its trajectory (sequence of log entries) between time @timefrom to @timeto 

Example:
select * from gettrajectory('8c8c985e610b4eb19268b23e2c348a6a','2020-04-16 00:00:00',getdate())
**********/

drop function getTrajectory
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

/*
Given the @uuid of a patient P, find its trajectory (sequence of log entries) between time @timefrom to @timeto 
and calculate the speed and distance between the various coordinates 

(Another version of the above "getTrajectory", adding speed calculations from previous coordinate)

Example:
select * from getTrajectorySpeed('8c8c985e610b4eb19268b23e2c348a6a' , '2020-04-24 00:00:00' , getdate())
*/


drop function getTrajectorySpeed
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
DROP FUNCTION [dbo].[getTrajectoryV2]
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



/***********************************************************
​
SOME GENERAL EXPPLANATIONS OF FUNCTIONS BELOW
​
1: In the JOIN, we prefilter for processing optimization using
      
       ON b.latitude BETWEEN a.latitude - (1 / 111.045) -- 1 km radius prefilter, change this to search wider
		AND a.latitude + (1 / 111.045)
		and b.longitude BETWEEN a.longitude - (1 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (1 / (111.045 * COS(RADIANS(a.latitude))))   
	  
	  This works as a constraint so we aren't searching for EVERY coordinate, but limiting it to within 
	  x km of our latitude/longitude, and get better efficiency using indexes. Latitudes are a constant 111.045 km width.
	  For the longitude it's more complex than latitude, since degrees of longitude are smaller distances the further away 
	  from the equator we move, so for longitude we have to multiply by the cosine of the latitude radius in order to get the correct km.

​
2: To define an overlap in time, we use (and return)
     	
	datediff(ss,iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
​
	This in general calculates the differense between MAX(a.timefrom  ,b.timefrom) and MIN(a.timeto , a.timeto).
	Then, the general overlap ">= @overlap" is to allow the user to define what the timeoverlap should be, as there are several log-entries of size = 0.
	- @overlap = 0 will catch everything that barely overlap.
	- @overlap > 0 requires the logs to overlap more than 0, meaning missing all events = 0
	- @overlap < 0 gives some slack. The calculated duration will then have no meaning, 
	  but one can see events where one enter a room where someone has been, you may be exposed to virus she has left behind, even though we have no overlap.
​
***********************************************************/
​
​
​
​
/*
Given the trajectory of P for user @uuio, find all trajectories that intersect with it                                      
—-> translated to: given person @uuid, find all intersection within a distance @distance for more than @overlapt between @timefrom to @timeto
​
Example:
select * from getIntersectedTrajectories('8c8c985e610b4eb19268b23e2c348a6a','2020-04-24 12:00:00','2020-04-24 18:00:00',5,0)
*/

drop function getIntersectedTrajectories
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

/*
Version of above, adding speed calculations from last row. Adding this as new function because it costs a little more.

Example:
select * from getIntersectedTrajectoriesSpeed('04368b5ef8bd4d6e88145242ac8afc96',dateadd(day,-14,getdate()),getdate(),5,0)

*/

drop function getIntersectedTrajectoriesSpeed
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

/*
Another version of getIntersectedTrajectories, 2x faster and less IO but more approximate. Instead of filtering on the fnGetDistanceT function,
we search within a rough square of @distance*@distance and just calculate the fnGetDistance for returning rows.

Example:
select * from getIntersectedTrajectories2('8c8c985e610b4eb19268b23e2c348a6a','2020-04-16 12:00:00','2020-04-17 12:00:00',2,5)
*/

drop function getIntersectedTrajectories2
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


/*
Just like getIntersectedTrajectories, let's make a Speed version of getIntersectedTrajectories2

Example:
select * from getIntersectedTrajectoriesSpeed2('0f8b985e5f044c84b6169a539b780012',dateadd(day,-14,getdate()),getdate(),5,0)
*/

drop function getIntersectedTrajectoriesSpeed2
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


/*
Now, let's also get the intersected Other UUID's speed from THEIR last measurement

Example:
select * from getIntersectedTrajectoriesIntersectSpeed2('1df18c5eee4a440387e217920eac3651',dateadd(day,-14,getdate()),getdate(),5,0)
*/

/*
drop function getIntersectedTrajectoriesIntersectSpeed2
go

create function getIntersectedTrajectoriesIntersectSpeed2(
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
	),
intermedresult as (
SELECT top 100 percent a.uuid as MyUUID, 
	a.latitude as MyLocationLat,
	a.longitude as MyLocationLong,
	a.accuracy as MyAccuracy,
	a.speed,
	a.distancemeters,
	a.[m/s],
    b.uuid as OtherUUID, 
	b.latitude as OtherLocationLat,
	b.longitude as OtherLocationLong,
	b.accuracy as OtherAccuracy,
	b.timefrom,
	b.timeto,
	iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom) as overlapstart,
	iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) as overlapend,
   datediff(ss,iif(datediff(ss,a.timefrom, b.timefrom)>0, b.timefrom,a.timefrom), 
		iif(datediff(ss,a.timeto, b.timeto)>0,a.timeto,b.timeto)) as overlaptime,
	round(dbo.fnGetDistance(a.latitude,a.longitude,b.latitude,b.longitude),2) as dist
FROM filter a 
JOIN userevents b 
	ON b.latitude BETWEEN a.latitude - (@distance*0.001 / 111.045) 
		AND a.latitude + (@distance*0.001 / 111.045)
		and b.longitude BETWEEN a.longitude - (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude)))) 
		AND a.longitude + (@distance*0.001 / (111.045 * COS(RADIANS(a.latitude))))  
	and datediff(ss,
		iif(datediff(ss, a.timefrom, b.timefrom) > 0, b.timefrom, a.timefrom),
			iif(datediff(ss, a.timeto, b.timeto) > 0, a.timeto, b.timeto)) >= @overlap
    AND a.uuid <> b.uuid
		and b.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
order by iif(datediff(ss, a.timeto,   b.timeto)   > 0, a.timeto,   b.timeto) desc
)
select a.MyUUID, a.MyLocationLat, a.MyLocationLong,a.MyAccuracy,a.speed,a.distancemeters, a.[m/s] as MyMPS,a.OtherUUID,
			a.OtherLocationLat,a.OtherLocationLong,a.OtherAccuracy,a.overlapstart, a.overlapend, a.overlaptime, a.dist, 
	case when (round(dbo.fnGetDistance(a.OtherLocationLat,a.OtherLocationLong,u3.latitude,u3.longitude),2))=0 then 0 else
		round((dbo.fnGetDistance(a.OtherLocationLat,a.OtherLocationLong,u3.latitude,u3.longitude)/datediff(ss,u3.timefrom,a.timefrom)),2) end as OtherMPS
from (select i.MyUUID, i.MyLocationLat, i.MyLocationLong,i.MyAccuracy,i.speed,i.distancemeters, i.[m/s],i.OtherUUID,
			i.OtherLocationLat,i.OtherLocationLong,i.OtherAccuracy,i.timefrom,i.timeto,i.overlapstart, i.overlapend, i.overlaptime, i.dist,
		max(u2.timefrom) as maxtime
	from intermedresult i
	join userevents u2
		on i.otheruuid = u2.uuid
		and i.timefrom > u2.timefrom
	group by i.MyUUID, i.MyLocationLat, i.MyLocationLong,i.MyAccuracy,i.speed,i.distancemeters, i.[m/s],i.OtherUUID,
			i.OtherLocationLat,i.OtherLocationLong,i.OtherAccuracy,i.timefrom,i.timeto,i.overlapstart, i.overlapend, i.overlaptime, i.dist) as a
join userevents u3 on a.OtherUUID = u3.uuid and a.maxtime = u3.timefrom	
);
go
*/
/***********************************************
Sum over overlaptime

Find all persons that have intersected with person @uuid within a distance @distance for more than @sumoverlaptime seconds in total between @timefrom to @timeto 
Note that the sum of the interactions, to be above @sumoverlaptime, is a calculated minimum. The database sum does NOT include more time than logged on the phone. 
There is no operations calculating the longer trajectories between shorter log entries etc. Thus, this sum is a bare minimum. 
Any python trajectory code probably interpolate and merge more entries into larger trajectories, meaning also counting time between these log entries. 
Thus, the real trajectory intersection times are probably get higher times than what is returned by the database. Still, the idea is to remove whoever 
that is just passing each other during a day far below for example the 15 minutes (900 sec) FHI wants.

The returned count is supposed to give an indication whether there are a lot of short overlapping events which will be the case in a moving person. 
The reason is that for example on a buss, the phone will not merge events due to high speed  (position changing between every 12 sec logentry), 
having timefrom=timeto, and the sum of time will not be increased. Thus, it will NOT be captured by the sum of times. However, if we also add the count, 
then a high number could be able to help identifying these situations.

Example usage:
select * from getSumIntersectedOverlaps('0b4f985e686e4cadb69db1fe3362ee18','2020-04-16 00:00:00','2020-04-17 00:00:00',5,10,0)
************************************************/

drop function getSumIntersectedOverlaps
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

/*
Combining the two above, returning full trajectories for UUIDs that are above sumoverlaptim. 
​
Find all persons that have intersected with person @uuid within a distance @distance for more than @sumoverlaptime seconds in total between @timefrom to @timeto 
​
Note that the sum of the interactions, to be above @sumoverlaptime, is a calculated minimum. The database sum does NOT include 
more time than logged on the phone. There is no operations calculating the longer trajectories between shorter log entries etc. 
Thus, this sum is a bare minimum. Any python trajectory code probably interpolate and merge more entries into larger trajectories, 
meaning also counting time between these log entries. Thus, the real trajectory intersection times are probably get higher times than 
what is returned by the database. Still, the idea is to remove whoever that is just passing each other during a day 
far below for example the 15 minutes (900 sec) FHI wants . 
​
Example:
select * from getIntersectedTrajectoriesBySumoverlaptime('2dc459f074e011eaa2e65e8d493bf34f' , '2020-04-02 00:00:00' , getdate() , 5 , 900,0)
*/

drop function getIntersectedTrajectoriesBySumoverlaptime
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

/*
getIntersections  ,  Find intersecting trajectories between persons a and b that have intersected within a distance @distance between @timefrom to @timeto   

example:
select * from getIntersections('0b4f985e686e4cadb69db1fe3362ee18','08295a74750811ea94e20edabf845fab','2020-03-01 00:00:00',getdate(),5,0)

-- Fint some active UUIDs
select uuid, count(*)
from gpsevents a join uuid_id u on a.id = u.id
where daypart = 107
group by uuid having count(*) > 1000 order by 2 desc
*/

drop function getIntersections
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

/********

Search for points (devices) within a polygon within a timeintercal:

Input must be in the format for the polygon: 'lon lat,lon lat,lon lat,lon lat, ...'  
(an arbitrary number of points in the polygon, but it must be closed, meaning that the first and last point must be the same)

This function translates the coordinates to points and polygons using the geography functions.

Example: -- NOTE this polygon is Oslo Sentrum within Ring 3 so it's a bit large result set
select * from getWithinPolygons('10.685 59.947,10.796 59.948,10.795 59.904,10.681 59.903,10.685 59.947',dateadd(day,-14,getdate()),getdate())

*******/

drop function getWithinPolygons
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


/********

Search for gps events within a Grunnkrets by a char(8) grunnkretskode 

Example: -- NOTE this grunnkrets is Frogner
select * from getGPSWithinGrunnkrets('03011101',dateadd(day,-14,getdate()),getdate())

*******/

drop function getGPSWithinGrunnkrets
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

drop function getGPSWithinGrunnkretsSimple
go

create function getGPSWithinGrunnkretsSimple(
	@grunnkretskode char(8), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid, ag.latitude, ag.longitude, ag.timefrom, ag.timeto, ag.accuracy
from uuid_id u with(nolock)
join agg_gpsevents ag with(nolock) on u.id = ag.id 
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
where ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and gk.grunnkrets_kode = @grunnkretskode
)
GO

/********

Search for gps events within multiple Grunnkrets by a comma-separated list of char(8) grunnkretskode 

Example: -- NOTE this list of grunnkrets is multiple grunnkrets in Frogner
select * from getGPSWithinMultipleGrunnkrets('03010612,03010613,03010614',dateadd(day,-14,getdate()),getdate())
order by 1 asc

*******/

drop function getGPSWithinMultipleGrunnkrets
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

drop function getGPSWithinMultipleGrunnkretsSimple
go

create function getGPSWithinMultipleGrunnkretsSimple(
	@grunnkretskode nvarchar(max), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid, ag.latitude, ag.longitude, ag.timefrom, ag.timeto, ag.accuracy
from uuid_id u with(nolock) 
join agg_gpsevents ag with(nolock) on u.id = ag.id 
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
join (select value from string_split(@grunnkretskode,',')) as s on gk.grunnkrets_kode = s.value
where ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
)
GO


/********

Search for BT events within a Grunnkrets by a char(8) grunnkretskode 

Example: -- NOTE this grunnkrets is Frognerparken
select * from getBTWithinGrunnkrets('03010501',dateadd(day,-14,getdate()),getdate())

*******/

drop function getBTWithinGrunnkrets
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


drop function getBTWithinGrunnkretsSimple
go

create function getBTWithinGrunnkretsSimple(
	@grunnkretskode char(8), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid,
	ag.timefrom       AS gps_timefrom,
	ag.timeto         AS gps_timeto,
	ag.latitude       AS gps_latitude, 
	ag.longitude      AS gps_longitude,
 	ag.accuracy       AS gps_accuracy,  a.pairedtime, a.rssi, a.txpower, u2.uuid as other_uuid
from btevents a with(nolock)
join uuid_id u with(nolock) on a.id = u.id
join uuid_id u2 with(nolock) on a.pairedid = u2.id
join agg_gpsevents ag with(nolock) on a.id = ag.id and a.pairedtime between ag.timefrom and ag.timeto
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
where ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
	  and gk.grunnkrets_kode = @grunnkretskode
)
GO

/*
select * from getUniqueUUIDsWithinGrunnkrets('03010501',dateadd(day,-14,getdate()),getdate())

*/
drop function getUniqueUUIDsWithinGrunnkrets
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


/*
sp_who2
select * from getUniqueUUIDsWithinMultipleGrunnkrets('03010612,03010613,03010614',dateadd(day,-14,getdate()),getdate())
*/

drop function getUniqueUUIDsWithinMultipleGrunnkrets
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


/********

Search for BT events within multiple Grunnkrets by a comma-separated list of char(8) grunnkretskode 

Example: -- NOTE this list of grunnkrets is multiple grunnkrets in Frogner
select * from getBTWithinMultipleGrunnkrets('03010611,03010612,03010613,0301614',dateadd(day,-14,getdate()),getdate())

*******/

drop function getBTWithinMultipleGrunnkrets
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

drop function getBTWithinMultipleGrunnkretsSimple
go

create function getBTWithinMultipleGrunnkretsSimple(
	@grunnkretskode char(8), 
	@timefrom datetime2(0), 
	@timeto datetime2(0)
	)
returns table
as
return (
select top 100 percent u.uuid,
	ag.timefrom       AS gps_timefrom,
	ag.timeto         AS gps_timeto,
	ag.latitude       AS gps_latitude, 
	ag.longitude      AS gps_longitude,
 	ag.accuracy       AS gps_accuracy, 
	a.pairedtime, a.rssi, a.txpower, u2.uuid as other_uuid
from btevents a with(nolock)
join uuid_id u with(nolock) on a.id = u.id
join uuid_id u2 with(nolock) on a.pairedid = u2.id
join agg_gpsevents ag with(nolock) on a.id = ag.id and a.pairedtime between ag.timefrom and ag.timeto
join grunnkrets gk with(nolock) on ag.grunnkrets_id = gk.grunnkrets_id
join (select value from string_split(@grunnkretskode,',')) as s on gk.grunnkrets_kode = s.value
where a.pairedtime between @timefrom and @timeto
      and ag.timefrom >= @timefrom
	  and ag.timeto <= @timeto
	  and ag.daypart between datepart(dayofyear,@timefrom) and datepart(dayofyear,@timeto)
)
GO

/****** Object:  UserDefinedFunction [dbo].[getWithinBB]    Script Date: 5/24/2020 11:15:45 PM ******/
drop function getwithinBB
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

drop function getwithinBBSimple
go

create function [dbo].[getWithinBBSimple](
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
	SELECT DISTINCT u.uuid , ag.timefrom , ag.timeto , ag.latitude , ag.longitude , ag.accuracy, ag.speed 
	FROM uuid_id u with(nolock) 
	join agg_gpsevents ag with(nolock) on u.id = ag.id 
	WHERE ag.longitude BETWEEN @longmin and @longmax
		AND ag.latitude BETWEEN @latmin  and @latmax
		AND ag.timefrom >= @timefrom
		AND ag.timeto <= @timeto
		AND ag.daypart >= datepart(dayofyear,@timefrom) 
		AND ag.daypart <= datepart(dayofyear,@timeto)
)
GO



drop function getUniqueUUIdswithinBB
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

/****** Object:  UserDefinedFunction [dbo].[getWithinBBlist]    Script Date: 5/24/2020 11:19:49 PM ******/

/*

getwithinMultipleBB
getUniqueUUIdswithinMultipleBB
Version with comma-separated list like:
'12,3 12,3 12,3 12,3; 23,4 23,4 23,4 23,4; 23,4 23,4 23,4 23,4'
*/

drop function [getWithinBBlist]
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
/***	     
	     select * from getWithinBB(@longminA,@latminA,@longmaxA,@latmaxA,@timefromA,@timetoA) 
	     UNION
	     (select * from getWithinBB(@longminB,@latminB,@longmaxB,@latmaxB,@timefromB,@timetoB)) 
	     UNION
	     (select * from getWithinBB(@longminC,@latminC,@longmaxC,@latmaxC,@timefromC,@timetoC)) 
	     UNION
	     (select * from getWithinBB(@longminD,@latminD,@longmaxD,@latmaxD,@timefromD,@timetoD)) 
	     UNION
	     (select * from getWithinBB(@longminE,@latminE,@longmaxE,@latmaxE,@timefromE,@timetoE))
***/	     
--	ORDER BY uuid, timefrom ASC
)
GO

/****** Object:  UserDefinedFunction [dbo].[getBTpairingsWithinBB]    Script Date: 5/25/2020 6:12:40 AM ******/
DROP FUNCTION [dbo].[getBTpairingsWithinBB]
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


DROP FUNCTION [dbo].[getBTpairingsWithinBBSimple]
GO

create function [dbo].[getBTpairingsWithinBBSimple](
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
	a.timefrom       AS gps_timefrom,
	a.timeto         AS gps_timeto,
	a.latitude       AS gps_latitude, 
	a.longitude      AS gps_longitude,
 	a.accuracy       AS gps_accuracy, 
	u2.uuid AS by_uuid,
        b.pairedtime     AS bt_pairedtime, 
	b.rssi		 AS bt_rssi,
	b.txpower	 AS bt_txpower

FROM filter a 
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
DROP FUNCTION [dbo].[getBTpairingsWithinPolygons]
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



/********
Returning trajectories of others that have an intersecting trajectory based on our input @uuid trajectory

1) First, make a temporarily "myt" table.
   Find which uuids that have intersected the between @timefrom and @timeto. Instead of returning all trajectories that 
   have intersected with the input uuid, we perform two optimizations
   a) just return the time between the first intersection with the infected person to the last intersection. Thus, if they 
      intersected at time x day 2 and at time y day 3, the trajectory returned is the one between time x and y.
   b) often, we are interested in and search for intersections of more than X minutes. Thus, if a person just passed 
      the infected person for a few seconds during the 14. day period, it is of no interest. The idea here is that we  only 
      return persons and their trajectories that have a TOTAL OVERLAP time more than @minoverlaptime (e.g., 900 sec = 15 minutes). 
      One shortcoming here is that if moving, the events sent by the phone in speed have timefrom = timeto, duration = 0. 
      We now detect these events and give a minimum value of about 10 s (the sampling frequency). 
      If you do not want to use it, just use "0", and all intersections wil be returned. 

2) For each uuid returned in "myt", return all events in the trajectory between the "startoverlap" and "endoverlap". We also 
   calculate and return speed and distance as for "getTrajecorySpeed.

Example usage:
select * from getOtherstrajectories('0f8b985e5f044c84b6169a539b780012', '2020-04-18 12:00', '2020-04-18 16:00', 5, 0, 900) order by 1, 2 asc
*******/

drop function getOtherstrajectories
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
grant select on getOthersTrajectories to [FHI-Smittestopp-Analytics-Prod];

GO


/*
getBluetoothPairing
select * from getBluetoothPairing('bb7d985e9ccb46f1bd5494cb830c0fd4', '2020-04-16 12:00:00', '2020-04-23 12:00:00') --9s
select * from getBluetoothPairing('855b985ed0e5450d80bfb720acee6840 ', '2020-04-16 12:00:00', '2020-04-28 12:00:00')
order by pairedtime asc

select * from userevents_bluetooth where uuid = '855b985ed0e5450d80bfb720acee6840' or paireddeviceid = '855b985ed0e5450d80bfb720acee6840'
and pairedtime between  '2020-04-16 12:00:00' and '2020-04-17 12:00:00'
order by pairedtime asc 

select top 100 * from uuid_id
join btevents on uuid_id.id = btevents.id
sp_spaceused 'btevents'
*/
drop function [getBluetoothPairing]
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
grant select on getBluetoothPairing to [FHI-Smittestopp-Analytics-Prod];
grant select on getBluetoothPairing to coronapipeline;
go

/*
Helper functions for conversions between datetime and unixtime

example:
SELECT dbo.UNIXToDateTime(dbo.DateTimeToUNIX(GETDATE()))
SELECT dbo.DateTimeToUNIX(GETDATE())
*/
drop function [UNIXToDateTime]
go
CREATE FUNCTION [dbo].[UNIXToDateTime] (@timestamp int)
        RETURNS datetime
AS
BEGIN
        DECLARE @ret datetime = DATEADD(second, @timestamp, '1970/01/01 00:00:00')
        RETURN @ret
END
GO

drop function [DateTimeToUNIX]
go
CREATE FUNCTION [dbo].[DateTimeToUNIX] (@date datetime)
        RETURNS int
AS
BEGIN
        DECLARE @ret int= DATEDIFF(second, '1970/01/01 00:00:00', @date)
        RETURN @ret
END
GO

/*
Helper function for converting a comma-separated string to a table
This is used in the getdatabyUUIDList procedure
*/
drop function CSVToTable
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

/*
Helper function for removing non-ASCII characters
This is used for data quality, garbage cleanup etc

example:
select dbo.RemoveNonASCII('1234*^"`6,.-7890')

*/
drop function RemoveNonASCII
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

/*********
SELECT * FROM getDeviceInformation('40ea8878728e11ea86d7ee3617b084b4,82e78c5e5c9245d69c5494db0e89576a')
**********/
		  
DROP FUNCTION getDeviceInformation
go
CREATE FUNCTION getDeviceInformation(    
@uuid_list VARCHAR(1000)    
)
RETURNS TABLE AS
RETURN(SELECT distinct uuid,platform,model,appversion
FROM dluserdatastaging with(nolock)
join (select value from string_split(@uuid_list,',')) as s on s.value = dluserdatastaging.uuid)

WHERE @uuid_list=uuid
OR @uuid_list LIKE uuid+',%'
OR @uuid_list LIKE '%,'+uuid+',%'
OR @uuid_list LIKE '%,'+uuid)
GO
		  
		  
/*********
SELECT * FROM getDeviceInformationSingle('40ea8878728e11ea86d7ee3617b084b4')
**********/
		  
DROP FUNCTION getDeviceInformationSingle
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


