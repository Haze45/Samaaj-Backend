"""
Firebase Cloud Messaging (FCM) notification service.
Handles sending push notifications to Android devices via Google FCM.

Setup:
1. Go to Firebase Console → Project Settings → Service Accounts
2. Click "Generate new private key" → download JSON file
3. Copy the entire JSON content and set it as FIREBASE_CREDENTIALS_JSON
   environment variable on Render dashboard.
"""

import json
import os
import logging
from typing import Optional
import firebase_admin
from firebase_admin import credentials, messaging
from core.config import settings

logger = logging.getLogger(__name__)

# Track whether Firebase has been initialized
_firebase_initialized = False


def _initialize_firebase():
    """
    Initialize Firebase Admin SDK using credentials from environment variable.
    Called lazily on first use so app startup is not blocked if credentials
    are not set (e.g. during local development without Firebase).
    """
    global _firebase_initialized

    if _firebase_initialized:
        return True

    creds_json = settings.FIREBASE_CREDENTIALS_JSON
    if not creds_json:
        logger.warning(
            "FIREBASE_CREDENTIALS_JSON not set. "
            "Push notifications will be disabled."
        )
        return False

    try:
        creds_dict = json.loads(creds_json)
        cred = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        return False


def send_notification_to_token(
    token: str,
    title: str,
    body: str,
    data: Optional[dict] = None
) -> bool:
    """
    Send a push notification to a single device token.
    Returns True if successful, False otherwise.
    """
    if not _initialize_firebase():
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    click_action="FLUTTER_NOTIFICATION_CLICK",
                )
            )
        )
        response = messaging.send(message)
        logger.info(f"Notification sent successfully: {response}")
        return True
    except messaging.UnregisteredError:
        # Token is no longer valid — device uninstalled app
        logger.warning(f"FCM token unregistered: {token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def send_notification_to_multiple_tokens(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None
) -> dict:
    """
    Send a push notification to multiple device tokens at once.
    Uses FCM MulticastMessage for efficiency (one API call for up to 500 tokens).
    Returns a dict with success_count and failure_count.
    """
    if not _initialize_firebase():
        return {"success_count": 0, "failure_count": len(tokens)}

    if not tokens:
        return {"success_count": 0, "failure_count": 0}

    try:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=tokens,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                )
            )
        )
        response = messaging.send_each_for_multicast(message)
        logger.info(
            f"Multicast sent: {response.success_count} success, "
            f"{response.failure_count} failure"
        )
        return {
            "success_count": response.success_count,
            "failure_count": response.failure_count,
        }
    except Exception as e:
        logger.error(f"Failed to send multicast notification: {e}")
        return {"success_count": 0, "failure_count": len(tokens)}


# ── Notification templates for SamaajBot ─────────────────────────────────────

def notify_new_document(
    community_name: str,
    document_name: str,
    community_id: int,
    tokens: list[str]
):
    """
    Notify all community members when admin uploads a new document.
    """
    if not tokens:
        return
    send_notification_to_multiple_tokens(
        tokens=tokens,
        title=f"📄 New document in {community_name}",
        body=f'"{document_name}" has been uploaded.',
        data={
            "type": "new_document",
            "community_id": str(community_id),
        }
    )


def notify_document_indexed(
    community_name: str,
    document_name: str,
    community_id: int,
    tokens: list[str]
):
    """
    Notify all community members when a document finishes AI indexing
    and is ready to be asked questions about.
    """
    if not tokens:
        return
    send_notification_to_multiple_tokens(
        tokens=tokens,
        title=f"✅ Document ready in {community_name}",
        body=f'"{document_name}" is now indexed. You can ask questions about it!',
        data={
            "type": "document_indexed",
            "community_id": str(community_id),
        }
    )


def notify_new_member(
    community_name: str,
    member_name: str,
    community_id: int,
    admin_token: Optional[str]
):
    """
    Notify the community admin when a new member joins.
    """
    if not admin_token:
        return
    send_notification_to_token(
        token=admin_token,
        title=f"👋 New member in {community_name}",
        body=f"{member_name} has joined your community.",
        data={
            "type": "new_member",
            "community_id": str(community_id),
        }
    )