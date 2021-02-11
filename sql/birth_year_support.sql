-- Create table to hold birth year and uuid
create table dbo.BirthYear(
    uuid varchar(36) primary key,
    birthyear smallint not null,
)


-- Create procedure to upsert birthYear 
create procedure dbo.upsertBirthYear(
    @uuid varchar(36),
    @birthyear smallint
) as
        if exists (select 1 from dbo.BirthYear where uuid = @uuid)
            update dbo.BirthYear
            set birthyear = @birthyear
            where uuid = @uuid
        else
            insert into dbo.birthyear(uuid, birthyear)
            values(@uuid, @birthyear)
    
-- Create function to get birth year by uuid 
create function [dbo].[getBirthYear]
(
                @uuid varchar(36)
)
returns table
as
return
(select birthyear from dbo.birthyear where uuid = @uuid)

-- Grants: 

grant select on dbo.getBirthYear to [FHI-Smittestopp-ServiceAPI-Dev];
grant execute on dbo.upsertBirthYear to [FHI-Smittestopp-Registration-Dev];



