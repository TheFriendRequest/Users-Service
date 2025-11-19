# Where to Store Firebase Service Account Key

## Recommended Location

**Store the key file here:**
```
Users-Service/serviceAccountKey.json
```

## Why This Location?

1. ✅ **Same directory as your code** - Easy to reference
2. ✅ **Protected by .gitignore** - Won't be committed to Git
3. ✅ **Simple path** - Easy to set in .env file

## Setup Steps

1. **Download the key** from Firebase Console
2. **Save it as:** `Users-Service/serviceAccountKey.json`
3. **Update `.env` file** with:
   ```
   FIREBASE_SERVICE_ACCOUNT_PATH=C:\Users\madha\Documents\Cloud Computing\Project\Users-Service\serviceAccountKey.json
   ```

## Security Notes

⚠️ **IMPORTANT:**
- ✅ The key file is automatically ignored by Git (`.gitignore` created)
- ✅ Never commit this file to version control
- ✅ Never share this file publicly
- ✅ Keep it secure on your local machine only

## Alternative Locations (if needed)

If you prefer to keep it outside the project:
- `C:\Users\madha\Documents\firebase-keys\serviceAccountKey.json`
- Then update `.env` path accordingly

