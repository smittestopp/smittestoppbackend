

CREATE TABLE [dbo].[uuid_rotating](
	[uuid] [varchar](36) NULL,
	[new_uuid] [char](32) NOT NULL,
	[created] [datetime2](0) NULL
) ON [PRIMARY]
GO

ALTER TABLE [dbo].[uuid_rotating] ADD  DEFAULT (getdate()) FOR [created]
GO

CREATE proc [dbo].[getnewuuids](@uuid varchar(36), @howmany int=100)
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
GO

grant execute on dbo.getnewuuids to [FHI-Smittestopp-Registration-Dev]
