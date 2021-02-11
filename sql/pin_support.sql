-- Create table:
create table dbo.PINcodes (
  id int primary key identity(1,1) not null, 
  msisdn char(16) not null, 
  pin char(10) not null,
  created_at datetime2(0) not null
)

-- Create procedure for inserting rows (id is auto increment) 
create procedure dbo.insertPinCode
(
	@msisdn char(16), 
	@pin char(10),
	@created_at datetime2(0)
)
as
insert into dbo.PINcodes(msisdn, pin, created_at) values (@msisdn, @pin, @created_at) 

-- Create function for getting pin codes by phone number (msisdn)
create function dbo.getPinCodesByPhoneNumber
(
	@msisdn char(16)
)
returns table
as
return
(select pin, created_at from PINcodes where msisdn = @msisdn)

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



-- GRANTS
--dev
grant select on dbo.getPinCodesByPhoneNumber to [FHI-Smittestopp-ServiceAPI-Dev];
grant select on dbo.getPinCodeNewestEntryByThreshold to [FHI-Smittestopp-ServiceAPI-Dev];
grant execute on dbo.insertPinCode to [FHI-Smittestopp-ServiceAPI-Dev];

grant select on dbo.getPinCodesByPhoneNumber to [FHI-Smittestopp-Registration-Dev];
grant select on dbo.getPinCodeNewestEntryByThreshold to [FHI-Smittestopp-Registration-Dev];

--prod
grant select on dbo.getPinCodesByPhoneNumber to [FHI-Smittestopp-ServiceAPI-Prod];
grant select on dbo.getPinCodeNewestEntryByThreshold to [FHI-Smittestopp-ServiceAPI-Prod];
grant execute on dbo.insertPinCode to [FHI-Smittestopp-ServiceAPI-Prod];

grant select on dbo.getPinCodesByPhoneNumber to [FHI-Smittestopp-Registration-Prod];
grant select on dbo.getPinCodeNewestEntryByThreshold to [FHI-Smittestopp-Registration-Prod];




