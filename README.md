# Users Service

Microservice responsible for user management, profiles, interests, and user-related operations.

## 📋 Overview

The Users Service handles all user-related functionality including:
- User registration and profile management
- User search and discovery
- Interest management
- User synchronization with Firebase
- Profile picture management

## 🏗️ Architecture

```
API Gateway → Composite Service → Users Service → User Database (Cloud SQL)
```

- **Port**: 8001
- **Database**: MySQL (Cloud SQL or local)
- **Authentication**: Trusts `x-firebase-uid` header from API Gateway

## 🚀 Setup

### Prerequisites

- Python 3.9+
- MySQL 8.0+
- Firebase service account key

### Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up database**
   ```bash
   mysql -u root -p user_db < ../DB-Service/initUser.sql
   ```

3. **Configure environment variables**
   Create a `.env` file:
   ```env
   DB_HOST=127.0.0.1
   DB_USER=root
   DB_PASS=your_password
   DB_NAME=user_db
   FIREBASE_SERVICE_ACCOUNT_PATH=./serviceAccountKey.json
   ```

4. **Add Firebase service account key**
   - Download from Firebase Console
   - Place as `serviceAccountKey.json` in service directory

5. **Run the service**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001
   ```

## 🔧 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|---------|
| `DB_HOST` | Database host address | `127.0.0.1` | Yes |
| `DB_USER` | Database username | `root` | Yes |
| `DB_PASS` | Database password | - | Yes |
| `DB_NAME` | Database name | `user_db` | Yes |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Path to Firebase service account JSON | `./serviceAccountKey.json` | No |

## 📡 API Endpoints

### User Management

#### `GET /users`
Get all users (excluding sensitive information)

**Headers:**
- `x-firebase-uid`: Firebase user ID (injected by API Gateway)

**Response:**
```json
[
  {
    "user_id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "email": "john@example.com",
    "profile_picture": "https://...",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

#### `GET /users/me`
Get current authenticated user's profile

**Headers:**
- `x-firebase-uid`: Firebase user ID

**Response:**
```json
{
  "user_id": 1,
  "firebase_uid": "abc123",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "email": "john@example.com",
  "profile_picture": "https://...",
  "created_at": "2024-01-01T00:00:00"
}
```

**ETag Support**: Returns `ETag` header for caching

#### `GET /users/{user_id}`
Get user by ID

#### `GET /users/username/{username}`
Get user by username

#### `POST /users`
Create new user (sync from Firebase)

**Request Body:**
```json
{
  "firebase_uid": "abc123",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe"
}
```

#### `PUT /users/me`
Update current user's profile

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "profile_picture": "https://..."
}
```

#### `GET /users/search`
Search users by query string

**Query Parameters:**
- `q`: Search query (required)
- `skip`: Pagination offset (default: 0)
- `limit`: Results per page (default: 10, max: 100)

### Interest Management

#### `GET /users/interests`
Get all available interests

#### `GET /users/me/interests`
Get current user's interests

#### `POST /users/me/interests`
Add interests to current user

**Request Body:**
```json
{
  "interest_ids": [1, 2, 3]
}
```

#### `DELETE /users/me/interests/{interest_id}`
Remove interest from current user

### User Sync

#### `POST /users/sync`
Sync user from Firebase (internal endpoint)

**Request Body:**
```json
{
  "firebase_uid": "abc123",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe"
}
```

## 🔐 Authentication

This service **does not** perform Firebase authentication directly. It trusts the `x-firebase-uid` header injected by the API Gateway middleware.

**Authentication Flow:**
1. Client sends request with `Authorization: Bearer <firebase-token>` to API Gateway
2. API Gateway validates token and extracts `firebase_uid`
3. API Gateway forwards request with `x-firebase-uid` header
4. Users Service uses `x-firebase-uid` to identify the user

## 🗄️ Database Schema

### Users Table
- `user_id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `firebase_uid` (VARCHAR, UNIQUE)
- `email` (VARCHAR, UNIQUE)
- `username` (VARCHAR, UNIQUE)
- `first_name` (VARCHAR)
- `last_name` (VARCHAR)
- `profile_picture` (TEXT)
- `created_at` (TIMESTAMP)

### Interests Table
- `interest_id` (INT, PRIMARY KEY)
- `interest_name` (VARCHAR, UNIQUE)

### UserInterests Table (Many-to-Many)
- `user_id` (INT, FOREIGN KEY)
- `interest_id` (INT, FOREIGN KEY)

## 🐳 Docker Deployment

### Build Image
```bash
docker build -t users-service .
```

### Run Container
```bash
docker run -p 8001:8001 \
  -e DB_HOST=your_db_host \
  -e DB_USER=your_db_user \
  -e DB_PASS=your_db_password \
  -e DB_NAME=user_db \
  users-service
```

## ☁️ GCP Cloud Run Deployment

The service is deployed to Cloud Run with:
- VPC Connector for database access
- Private IP connection to Cloud SQL
- Environment variables configured via deployment script

See [../GCP_DEPLOYMENT_GUIDE.md](../GCP_DEPLOYMENT_GUIDE.md) for details.

## 🧪 Testing

### Health Check
```bash
curl http://localhost:8001/
```

### Get Current User
```bash
curl -H "x-firebase-uid: your-firebase-uid" \
     http://localhost:8001/users/me
```

### Search Users
```bash
curl -H "x-firebase-uid: your-firebase-uid" \
     "http://localhost:8001/users/search?q=john"
```

## 📚 API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`
- OpenAPI JSON: `http://localhost:8001/openapi.json`

## 🔍 Error Handling

The service returns standard HTTP status codes:

- `200 OK`: Successful request
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid `x-firebase-uid` header
- `404 Not Found`: Resource not found
- `409 Conflict`: Duplicate resource (e.g., username already exists)
- `500 Internal Server Error`: Server error

## 📝 Notes

- The service uses MySQL connector with dictionary cursor for JSON-like responses
- ETag support is implemented for `/users/me` endpoint for caching
- All user data is validated before database operations
- Username and email must be unique

## 🤝 Contributing

When adding new endpoints:
1. Add route to `routers/users.py`
2. Use `get_firebase_uid_from_header()` helper for authentication
3. Add proper error handling
4. Update this README with endpoint documentation
