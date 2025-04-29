"""
Background tasks for handling asynchronous operations.
"""

from typing import List, Dict, Any, Optional
from fastapi import BackgroundTasks
from pydantic import EmailStr
from app.utils.email_service import (
    EmailSchema, 
    BulkEmailSchema, 
    send_email,
    send_bulk_email,
    send_welcome_email,
    send_password_reset_email,
    send_deal_notification_email
)
from app.models import User, Deal, Client, NotificationType, Notification
from sqlmodel import Session

# Email background tasks
def send_email_in_background(
    background_tasks: BackgroundTasks,
    recipient: List[EmailStr],
    subject: str,
    body: str,
    template_name: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Add email sending to background tasks
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        recipient: List of recipient email addresses
        subject: Email subject
        body: Email body (used if no template)
        template_name: Optional template name
        template_data: Optional template data
    """
    email_data = EmailSchema(
        recipient=recipient,
        subject=subject,
        body=body,
        template_name=template_name,
        template_data=template_data
    )
    background_tasks.add_task(send_email, email_data)

def send_bulk_email_in_background(
    background_tasks: BackgroundTasks,
    recipients: List[EmailStr],
    subject: str,
    body: str,
    template_name: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Add bulk email sending to background tasks
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        recipients: List of recipient email addresses
        subject: Email subject
        body: Email body (used if no template)
        template_name: Optional template name
        template_data: Optional template data
    """
    email_data = BulkEmailSchema(
        recipients=recipients,
        subject=subject,
        body=body,
        template_name=template_name,
        template_data=template_data
    )
    background_tasks.add_task(send_bulk_email, email_data)

def send_welcome_email_in_background(
    background_tasks: BackgroundTasks,
    recipient: EmailStr,
    user_name: str
) -> None:
    """
    Add welcome email sending to background tasks
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        recipient: User's email address
        user_name: User's name or email
    """
    background_tasks.add_task(send_welcome_email, recipient, user_name)

def send_password_reset_email_in_background(
    background_tasks: BackgroundTasks,
    recipient: EmailStr,
    reset_token: str
) -> None:
    """
    Add password reset email sending to background tasks
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        recipient: User's email address
        reset_token: Password reset token
    """
    background_tasks.add_task(send_password_reset_email, recipient, reset_token)

def send_deal_notification_email_in_background(
    background_tasks: BackgroundTasks,
    db: Session,
    user: User,
    deal_id: int,
    notification_type: str
) -> None:
    """
    Create and send deal notification email in background
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        db: Database session
        user: User to notify
        deal_id: ID of the deal
        notification_type: Type of notification
    """
    # Get deal and client details
    deal = db.get(Deal, deal_id)
    if not deal:
        return
    
    client = db.get(Client, deal.client_id)
    if not client:
        return
    
    # Prepare deal title (using ID as title)
    deal_title = f"Deal #{deal_id}"
    
    # Determine status message based on notification type
    status = deal.stage
    if notification_type == NotificationType.DEAL_CREATED:
        subject = f"New Deal Created: {deal_title}"
    elif notification_type == NotificationType.DEAL_UPDATED:
        subject = f"Deal Updated: {deal_title}"
    elif notification_type == NotificationType.DEAL_STAGE_CHANGED:
        subject = f"Deal Stage Changed: {deal_title}"
    else:
        subject = f"Deal Update: {deal_title}"
    
    # Only send if user has email notifications enabled
    if user.email_notifications_enabled:
        background_tasks.add_task(
            send_deal_notification_email,
            recipient=user.email,
            user_name=user.full_name or user.email,
            deal_id=deal_id,
            deal_title=deal_title,
            client_name=client.name,
            status=status
        )

def create_notification_with_email(
    background_tasks: BackgroundTasks,
    db: Session,
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    entity_type: str,
    entity_id: int
) -> None:
    """
    Create notification and send email notification in background
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        db: Database session
        user_id: ID of the user to notify
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        entity_type: Type of entity (deal, client, etc.)
        entity_id: ID of the entity
    """
    # Create notification in database
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        is_read=False
    )
    db.add(notification)
    db.commit()
    
    # Get user
    user = db.get(User, user_id)
    if not user:
        return
    
    # Send email notification based on entity type
    if entity_type == "deal":
        send_deal_notification_email_in_background(
            background_tasks=background_tasks,
            db=db,
            user=user,
            deal_id=entity_id,
            notification_type=notification_type
        ) 