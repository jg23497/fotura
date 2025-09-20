# For v1.0

* Allow auto-deletion of token.json if it has expired and cannot be refreshed.
* Let the report's filename include the run's timestamp.
* Improve unit test coverage in general:
  * ExifUtils
  * FilenameTimestampExtractPreprocessor
  * Report creation
* Allow selection of the file name conflict resolution strategy.
* Allow dry run mode to plan conflict resolutions without relying on the file system.
* Check we have read/write permissions on the source and destination directories.