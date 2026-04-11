# Fotura

<img src="./docs/images/logo.png" width="200px" alt="Fotura logo"/>

**A Python CLI for importing, organizing, and uploading your photos.**

[![Python CI](https://github.com/jg23497/fotura/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/jg23497/fotura/actions/workflows/main.yml)

Fotura moves photos from a source directory into a clean, date-organised folder structure. It extracts timestamps from EXIF metadata and filenames, resolves conflicts, and can upload directly to Google Photos, all from a single command.

![Fotura pipeline flow diagram](./docs/images/pipeline-flow-diagram.png)

## Installation

> **Note:** Fotura is not yet published to PyPI. Until then, please follow the [development setup instructions](docs/development.md) to install from source.

```bash
pipx install fotura
```

## Usage

```bash
fotura import ~/Pictures/unsorted ~/Pictures/organized
```

Always preview first with `--dry-run`:

```bash
fotura import ~/Pictures/unsorted ~/Pictures/organized --dry-run --open-report
```

<img src="./docs/images/report-example.png" width="600px" alt="Example report"/>

## Processors

Processors extend the import pipeline. Specify them with `--before-each`, `--after-each`, or `--after-all`. Multiple processors can be chained by repeating the flag.

Before-each processors run prior to a photo being moved. They extract facts, such as a timestamp from a filename, which inform how the photo is routed and processed.

### Filename Timestamp Extract

Extracts timestamps from WhatsApp and Android filenames and writes them back into EXIF metadata.

```bash
fotura import --before-each "filename_timestamp_extract" ~/Pictures/unsorted ~/Pictures/organized
```

### Google Photos Upload

Uploads each photo to Google Photos as it is moved. See the [full documentation](./docs/processors/google_photos_upload.md) for setup.

```bash
fotura import --after-each "google_photos_upload" ~/Pictures/unsorted ~/Pictures/organized
```

### Google Photos Batch Upload

Uploads in parallel after the full import completes, using the Google Photos batch API for efficiency.

```bash
fotura import --after-all "google_photos_upload_batch" ~/Pictures/unsorted ~/Pictures/organized
fotura import --after-all "google_photos_upload_batch:concurrency=3,batch_size=20" ~/Pictures/unsorted ~/Pictures/organized
```

| Parameter     | Default | Range | Description                       |
| ------------- | ------- | ----- | --------------------------------- |
| `concurrency` | 2       | 1–5   | Parallel byte uploads             |
| `batch_size`  | 10      | 1–50  | Photos per batch creation request |

Both Google Photos processors are resumable. Interrupted or failed uploads can be retried without re-uploading photos that already succeeded:

```bash
fotura processor resume google_photos_upload
fotura processor resume google_photos_upload_batch
```

## Options

| Option                 | Description                                             |
| ---------------------- | ------------------------------------------------------- |
| `--dry-run`            | Preview changes without moving files                    |
| `--open-report`        | Open the HTML report in a browser after import          |
| `--before-each`        | Processor to run per photo before moving                |
| `--after-each`         | Processor to run per photo after moving                 |
| `--after-all`          | Processor to run once after all photos are processed    |
| `--conflict-strategy`  | How to handle filename collisions (`keep_both`, `skip`) |
| `--target-path-format` | Date format for the target directory structure          |

### Path format

Photos are organised into `%Y/%Y-%m` by default (e.g. `2023/2023-05`). Override with `--target-path-format` using [Python date format codes](https://docs.python.org/3/library/datetime.html#format-codes):

| Style              | Format              | Example                               |
| ------------------ | ------------------- | ------------------------------------- |
| Year / Month       | `%Y/%m`             | `2008/05/example.jpg`                 |
| Year / Month name  | `%Y/%B`             | `2008/May/example.jpg`                |
| Year-Month flat    | `%Y-%m`             | `2008-05/example.jpg`                 |
| Year / Month / Day | `%Y/%m/%d`          | `2008/12/25/example.jpg`              |
| Daily folders      | `%Y/%Y-%m/%Y-%m-%d` | `2008/2008-05/2008-05-30/example.jpg` |

### Conflict resolution

- `keep_both`: appends a numeric suffix to the incoming file (`photo_1.jpg`, `photo_2.jpg`, …)
- `skip`: leaves the existing file in place and skips the incoming one

## Coming soon

- Stripping location data from EXIF.
- Flagging low-quality images (blurry, over/under-exposed, duplicates).
- Image labelling via a multimodal LLM.

## Development

See [Development](docs/development.md).
