CREATE or ALTER FUNCTION getContacts (@device varchar(36), @starttime datetime2, @endtime datetime2) 
RETURNS TABLE AS RETURN 
(
with flagged as (
  select *, 
         case
            when DATEDIFF(SECOND , lag(pairedtime) over (partition by bt.paireddeviceid,bt.uuid order by pairedtime), pairedtime) < 180  then 'ns' --lag(pairedtime) over (order by pairedtime)
            when DATEDIFF(SECOND , lag(pairedtime) over (partition by bt.paireddeviceid,bt.uuid order by pairedtime), pairedtime) >= 180 then 's' --pairedtime
            when lag(pairedtime) over (partition by bt.paireddeviceid,bt.uuid order by pairedtime) is null then 's'
          end as change_flag
  from [dbo].[userevents_bluetooth] bt
  where (bt.uuid = @device  or bt.paireddeviceid = @device) and pairedtime between @starttime and @endtime  
  
),
encounters as
(
select be.uuid, be.paireddeviceid, be.pairedtime, max(f.pairedtime) as encounterstarttime
from [dbo].[userevents_bluetooth] be
right join flagged f on be.uuid = f.uuid and be.paireddeviceid = f.paireddeviceid 
and be.pairedtime between @starttime and @endtime 
where f.pairedtime <= be.pairedtime and f.change_flag = 's'
group by be.uuid, be.paireddeviceid, be.pairedtime
)
,
encounters_summary as
(
select uuid,paireddeviceid,encounterstarttime, 
(select max(pairedtime) from encounters enc_2 where enc_2.uuid = enc.uuid and enc_2.encounterstarttime = enc.encounterstarttime 
and  enc_2.paireddeviceid = enc.paireddeviceid) as encounterendtime
from encounters enc
group by uuid,paireddeviceid,encounterstarttime
)
,
encounters_stats as
(
select uuid,paireddeviceid,encounterstarttime,encounterendtime, 
case 
   when (DATEDIFF(SECOND , encounterstarttime,encounterendtime)) = 0 then 60 
   else (DATEDIFF(SECOND , encounterstarttime,encounterendtime))
end 
duration
-- DATEDIFF(SECOND , encounterstarttime,encounterendtime) duration 
 from encounters_summary 
 )
,
encounters_rssi as
(
 select cs.uuid,cs.paireddeviceid,encounterstarttime,encounterendtime,duration,pairedtime,platform,rssi 
 from encounters_stats cs, userevents_bluetooth bt, userdata ud 
 where 
 cs.uuid=bt.uuid
 and 
 cs.paireddeviceid=bt.paireddeviceid
 and
 ud.uuid=cs.paireddeviceid
 and encounterstarttime<=pairedtime
 and pairedtime<=encounterendtime
 group by cs.uuid,cs.paireddeviceid,encounterstarttime,encounterendtime,duration,pairedtime,rssi,platform 
)

,
encounter_details as
(
select uuid,paireddeviceid,encounterstarttime, duration, 
sum(case when (rssi>=-55 and platform='ios') or (rssi>=-65 and platform='android')  then 1 else 0 end) as very_close_kn,  
sum(case when (rssi>=-65 and platform='ios') or (rssi>=-75 and platform='android') then 1 else 0 end) as close_kn,
count(*) as rssi_length, (select platform from userdata where uuid=er.uuid) platform_a, platform as platform_b
from encounters_rssi er
group by  uuid,paireddeviceid,encounterstarttime,duration,platform
)
select uuid,paireddeviceid,encounterstarttime, duration,duration*(cast(very_close_kn AS float)/rssi_length ) very_close_duration, 
duration*(cast((close_kn-very_close_kn) AS float)/rssi_length ) close_duration
  from encounter_details 

)
