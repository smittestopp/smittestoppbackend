-- kjøre hver natt
-- 1 antall bt pairinger, time, dato, grunnkrets, filter på fra-til
-- 2 antall unike uuids, time, dato, grnnkrets ()
-- 3 telling av første GPS/UUID event i døgnet for grunnkrets, dato, grunnkrets

exec sp_who2
select datepart(dayofyear,getdate())

--1
-- select * from stats_getbtpairings('2020-05-05 00:00:00','2020-06-05 00:00:00')
drop function stats_getbtpairings
go
create function stats_getbtpairings(
	@timefrom datetime2(0), 
	@timeto datetime2(0))
returns table
as
return(
	select top 100 percent cast(pairedtime as char(10)) as day, datepart(hour,pairedtime) as hour, grunnkrets_kode, count(*) as total
	from agg_gpsevents a with(nolock)
	join btevents b with (nolock) on a.id = b.id and (b.pairedtime between a.timefrom and a.timeto) and a.daypart = b.daypart
	join grunnkrets with (nolock) on a.grunnkrets_id = grunnkrets.grunnkrets_id
	where a.timefrom >= @timefrom
		AND a.timeto <= @timeto
	group by cast(pairedtime as char(10)), datepart(hour,pairedtime), grunnkrets_kode
	order by 1 asc, 2 asc, 3 asc
)


--2
-- select * from stats_getgpsbygrunnkrets('2020-05-31 00:00:00','2020-06-05 00:00:00')
drop function stats_getgpsbygrunnkrets
go
create function stats_getgpsbygrunnkrets(
	@timefrom datetime2(0), 
	@timeto datetime2(0))
returns table
as
return(
select top 100 percent cast(timeto as char(10)) as day, datepart(hour,timeto) as hour, grunnkrets_kode, count(distinct id) as total
from agg_gpsevents with(nolock)
join grunnkrets on agg_gpsevents.grunnkrets_id = grunnkrets.grunnkrets_id
	where timefrom >= @timefrom
		AND timeto <= @timeto
group by cast(timeto as char(10)), datepart(hour,timeto), grunnkrets_kode
order by 1 asc, 2 asc, 3
)

--3
-- select * from stats_getfirstgpsbygrunnkrets('2020-05-31 00:00:00','2020-06-05 00:00:00')
drop function stats_getfirstgpsbygrunnkrets
go
create function stats_getfirstgpsbygrunnkrets(
	@timefrom datetime2(0), 
	@timeto datetime2(0))
returns table
as
return(
with firsttimes as (select id, min(timeto) as timeto from agg_gpsevents with(nolock)
	where timefrom >= @timefrom
		AND timeto <= @timeto
	group by id)
select top 100 percent cast(a.timeto as char(10)) as day, grunnkrets_kode, count(*) as total
from agg_gpsevents a with(nolock)
join firsttimes f on a.id = f.id and a.timeto = f.timeto 
join grunnkrets on a.grunnkrets_id = grunnkrets.grunnkrets_id
where a.timefrom >= @timefrom
	AND a.timeto <= @timeto
group by cast(a.timeto as char(10)),  grunnkrets_kode
order by 1 asc, 2 asc
)
go

grant select on stats_getfirstgpsbygrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on stats_getgpsbygrunnkrets to [FHI-Smittestopp-Analytics-Prod];
grant select on stats_getbtpairings to [FHI-Smittestopp-Analytics-Prod];
