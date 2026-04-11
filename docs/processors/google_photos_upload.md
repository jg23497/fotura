# Google Photos Upload

Two processors are available for uploading photos to Google Photos, which both share the same OAuth2 authentication setup.

## After-each processor

Uploads each photo individually as soon as it has been moved to its target location.

```
fotura import --after-each "google_photos_upload" ~/Pictures/unsorted ~/Pictures/organized
```

## After-all processor

Uploads all photos in batches after the full import is complete. This is more efficient for large imports as it parallelises byte uploads and uses the Google Photos Batch Create API.

```
fotura import --after-all "google_photos_upload_batch" ~/Pictures/unsorted ~/Pictures/organized
```

### Parameters

| Parameter     | Default | Range | Description                                 |
| ------------- | ------- | ----- | ------------------------------------------- |
| `concurrency` | 2       | 1–5   | Number of concurrent byte uploads           |
| `batch_size`  | 10      | 1–50  | Number of photos per batch creation request |

```
fotura import --after-all "google_photos_upload_batch:concurrency=3,batch_size=20" ~/Pictures/unsorted ~/Pictures/organized
```

Both processors are resumable via the `processor resume` command, in the case of failed or interrupted uploads:

```
fotura processor resume google_photos_upload
fotura processor resume google_photos_upload_batch
```

## Configuration

To use either processor, you must configure a Google Cloud project and enable the Google Photos Library API.

### Step 1: Obtain your personal Google Photos API credentials

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/) and [create a new project](https://console.cloud.google.com/projectcreate) or select an existing one.
2. Enable the [Google Photos Library API](https://console.cloud.google.com/apis/library/photoslibrary.googleapis.com) (click 'Enable API').
3. Go to the [Credentials page](https://console.cloud.google.com/apis/credentials?), click [Create credentials](https://console.cloud.google.com/auth/clients/create) and then 'Create OAuth client ID'.
4. On the Application type screen, choose 'Desktop app' and provide a name (e.g. "Fotura"), and then click 'Create'.
5. A dialog box will appear with your client ID and client secret. Click 'Download JSON'.

Note: Using the [Google Auth Platform - Audience](https://console.cloud.google.com/auth/audience) page, you may also need to set the project's 'Publishing status' to 'Testing' and then add your Google account to the test users list to allow the OAuth flow to succeed.

### Step 2: Save the credentials file

1. The downloaded JSON file contains your application's credentials. Rename this file to `client_secret.json` and place it under your user config directory, creating the subdirectories shown below as needed:
   - Linux: `~/.config/fotura/integrations/google_photos`
   - MacOS: `~/Library/Application Support/fotura/integrations/google_photos`
   - Windows: `%LocalAppData%\fotura\fotura\integrations\google_photos`

   Or attempt to use the processor without providing the file and check the path it provides in its error message.

### Step 3: Authenticate

1. The first time you run either processor, it will initiate the OAuth authentication flow.
2. A browser window will open, prompting you to sign in to your Google account and grant Fotura permission to upload photos.
3. After you approve the permissions, the application will receive a token. This token is saved as `token.json` in the user config directory:
   - Linux: `~/.config/fotura/integrations/google_photos/token.json`
   - MacOS: `~/Library/Application Support/fotura/integrations/google_photos/token.json`
   - Windows: `%LocalAppData%\fotura\fotura\integrations\google_photos\token.json`
4. Subsequent runs will use this cached token for authentication, so you will not need to re-authenticate unless the token expires or is manually revoked.
