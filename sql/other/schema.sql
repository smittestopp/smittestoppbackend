-- ##########################################################################
-- #### Extensions                                                       ####
-- ##########################################################################

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_partman;


-- ##########################################################################
-- #### Identification                                                   ####
-- ##########################################################################

-- ====== Table =============================================================
CREATE TABLE PhoneNumbers (
   UserID             UUID                        NOT NULL,    -- UUID
   PhoneNumber        CHARACTER(16)               NOT NULL,    -- phone number
   PRIMARY KEY (UserID)
);


-- ##########################################################################
-- #### Positioning                                                      ####
-- ##########################################################################

-- ====== Table =============================================================
CREATE TABLE PositionEvents (
   UserID             UUID                        NOT NULL,    -- UUID
   TimeStamp          TIMESTAMP WITHOUT TIME ZONE NOT NULL,    -- Time Stamp

   GridID             BIGINT                      NOT NULL,    -- Grid ID
   Location           geometry(Point, 4326)       NOT NULL,    -- (longitude,latitude)
   LocationAccuracy   SMALLINT                    NOT NULL,    -- Location accuracy in m
   Altitude           SMALLINT                    NOT NULL,    -- Altitude in m
   AltitudeAccuracy   SMALLINT                    NOT NULL,    -- Altitude accuracy in m

   AccelerometerX     SMALLINT,                                -- Speed in m/s ???
   AccelerometerY     SMALLINT,                                -- Speed in m/s ???
   AccelerometerZ     SMALLINT,                                -- Speed in m/s ???

   GyroscopeX         SMALLINT,                                -- Gyroscope in ???
   GyroscopeY         SMALLINT,                                -- Gyroscope in ???
   GyroscopeZ         SMALLINT,                                -- Gyroscope in ???

   GravityX           SMALLINT,                                -- Gravity in ???
   GravityY           SMALLINT,                                -- Gravity in ???
   GravityZ           SMALLINT,                                -- Gravity in ???

   LinAccelerationX   SMALLINT,                                -- LinearAcceleration in ???
   LinAccelerationY   SMALLINT,                                -- LinearAcceleration in ???
   LinAccelerationZ   SMALLINT,                                -- LinearAcceleration in ???

   PRIMARY KEY (UserID, TimeStamp)
);

-- ====== Partitioning ======================================================
-- Create partitioning. Note: table and fields must be in lowercase!
SELECT create_parent('public.positionevents', 'timestamp', 'partman', 'daily');
SELECT create_sub_parent('public.positionevents', 'gridid', 'partman', '10');   -- One partition per 10 GridID values!


-- ##########################################################################
-- #### Bluetooth                                                        ####
-- ##########################################################################

-- ====== Table =============================================================
CREATE TYPE BluetoothStatus AS ENUM (
   'device_seen',             -- The device appeared
   'device_disappeared',      -- The device disappeared
   'device_connected_to'      -- Contact established
);

DROP TABLE IF EXISTS BluetoothEvents;
CREATE TABLE BluetoothEvents (
   UserID             UUID                        NOT NULL,    -- UUID
   TimeStamp          TIMESTAMP WITHOUT TIME ZONE NOT NULL,    -- Time Stamp

   GridID             BIGINT                      NOT NULL,    -- Grid ID
   Location           geometry(POINT, 4326)       NOT NULL,    -- (longitude,latitude)
   LocationAccuracy   SMALLINT                    NOT NULL,    -- Location accuracy in m
   Altitude           SMALLINT                    NOT NULL,    -- Altitude in m
   AltitudeAccuracy   SMALLINT                    NOT NULL,    -- Altitude accuracy in m

   MAC                MACADDR,                                 -- Bluetooth device MAC address
   DeviceName         CHARACTER VARYING(248),                  -- Bluetooth device name
   Status             BluetoothStatus             NOT NULL,    -- Bluetooth device status
--    Signal
--    (what else?)

   PRIMARY KEY (UserID, TimeStamp)
);

-- ====== Indexes ===========================================================
-- ??? Index on MAC, to find users having seen a certain MAC address?
CREATE INDEX BluetoothEventsMACIndex ON BluetoothEvents (MAC ASC);
-- ??? Index on DeviceName, to find users having seen a certain device name?
-- NOTE: This will consume significant space (DeviceName may have up to 248 bytes)!
-- CREATE INDEX BluetoothEventsDeviceNameIndex ON BluetoothEvents (DeviceName ASC);

-- ====== Partitioning ======================================================
-- Create partitioning. Note: table and fields must be in lowercase!
SELECT create_parent('public.bluetoothevents', 'timestamp', 'partman', 'daily');
SELECT create_sub_parent('public.bluetoothevents', 'gridid', 'partman', '10');   -- One partition per 10 GridID values!


-- ##########################################################################
-- #### Wi-Fi                                                            ####
-- ##########################################################################

-- ====== Table =============================================================
CREATE TYPE WiFiStatus AS ENUM (
   'network_seen',             -- The network appeared
   'network_disappeared',      -- The network disappeared
   'network_connected_to'      -- Contact established
);

DROP TABLE IF EXISTS WiFiEvents;
CREATE TABLE WiFiEvents (
   UserID             UUID                        NOT NULL,    -- UUID
   TimeStamp          TIMESTAMP WITHOUT TIME ZONE NOT NULL,    -- Time Stamp

   GridID             BIGINT                      NOT NULL,    -- Grid ID
   Location           geometry(POINT, 4326)       NOT NULL,    -- (longitude,latitude)
   LocationAccuracy   SMALLINT                    NOT NULL,    -- Location accuracy in m
   Altitude           SMALLINT                    NOT NULL,    -- Altitude in m
   AltitudeAccuracy   SMALLINT                    NOT NULL,    -- Altitude accuracy in m

   ESSID              CHARACTER(32)               NOT NULL,    -- Wi-Fi AP's ESSID
   MAC                MACADDR                     NOT NULL,    -- Wi-Fi AP's MAC address
   Status             WiFiStatus                  NOT NULL,    -- Wi-Fi network status
--    Signal                                             -- Signal strength
--    (what else?)

   PRIMARY KEY (UserID, TimeStamp)
);

-- ====== Indexes ===========================================================
-- ??? Index on MAC, to find users having seen a certain MAC address?
CREATE INDEX WiFiEventsMACIndex   ON WiFiEvents (MAC ASC);
-- ??? Index on ESSID, to find users having seen a certain ESSID address?
-- NOTE: This will consume significant space (each ESSID has 32 bytes)!
-- CREATE INDEX WiFiEventsESSIDIndex ON WiFiEvents (MAC ASC);

-- ====== Partitioning ======================================================
-- Create partitioning. Note: table and fields must be in lowercase!
SELECT create_parent('public.wifievents', 'timestamp', 'partman', 'daily');
SELECT create_sub_parent('public.wifievents', 'gridid', 'partman', '10');   -- One partition per 10 GridID values!
