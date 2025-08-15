# Google Photos Upload Postprocessor

This post-processor automates the process of uploading images to a user's Google Photos library after they have been processed by PhotoTidy.

## Features
* Automated Upload: Automatically uploads supported image files to your Google Photos account.
* OAuth 2.0 Integration: Securely authenticates with the Google Photos Library API using the OAuth 2.0 protocol for desktop applications.
* Token Management: Manages the entire OAuth lifecycle, including obtaining, caching, and refreshing access tokens.
* Dry-Run Mode: Supports a dry-run feature to simulate the upload process without actually sending any data.

## Usage

`--postprocessors "google_photos_upload"`

## Configuration
To use this post-processor, you must configure a Google Cloud project and enable the Google Photos Library API.

### Step 1: Obtain your personal Google Photos API credentials
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/) and [create a new project](https://console.cloud.google.com/projectcreate) or select an existing one.
2. Enable the [Google Photos Library API](https://console.cloud.google.com/apis/library/photoslibrary.googleapis.com) (click 'Enable API').
3. Go to the [Credentials page](https://console.cloud.google.com/apis/credentials?), click [Create credentials](https://console.cloud.google.com/auth/clients/create) and then 'Create OAuth client ID'.
5. On the Application type screen, choose 'Desktop app' and provide a name (e.g. "PhotoTidy"), and then click 'Create'.
6. A dialog box will appear with your client ID and client secret. Click 'Download JSON'.

Note: Using the [Google Auth Platform - Audience](https://console.cloud.google.com/auth/audience) page, you may also need to set the project's 'Publishing status' to 'Testing' and then add your Google account to the 'Test users' list to allow the OAuth flow to succeed.

### Step 2: Save the credentials File
1. The downloaded JSON file contains your application's credentials. Rename this file to `client_secret.json` and place it in a folder named `.secrets` within your PhotoTidy application directory. The expected path is: `.secrets/client_secret.json`.
2. Alternatively, you can specify a different location for this file by setting the `GOOGLE_CREDENTIALS_FILE` environment variable.

### Step 3: Run the post-processor
1. The first time you run the post-processor, it will initiate the OAuth authentication flow.
2. A browser window will open, prompting you to sign in to your Google account and grant PhotoTidy permission to upload photos.
3. After you approve the permissions, the application will receive a token. This token is securely saved as `token.json` in the `.secrets` directory. The expected path is: `.secrets/token.json`.
4. Subsequent runs will use this cached token for authentication, so you will not need to re-authenticate unless the token expires or is manually revoked. You can change the location of this file using the `GOOGLE_TOKEN_FILE` environment variable.