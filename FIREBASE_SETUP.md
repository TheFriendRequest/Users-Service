# Firebase Authentication Setup Guide

## Overview
This service uses Firebase Authentication for user login (Google Sign-In) while maintaining all user data, relationships, and business logic in your MySQL database.

## Architecture

```
┌─────────────┐
│  Frontend   │ → Firebase Auth (Google Sign-In)
│  (React)    │ → Gets Firebase ID Token
└──────┬──────┘
       │
       │ Bearer Token (Firebase ID Token)
       ▼
┌─────────────┐
│Users Service│ → Verifies Firebase Token
│  (FastAPI)  │ → Maps Firebase UID → user_id
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   MySQL DB  │ → Stores user profiles, friendships, schedules
└─────────────┘
```

## Setup Steps

### 1. Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project"
3. Enter project name and follow the setup wizard
4. Enable Google Authentication:
   - Go to Authentication > Sign-in method
   - Enable "Google" provider
   - Add authorized domains if needed

### 2. Get Firebase Configuration

1. In Firebase Console, go to Project Settings > General
2. Scroll to "Your apps" section
3. Click on the Web icon (`</>`) to add a web app
4. Copy the Firebase configuration object

### 3. Backend Setup (Users Service)

#### Option A: Local Development

1. Create a service account key:
   - Go to Firebase Console > Project Settings > Service Accounts
   - Click "Generate new private key"
   - Save the JSON file securely

2. Set environment variable:
   ```bash
   export FIREBASE_SERVICE_ACCOUNT_PATH="/path/to/serviceAccountKey.json"
   ```

3. Update `auth.py` to use the service account:
   ```python
   cred = credentials.Certificate(os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH"))
   firebase_admin.initialize_app(cred)
   ```

#### Option B: Cloud Run Deployment

1. When deployed on Cloud Run, Firebase Admin SDK can use Application Default Credentials (ADC)
2. Make sure your Cloud Run service has the necessary IAM permissions
3. The code will automatically detect `GOOGLE_CLOUD_PROJECT` environment variable

### 4. Frontend Setup

1. Create `.env` file in `frontend-service/`:
   ```env
   REACT_APP_FIREBASE_API_KEY=your_api_key
   REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   REACT_APP_FIREBASE_PROJECT_ID=your-project-id
   REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
   REACT_APP_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
   REACT_APP_FIREBASE_APP_ID=your_app_id
   REACT_APP_USERS_SERVICE_URL=http://localhost:8000
   ```

2. Install dependencies:
   ```bash
   cd frontend-service
   npm install
   ```

### 5. Database Migration

Run the updated `init.sql` to add the `firebase_uid` column to the Users table:

```sql
ALTER TABLE Users ADD COLUMN firebase_uid VARCHAR(128) UNIQUE NOT NULL AFTER user_id;
```

Or recreate the database with the updated schema.

## How It Works

### User Flow

1. **First Login:**
   - User clicks "Sign in with Google" on frontend
   - Firebase authenticates user and returns Firebase ID token
   - Frontend calls `/users/sync` endpoint with user profile data
   - Backend verifies Firebase token, extracts `firebase_uid`
   - Backend creates new user record in database with `firebase_uid`

2. **Subsequent Logins:**
   - User signs in with Google
   - Frontend gets Firebase ID token
   - All API calls include `Authorization: Bearer <token>` header
   - Backend verifies token and maps `firebase_uid` to `user_id`
   - User can access all authenticated endpoints

### API Endpoints

- `POST /users/sync` - Sync Firebase user to database (called after first login)
- `GET /users/me` - Get current authenticated user's profile
- `GET /users` - Get all users (requires authentication)
- `GET /users/{username}` - Get user by username (requires authentication)
- `PUT /users/{user_id}` - Update user (can only update own profile)
- `DELETE /users/{user_id}` - Delete user (can only delete own account)

All endpoints except `/users/sync` require Firebase authentication via Bearer token.

## Security Notes

1. **Token Verification:** Always verify Firebase tokens on the backend. Never trust client-side tokens alone.

2. **Authorization:** Even with Firebase Auth, you still need to implement authorization:
   - Users can only update/delete their own profiles
   - Friend requests can only be sent by authenticated users
   - Schedule/event access should be restricted appropriately

3. **Environment Variables:** Never commit Firebase credentials or service account keys to version control.

4. **CORS:** Configure CORS properly in your FastAPI service to allow requests from your frontend domain.

## Testing

1. Start the Users Service:
   ```bash
   cd Users-Service
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

2. Start the Frontend:
   ```bash
   cd frontend-service
   npm start
   ```

3. Test the flow:
   - Open http://localhost:3000
   - Click "Sign in with Google"
   - Complete Google authentication
   - Verify user is created in database
   - Check that token is stored and used in subsequent requests

## Troubleshooting

### "Firebase initialization warning"
- Make sure you've set up Firebase credentials (service account or ADC)
- Check that environment variables are set correctly

### "Invalid Firebase token"
- Token may be expired - refresh the token
- Check that the token is being sent in the Authorization header correctly

### "User not found in database"
- Make sure `/users/sync` endpoint was called after first login
- Check that `firebase_uid` is being stored correctly in database

### CORS errors
- Add your frontend URL to CORS allowed origins in `main.py`
- Check that the Users Service is running and accessible

