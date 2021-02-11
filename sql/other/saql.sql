/* 
Ok I'll try to explain what's going on here -

We are reading JSON messages from IoT Hub, the messages have an Event JSON array as the main payload,
some IoTHub properties and some headers that describe the device.

As a principle we try to validate the datatype and length so we don't get output data errors. The current
set Stream Analytics error policy is to drop errors (no stopping) and we don't want drops to happen either. 
Validate by: 
1. try casting to correct datatype, NULL if casting fails
2. removing special characters via Javacript UDF "udf.ValidateUserdata"
3. Trimming to correct length

Also we want to scale with paralellism and at the same time get good sized batch inserts to SQL DB, so
we want to pass through data fast and with minimal row processing.

*/
with userdatagrouping as (select count(EventEnqueuedUtcTime) as time,
    iothub.connectiondeviceid as UUID,
  --  PartitionId,
    substring(udf.ValidateUserdata(try_cast(platform as nvarchar(max))),0,99) as platform, 
    substring(udf.ValidateUserdata(try_cast(osVersion as nvarchar(max))),0,99) as osVersion, 
    substring(udf.ValidateUserdata(try_cast(appVersion as nvarchar(max))),0,99) as appVersion, 
    substring(udf.ValidateUserdata(try_cast(model as nvarchar(max))),0,99) as model
    from  [iothub-smittestopp] timestamp by EventEnqueuedUtcTime Partition By PartitionId
     WHERE cast(substring(try_cast(appVersion as nvarchar(max)),1,1) as bigint) >= 1 -- Launch versions
    and appVersion is not null -- At least we need appverson
    group by TumblingWindow(minute,45), iothub.connectiondeviceid, PartitionId, platform, osversion, appversion, model -- 3min groups for decent batchsize, adjust for volume
),
gpsgrouping as (
    SELECT i.iothub.connectiondeviceid as uuid, 
        i.PartitionId,
        substring(try_cast(eventrecords.arrayvalue.timeto as nvarchar(max)),1,18) as rnd_timeto, -- rounding off to nearest 10sec interval
        min(try_cast(eventrecords.arrayvalue.timeto as datetime)) as min_timeto, -- returning the lowest timeto in current 10sec interval
        count(*)
    FROM 
        [iothub-smittestopp] i timestamp by EventEnqueuedUtcTime Partition By PartitionId
    cross apply getarrayelements(events) as eventrecords
    where eventrecords.arrayvalue.latitude is not null -- Eventtype=GPS means it is a GPS payload
                and cast(substring(try_cast(i.appVersion as nvarchar(max)),1,1) as bigint) >= 1 
                and try_cast(eventrecords.arrayvalue.timeto as datetime) <= dateadd(hour,12,i.EventEnqueuedUtcTime) -- timeto should not be higher than eventenqueuedUTCtime+2hr
                and try_cast(eventrecords.arrayvalue.timefrom as datetime) <= dateadd(hour,12,i.EventEnqueuedUtcTime) -- timefrom should not be higher than eventenqueuedUTCtime+2hr
                and try_cast(eventrecords.arrayvalue.timeto as datetime) > cast('2020-04-15' as datetime) -- timeto should not be lower than app launch time
               and try_cast(eventrecords.arrayvalue.timefrom as datetime) > cast('2020-04-15' as datetime) -- timefrom should not be lower than app launch time
    GROUP BY TumblingWindow(minute,15),i.iothub.connectiondeviceid,i.PartitionId,substring(try_cast(eventrecords.arrayvalue.timeto as nvarchar(max)),1,18)
),
bluetoothgrouping as(    
    SELECT j.iothub.connectiondeviceid as uuid, 
    j.PartitionId,
        case when len(eventrecords.arrayvalue.deviceid)=32 then eventrecords.arrayvalue.deviceid 
            else substring(eventrecords.arrayvalue.deviceid,1,36) -- could have done input validation here, but it's only 32 bytes so..
        end as paireddeviceid,
        case when len(try_cast(eventrecords.arrayvalue.time as nvarchar(max)))>28 then '1900-01-01' else 
            substring(try_cast(eventrecords.arrayvalue.time as nvarchar(max)),1,18)
        end as rnd_pairedtime,
        min(case when len(try_cast(eventrecords.arrayvalue.time as nvarchar(max)))>28 then cast('1900-01-01' as datetime) else 
            try_cast(substring(try_cast(eventrecords.arrayvalue.time as nvarchar(max)),1,19) as datetime)
        end) as min_pairedtime
    FROM 
        [iothub-smittestopp] j timestamp by EventEnqueuedUtcTime Partition By PartitionId
    outer apply getarrayelements(events) as eventrecords
    where eventrecords.arrayvalue.deviceid is not null and eventrecords.arrayvalue.deviceid <> ''-- Some messages were arriving without paired deviceid
        and cast(substring(try_cast(j.appVersion as nvarchar(max)),1,1) as bigint) >= 1 
        and try_cast(eventrecords.arrayvalue.time as datetime) <= try_cast(dateadd(hour,12,j.EventEnqueuedUtcTime) as datetime) -- timeto should not be higher than eventenqueuedUTCtime+24hr
        and try_cast(eventrecords.arrayvalue.time as datetime) > try_cast('2020-04-15' as datetime) -- timefrom should not be lower than app launch time
    GROUP BY TumblingWindow(minute,15),j.iothub.connectiondeviceid,j.PartitionId,case when len(try_cast(eventrecords.arrayvalue.time as nvarchar(max)))>28 then '1900-01-01' else 
            substring(try_cast(eventrecords.arrayvalue.time as nvarchar(max)),1,18)
        end, eventrecords.arrayvalue.deviceid
    )
