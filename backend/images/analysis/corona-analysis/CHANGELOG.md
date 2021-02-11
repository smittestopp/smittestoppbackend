# Smittestopp Analytics Pipeline Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [2.4.3] - 2020-06-15
### Removed
- Remove obsolete copy of file `output_structure.json`

### Fixed
- Import missing `contextmanager`


## [2.4.2] - 2020-06-15
### Added
- Add additional logging to capture the duration of database connection and queries in runtime

### Changed
- Remove obsolete UUIDs from pipeline tests
- Retry SQL queries multiple times, using exponential waiting time in case of subsequent failures


## [2.4.1] - 2020-06-03
### Added
- Add request identifier to log messages


## [2.4.0] - 2020-05-27
### Added
- Add logging of non-sensitive configuration parameters

### Changed
- Reduce number of calls to the OSM Overpass API
- Update UUID in unit tests to `dd84433a729411ea80ea42a51fad92d3`
- Update documents `DEVELOPMENT_GUIDELINES.md` and `RELEASE_GUIDELINES.md`


## [2.3.2] - 2020-05-23
### Changed
- Retry all SQL queries 5 times before giving up


## [2.3.1] - 2020-05-19
### Added
- Add config option to enable/disable device information lookup


## [2.3.0] - 2020-05-18
### Added
- Show device information (platform, model, app version) in JSON output and reports

### Changed
- Increase the search radius for POIs around a point based GPS accuracy and transport mode

### Fixed
- Fix zooming when contacts are not clustered
- Fix parsing of the input configuration file (overwrites, type-checking, and quotation)


## [2.2.5] - 2020-05-14
### Changed
- Update rule for categorizing a contact as "inside transport"

### Fixed
- Fix logic in "gps_only" risk score


## [2.2.4] - 2020-05-14
### Fixed
- Filter contacts after splitting by days in order to remove empty or single-point contacts


## [2.2.3] - 2020-05-13
### Changed
- Revert using of persistent database connections


## [2.2.2] - 2020-05-13
### Changed
- Improve the efficiency of database queries by using persistent connection
- Refactor configuration to make it easier to introduce new options
- Update `DEVELOPMENT_GUIDELINES.md` document

### Fixed
- Handle type error in median distance calculation
- Do not silently ignore OSM query errors


## [2.2.1] - 2020-05-11
### Changed
- Update FHI criteria for GPS contacts
- Update GPS trajectory splitting parameters to reduce the number of SQL queries


## [2.2.0] - 2020-05-11
### Changed
- Show a second map for trajectories that zooms into the contact area
- Update POI algorithm
- Improve computation of contact duration

### Fixed
- Fix wrongly displayed sub-duration of contacts, to correctly add up to total duration of contacts
- Interpolate GPS trajectories for BT contacts to contact times, so that we can always show red contact markers on maps


## [2.1.4] - 2020-05-10
### Fixed
- Gracefully handle case when patient's GPS trajectory is empty


## [2.1.3] - 2020-05-09
### Changed
- Use dynamic sizes for bounding boxes to avoid too many SQL queries when the patient is moving
- Stop using `pprint` in logging to improve searchability in logs


## [2.1.2] - 2020-05-08
### Removed
- Disable device information query


## [2.1.1] - 2020-05-08
### Added
- Add more logging messages


## [2.1.0] - 2020-05-08
### Added
- Add GPS contacts
- Show device information (platform, model, app version) in JSON output and reports

### Changed
- Update GPS contact algorithm so that it is faster
- Update filter to show GPS contacts longer than 30min even without BT contact
- Switch off FHI filter for individual reports

### Fixed
- Fix the display of "short" bar plots by finer axis formating


## [1.4.0] - 2020-05-07
### Added
- Add field to JSON output called `days_in_contact`, indicating the number of days in which a UUID has had contact with another

### Changed
- Update `cartopy`-related requirements
- Improve POI detection
- Improve BT contacts

### Fixed
- Fix error in handling special GPS contact cases


## [1.3.3] - 2020-05-06
### Removed
- Remove unused import from `plotly`


## [1.3.2] - 2020-05-06
### Removed
- Remove update of BT contacts


## [1.3.1] - 2020-05-06
### Changed
- Change from static maps based on `plotly` to based on `cartopy`
- Improve BT contacts


## [1.3.0] - 2020-05-05
### Added
- Add support for static maps
- Add more logging of OSM activitiy
- Add reference JSON output to repository
- Add data aggregation categories
- Add analytics pipeline version to JSON output

### Changed
- Change from interactive to static maps by default
- Improve POI algorithm (PR #110)

### Removed
- Deactivate GPS contacts

### Fixed
- Fix attempt for histogram plots where BT contacts are not displayed


## [2.0.1] - 2020-05-02
### Fixed
- Fix GPS contacts


## [2.0.0] - 2020-05-01
### Added
- Add GPS contacts
- Add more unit tests

### Removed
- Remove debugging statements


## [1.2.0] - 2020-05-01
### Changed
- Update the distance threshold for BT contacts from 15m to 2m
- Update handling of POI queries to be more robust


## [1.1.0] - 2020-04-30
### Added
- Add Point of Interest (POI) detection
- Add GPS location for BT contacts
- Add debug information for testing on production
- Add functionality to subsample consecutive GPS events with respect to distance and time
- Add bar plots to contact list (new figure in risk report)
- Add BT contact duration to internal report, with new keys in daily dict (`close_duration`, `very_close_duration`, `relative_duration`)
- Add uniform logging throughout the pipeline with `corona.logger`
- Add analytics pipeline version to logging format
- Add `DEBUG` flag to toggle default logging level
- Add logging if a contact matches FHI requirements

### Changed
- Update package name and description
- Update BT device filtering rules
- Update risk score threshold
- Update parameter dictionary

### Removed
- Remove hardcoded congifuration information for OSM servers
- Remove unused SQL queries


## [1.0.0] - 2020-04-27
### Added
- Given a UUID, the analytics pipeline queries the BT contacts of this UUID and provides a JSON output containing a risk analysis. Only contacts of at least 15min will be reported
