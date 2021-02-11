/********

Same as above, but not aggregating - giving all parings within the polygon with both GPS and BT details

Example: -- NOTE this polygon is Oslo Sentrum within Ring 3 so it's a bit large result set
select * from getBTpairingsWithinPolygons('10.685 59.947,10.796 59.948,10.795 59.904,10.681 59.903,10.685 59.947' , '2020-04-09' , -6 , 6)

********/

drop function getBTpairingsWithinPolygons
go

create function getBTpairingsWithinPolygons(
	@polygon varchar(8000),
	@dateday datetime2(0),
	@timeslack_before int,
	@timeslack_after int
	)
returns table
as
return (
SELECT top 100 percent
	a.uuid           AS gps_uuid,
	a.timefrom       AS gps_timefrom,
	a.timeto         AS gps_timeto,
	a.latitude       AS gps_latitude,
	a.longitude      AS gps_longitude,
 	a.accuracy       AS gps_accuracy,
	b.paireddeviceid AS by_uuid,
        b.pairedtime     AS bt_pairedtime,
	b.rssi		 AS bt_rssi,
	b.txpower	 AS bt_txpower
FROM userevents a INNER JOIN userevents_bluetooth b
ON a.uuid = b.uuid
   AND a.daypart = datepart(dayofyear, @dateday)
   AND b.daypart = datepart(dayofyear, @dateday)
   AND b.pairedtime BETWEEN dateadd(ss, @timeslack_before , a.timefrom) AND dateadd(ss , @timeslack_after , a.timeto)
WHERE geography::STPointFromText('POINT(' + cast(a.longitude as varchar(20)) + ' ' + cast(a.latitude as varchar(20)) + ')', 4326).STWithin(
      geography::STPolyFromText('POLYGON((' + @polygon + '))', 4326)) = 1
ORDER BY a.uuid, b.paireddeviceid, a.timefrom, b.pairedtime
)
GO

grant select on getBTpairingsWithinPolygons to coronaanalyst



/********

	v2 - splitted the search/filtering before the join

Example: -- NOTE this polygon is Oslo Sentrum within Ring 3 so it's a bit large result set
select * from getBTpairingsWithinPolygons2('10.685 59.947,10.796 59.948,10.795 59.904,10.681 59.903,10.685 59.947' , '2020-04-09' , -6 , 6)

********/

drop function getBTpairingsWithinPolygons2
go

create function getBTpairingsWithinPolygons2(
	@polygon varchar(8000),
	@dateday datetime2(0),
	@timeslack_before int,
	@timeslack_after int
	)
returns table
as
return (
with filter as (
	SELECT distinct uuid , timefrom , timeto , latitude , longitude , accuracy FROM userevents
	WHERE daypart = datepart(dayofyear, @dateday)
        AND geography::STPointFromText('POINT(' + cast(longitude as varchar(20)) + ' ' + cast(latitude as varchar(20)) + ')', 4326).STWithin( geography::STPolyFromText('POLYGON((' + @polygon + '))', 4326)) = 1
	)
SELECT top 100 percent
	a.uuid           AS gps_uuid,
	a.timefrom       AS gps_timefrom,
	a.timeto         AS gps_timeto,
	a.latitude       AS gps_latitude,
	a.longitude      AS gps_longitude,
 	a.accuracy       AS gps_accuracy,
	b.paireddeviceid AS by_uuid,
        b.pairedtime     AS bt_pairedtime,
	b.rssi		 AS bt_rssi,
	b.txpower	 AS bt_txpower
FROM filter a JOIN userevents_bluetooth b
ON a.uuid = b.uuid
   AND b.daypart = datepart(dayofyear, @dateday)
   AND b.pairedtime BETWEEN dateadd(ss, @timeslack_before , a.timefrom) AND dateadd(ss , @timeslack_after , a.timeto)
ORDER BY a.uuid, b.paireddeviceid, a.timefrom, b.pairedtime
)
GO

grant select on getBTpairingsWithinPolygons2 to coronaanalyst



/********

Same idea as above, but it is no longer a polygon but a BoundingBox (BB) given by <south,west> and <north,east> corners
of the BB.

Example: -- NOTE this BB is Oslo Sentrum within Ring 3 so it's a bit large result set
select * from getBTpairingsWithinBB(10.681 , 59.903 , 10.796 , 59.948 , '2020-04-09' , -6 , 6)

********/

drop function getBTpairingsWithinBB
go

create function getBTpairingsWithinBB(
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
with filter as (
	SELECT DISTINCT uuid , timefrom , timeto , latitude , longitude , accuracy
	FROM userevents
	WHERE daypart = datepart(dayofyear, @dateday)
	      AND latitude  BETWEEN @latmin  and @latmax
	      AND longitude BETWEEN @longmin and @longmax
)
SELECT top 100 percent
	a.uuid           AS gps_uuid,
	a.timefrom       AS gps_timefrom,
	a.timeto         AS gps_timeto,
	a.latitude       AS gps_latitude,
	a.longitude      AS gps_longitude,
 	a.accuracy       AS gps_accuracy,
	b.paireddeviceid AS by_uuid,
        b.pairedtime     AS bt_pairedtime,
	b.rssi		 AS bt_rssi,
	b.txpower	 AS bt_txpower
FROM filter a INNER JOIN userevents_bluetooth b
ON a.uuid = b.uuid
   AND b.daypart = datepart(dayofyear, @dateday)
   AND b.pairedtime BETWEEN dateadd(ss, @timeslack_before , a.timefrom) AND dateadd(ss , @timeslack_after , a.timeto)
ORDER BY a.uuid, b.paireddeviceid, a.timefrom, b.pairedtime
)
GO