-- Userdata
SELECT uuid, platform, osVersion, appVersion, model
INTO [sql-smittestopp]
FROM userdatagrouping Partition By PartitionId Into 8
-- GPS
select i.iothub.connectiondeviceid as uuid, 
    try_cast(eventrecords.arrayvalue.timefrom as datetime) as timefrom,
    try_cast(eventrecords.arrayvalue.timeto as datetime) as timeto,
     round(try_cast(eventrecords.arrayvalue.latitude as float),6) as latitude, 
        round(try_cast(eventrecords.arrayvalue.longitude as float),6) as longitude,
        round(try_cast(eventrecords.arrayvalue.accuracy as float),3) as accuracy,
        round(try_cast(eventrecords.arrayvalue.speed as float),3) as speed,
        case when round(try_cast(eventrecords.arrayvalue.speedaccuracy as float),3) is null then 0 else round(try_cast(eventrecords.arrayvalue.speedaccuracy as float),3) end as speedaccuracy,
        round(try_cast(eventrecords.arrayvalue.altitude as float),1) as altitude,
        round(try_cast(eventrecords.arrayvalue.altitudeaccuracy as float),1) as altitudeaccuracy,
        datepart(dayofyear,try_cast(eventrecords.arrayvalue.timefrom as datetime)) as daypart
        /*
        datepart(dayofyear,
        case substring(try_cast(case 
            when len(try_cast(eventrecords.arrayvalue.timefrom as nvarchar(max)))>28 then '1900-01-01' 
            else eventrecords.arrayvalue.timefrom 
            end as nvarchar(max)),1,1) 
        when '1' 
            then dateadd(s,case 
                when len(try_cast(eventrecords.arrayvalue.timefrom as nvarchar(max)))>28 then '1900-01-01' 
                else eventrecords.arrayvalue.timefrom 
                end,'1970-01-01T00:00:00') 
        else eventrecords.arrayvalue.timefrom 
        end
        )  as daypart */
    INTO
        [sqlevents-smittestopp]
    from [iothub-smittestopp] i timestamp by EventEnqueuedUtcTime Partition By PartitionId
    join gpsgrouping
    ON (DATEDIFF(second,i,gpsgrouping) BETWEEN 0 AND 40) and gpsgrouping.uuid = i.iothub.connectiondeviceid --and gpsgrouping.PartitionID = i.PartitionID 
    cross apply getarrayelements(i.events) as eventrecords
    where eventrecords.arrayvalue.latitude is not null
        and try_cast(substring(try_cast(i.appVersion as nvarchar(max)),1,1) as bigint) >= 1 
         and try_cast(gpsgrouping.min_timeto as datetime) = try_cast(eventrecords.arrayvalue.timeto as datetime)
-- Bluetooth         
select bluetoothgrouping.uuid,
        case when len(eventrecords.arrayvalue.deviceid)=32 then eventrecords.arrayvalue.deviceid 
            else substring(eventrecords.arrayvalue.deviceid,1,36) 
        end as paireddeviceid,
        try_cast(bluetoothgrouping.min_pairedtime as datetime) as pairedtime,
        try_cast(eventrecords.arrayvalue.rssi as bigint) as rssi, 
        case when try_cast(eventrecords.arrayvalue.txpower as bigint) is null then 0 else try_cast(eventrecords.arrayvalue.txpower as bigint) end as txpower,
            datepart(dayofyear,substring(try_cast(case when len(try_cast(eventrecords.arrayvalue.time as nvarchar(max)))>28 then '1900-01-01'
        else eventrecords.arrayvalue.time end as nvarchar(max)),1,19)) as daypart
    INTO
        [sqlevents-bluetooth-smittestopp]
    from [iothub-smittestopp] i timestamp by EventEnqueuedUtcTime Partition By PartitionId
    join bluetoothgrouping
        ON (DATEDIFF(second,i,bluetoothgrouping) BETWEEN 0 AND 40) and bluetoothgrouping.uuid = i.iothub.connectiondeviceid --and bluetoothgrouping.PartitionID = i.PartitionID
    cross apply getarrayelements(i.events) as eventrecords
    where eventrecords.arrayvalue.deviceid is not null and eventrecords.arrayvalue.deviceid <> ''
        and try_cast(bluetoothgrouping.min_pairedtime as datetime) = try_cast(eventrecords.arrayvalue.time as datetime) 
        and bluetoothgrouping.paireddeviceid = eventrecords.arrayvalue.deviceid
        and try_cast(substring(try_cast(i.appVersion as nvarchar(max)),1,1) as bigint) >= 1 ;


