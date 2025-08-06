# iCloud Sync for Just Press Record

This guide explains how to sync your Just Press Record audio files from iCloud Drive to your local machine so the transcription pipeline can process them.

## On macOS

1. **Enable iCloud Drive for Just Press Record**
   - Open **System Settings** (or **System Preferences**) > **Apple ID** > **iCloud Drive**.
   - Click **Options** next to **iCloud Drive**.
   - Ensure **Just Press Record** folder is selected (or that iCloud Drive syncs your Documents folder where Just Press Record stores recordings).

2. **Locate the local iCloud Drive folder**
   - The local path is typically:
     ```
     ~/Library/Mobile Documents/com~apple~CloudDocs/Just Press Record
     ```

3. **Verify files are synced locally**
   - Open Finder and navigate to the path above.
   - Wait for any pending uploads/downloads to complete.

4. **Configure the pipeline**
   - In your `.env` file, set the `AUDIO` variable to this path:
     ```env
     AUDIO="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Just Press Record"
     ```

## On other platforms

If you are using a non-macOS system, you can use third-party tools like `rclone` to sync your iCloud Drive Just Press Record folder:

```bash
# Install rclone and configure a remote called 'icloud'
rclone config

# Sync the Just Press Record folder to a local directory
rclone sync icloud:"Just Press Record" /path/to/local/audio
```

Then set the `AUDIO` variable in your `.env` file to `/path/to/local/audio`.