grant select on getBTpairingsWithinBB to coronaanalyst







/********

Get all uuids within a BB given by the <south,west> and <north,east> corners in a given time interval

select * from getWithinBB(10.681 , 59.903 , 10.796 , 59.948 , '2020-04-01' , '2020-04-09')

********/

/*** defined earlier - do not change

drop function getWithinBB
go


create function getWithinBB(
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
	SELECT DISTINCT uuid , timefrom , timeto , latitude , longitude , accuracy, speed
	FROM userevents
	WHERE longitude BETWEEN @longmin and @longmax
		AND latitude BETWEEN @latmin  and @latmax
		AND timefrom >= @timefrom
		AND timeto <= @timeto
		AND daypart >= datepart(dayofyear,@timefrom)
		AND daypart <= datepart(dayofyear,@timeto)
)
GO
****/


-- batched several requests - a while loop would be great

/***
drop function getWithinBBlist
go


create function getWithinBBlist(
       	@longminA decimal(9,6), @latminA decimal(9,6), @longmaxA decimal(9,6), @latmaxA decimal(9,6), @timefromA datetime2(0), @timetoA datetime2(0),
       	@longminB decimal(9,6), @latminB decimal(9,6), @longmaxB decimal(9,6), @latmaxB decimal(9,6), @timefromB datetime2(0), @timetoB datetime2(0),
       	@longminC decimal(9,6), @latminC decimal(9,6), @longmaxC decimal(9,6), @latmaxC decimal(9,6), @timefromC datetime2(0), @timetoC datetime2(0),
       	@longminD decimal(9,6), @latminD decimal(9,6), @longmaxD decimal(9,6), @latmaxD decimal(9,6), @timefromD datetime2(0), @timetoD datetime2(0),
       	@longminE decimal(9,6), @latminE decimal(9,6), @longmaxE decimal(9,6), @latmaxE decimal(9,6), @timefromE datetime2(0), @timetoE datetime2(0)
	)
returns table
as
return (
	SELECT DISTINCT uuid , timefrom , timeto , latitude , longitude , accuracy, speed
	FROM (
	     select * from getWithinBB(@longminA,@latminA,@longmaxA,@latmaxA,@timefromA,@timetoA)
	     UNION
	     select * from getWithinBB(@longminB,@latminB,@longmaxB,@latmaxB,@timefromB,@timetoB)
	     UNION
	     select * from getWithinBB(@longminC,@latminC,@longmaxC,@latmaxC,@timefromC,@timetoC)
	     UNION
	     select * from getWithinBB(@longminD,@latminD,@longmaxD,@latmaxD,@timefromD,@timetoD)
	     UNION
	     select * from getWithinBB(@longminE,@latminE,@longmaxE,@latmaxE,@timefromE,@timetoE
	     )
	ORDER BY uuid, timefrom ASC
)
GO


-- examples

SELECT * FROM getWithinBB (10.803672, 59.844187,10.804089,59.845785,'2020-04-02 14:43:17','2020-04-02 14:48:33') ORDER BY 1,2 ASC
UNION
SELECT * FROM getWithinBB (10.803754, 59.842059,10.804268,59.843825,'2020-04-02 14:48:34','2020-04-02 14:51:36') ORDER BY 1,2 ASC
UNION
SELECT * FROM getWithinBB (10.804346, 59.840181,10.805156,59.841919,'2020-04-02 14:51:37','2020-04-02 14:55:12') ORDER BY 1,2 ASC
UNION
SELECT * FROM getWithinBB (10.805305, 59.838413,10.80625, 59.840077,'2020-04-02 14:55:13','2020-04-02 14:58:23') ORDER BY 1,2 ASC
UNION
SELECT * FROM getWithinBB (10.806394, 59.837576,10.80776, 59.839221,'2020-04-02 14:58:24','2020-04-02 15:03:40') ORDER BY 1,2 ASC
go

SELECT * FROM getWithinBBlist (10.803672, 59.844187, 10.804089, 59.845785, '2020-04-02 14:43:17', '2020-04-02 14:48:33',
       	      		       10.803754, 59.842059, 10.804268, 59.843825, '2020-04-02 14:48:34', '2020-04-02 14:51:36',
			       10.804346, 59.840181, 10.805156, 59.841919, '2020-04-02 14:51:37', '2020-04-02 14:55:12',
			       10.805305, 59.838413, 10.80625,  59.840077, '2020-04-02 14:55:13', '2020-04-02 14:58:23',
			       10.806394, 59.837576, 10.80776,  59.839221, '2020-04-02 14:58:24', '2020-04-02 15:03:40')
go

***/
