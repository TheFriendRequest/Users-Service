"""
Firebase Custom Claims Management
Handles setting and updating custom claims (like roles) in Firebase
"""
import firebase_admin
from firebase_admin import auth, credentials
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=env_path, override=True)

# Initialize Firebase Admin SDK if not already initialized
def _ensure_firebase_initialized():
    """Ensure Firebase Admin SDK is initialized"""
    if len(firebase_admin._apps) == 0:
        try:
            # Try service account path first (local development)
            service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            if service_account_path:
                # Convert relative path to absolute path
                if not os.path.isabs(service_account_path):
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    service_account_path = os.path.join(current_dir, service_account_path)
                
                if os.path.exists(service_account_path):
                    cred = credentials.Certificate(service_account_path)
                    firebase_admin.initialize_app(cred)
                    print("✅ Firebase Admin initialized in firebase_claims module")
                else:
                    print(f"⚠️  Firebase service account file not found: {service_account_path}")
            else:
                # Try Application Default Credentials (for GCP deployment)
                project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
                if project_id:
                    firebase_admin.initialize_app()
                    print("✅ Firebase Admin initialized with Application Default Credentials")
                else:
                    print("⚠️  Firebase not initialized: No credentials found")
        except Exception as e:
            print(f"⚠️  Firebase initialization error in firebase_claims: {e}")


def set_user_role(firebase_uid: str, role: str) -> bool:
    """
    Set custom claim (role) for a Firebase user.
    
    Args:
        firebase_uid: Firebase user UID
        role: Role to assign (e.g., "user", "admin", "moderator")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure Firebase is initialized
        _ensure_firebase_initialized()
        
        # Check if Firebase is initialized after attempting to initialize
        if len(firebase_admin._apps) == 0:
            print("⚠️  Firebase Admin not initialized, cannot set custom claims")
            return False
        
        # Get current custom claims (if any)
        user = auth.get_user(firebase_uid)
        current_claims = user.custom_claims or {}
        
        # Update claims with new role
        updated_claims = {**current_claims, "role": role}
        
        # Set custom claims
        auth.set_custom_user_claims(firebase_uid, updated_claims)
        
        print(f"✅ Set Firebase custom claim: role={role} for firebase_uid={firebase_uid}")
        return True
        
    except auth.UserNotFoundError:
        print(f"❌ Firebase user not found: {firebase_uid}")
        return False
    except Exception as e:
        print(f"❌ Failed to set custom claims for {firebase_uid}: {e}")
        import traceback
        traceback.print_exc()
        return False


def update_user_role(firebase_uid: str, new_role: str) -> bool:
    """
    Update role in Firebase custom claims.
    Alias for set_user_role (same functionality).
    
    Args:
        firebase_uid: Firebase user UID
        new_role: New role to assign
    
    Returns:
        True if successful, False otherwise
    """
    return set_user_role(firebase_uid, new_role)


def get_user_role(firebase_uid: str) -> Optional[str]:
    """
    Get role from Firebase custom claims.
    
    Args:
        firebase_uid: Firebase user UID
    
    Returns:
        Role string if found, None otherwise
    """
    try:
        # Ensure Firebase is initialized
        _ensure_firebase_initialized()
        
        if len(firebase_admin._apps) == 0:
            return None
        
        user = auth.get_user(firebase_uid)
        claims = user.custom_claims or {}
        return claims.get("role")
        
    except Exception as e:
        print(f"❌ Failed to get custom claims for {firebase_uid}: {e}")
        return None


def sync_role_to_firebase(firebase_uid: str, role: str) -> bool:
    """
    Sync role from database to Firebase custom claims.
    Useful when role is updated in database and needs to be synced to Firebase.
    
    Args:
        firebase_uid: Firebase user UID
        role: Role from database
    
    Returns:
        True if synced successfully, False otherwise
    """
    try:
        # Get current Firebase role
        firebase_role = get_user_role(firebase_uid)
        
        # Only update if different
        if firebase_role != role:
            print(f"🔄 Syncing role: {firebase_role} → {role} for {firebase_uid}")
            return set_user_role(firebase_uid, role)
        else:
            print(f"✅ Firebase role already matches database: {role}")
            return True
            
    except Exception as e:
        print(f"❌ Failed to sync role to Firebase: {e}")
        return False

