# Firebase Backend Setup - Step by Step Guide

## Step 1: Download Service Account Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project: **cloud-project-7a745**
3. Click the gear icon ⚙️ (Settings) in the left sidebar
4. Click **"Project settings"**
5. Go to the **"Service accounts"** tab
6. Click **"Generate new private key"** button
7. Click **"Generate key"** in the popup (this downloads a JSON file)
8. Save the file in a secure location, e.g.:
   - `C:\Users\madha\Documents\Cloud Computing\Project\Users-Service\serviceAccountKey.json`
   - **IMPORTANT:** Never commit this file to Git! It's already in .gitignore

## Step 2: Set Environment Variable (Windows PowerShell)

Open PowerShell and run:

```powershell
# Navigate to your project
cd "C:\Users\madha\Documents\Cloud Computing\Project\Users-Service"

# Set environment variable (replace path with your actual path)
$env:FIREBASE_SERVICE_ACCOUNT_PATH="C:\Users\madha\Documents\Cloud Computing\Project\Users-Service\serviceAccountKey.json"

# Verify it's set
echo $env:FIREBASE_SERVICE_ACCOUNT_PATH
```

**Note:** This only sets it for the current PowerShell session. For permanent setup, see Step 3.

## Step 3: Create .env File (Recommended)

Create a file `Users-Service/.env` with:

```env
FIREBASE_SERVICE_ACCOUNT_PATH=C:\Users\madha\Documents\Cloud Computing\Project\Users-Service\serviceAccountKey.json
DB_HOST=127.0.0.1
DB_USER=root
DB_PASS=your_mysql_password
DB_NAME=friend_request_db
```

Replace `your_mysql_password` with your actual MySQL password.

## Step 4: Update auth.py

The code will automatically use the service account if `FIREBASE_SERVICE_ACCOUNT_PATH` is set.

## Step 5: Test

Run your service:
```powershell
cd "C:\Users\madha\Documents\Cloud Computing\Project\Users-Service"
uvicorn main:app --reload
```

You should see the service start without Firebase initialization warnings.

