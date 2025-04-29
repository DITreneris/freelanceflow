"""
Email service utility for sending emails.
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr, BaseModel
from jinja2 import Environment, select_autoescape, FileSystemLoader

# Email configuration
class EmailConfig:
    """Email configuration settings"""
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "your-email@example.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "your-password")
    MAIL_FROM = os.getenv("MAIL_FROM", "your-email@example.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "FreelanceFlow")
    MAIL_TLS = True
    MAIL_SSL = False
    USE_CREDENTIALS = True
    TEMPLATE_FOLDER = Path(__file__).parent.parent / "templates" / "email"

# Configure FastMail
conf = ConnectionConfig(
    MAIL_USERNAME=EmailConfig.MAIL_USERNAME,
    MAIL_PASSWORD=EmailConfig.MAIL_PASSWORD,
    MAIL_FROM=EmailConfig.MAIL_FROM,
    MAIL_PORT=EmailConfig.MAIL_PORT,
    MAIL_SERVER=EmailConfig.MAIL_SERVER,
    MAIL_FROM_NAME=EmailConfig.MAIL_FROM_NAME,
    MAIL_TLS=EmailConfig.MAIL_TLS,
    MAIL_SSL=EmailConfig.MAIL_SSL,
    USE_CREDENTIALS=EmailConfig.USE_CREDENTIALS,
    TEMPLATE_FOLDER=EmailConfig.TEMPLATE_FOLDER
)

# Create FastMail instance
mail = FastMail(conf)

# Create Jinja2 environment for email templates
templates_path = Path(__file__).parent.parent / "templates" / "email"
if not templates_path.exists():
    templates_path.mkdir(parents=True, exist_ok=True)

env = Environment(
    loader=FileSystemLoader(templates_path),
    autoescape=select_autoescape(['html', 'xml'])
)

# Email models
class EmailSchema(BaseModel):
    """Email schema for validation"""
    recipient: List[EmailStr]
    subject: str
    body: str
    template_name: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None

class BulkEmailSchema(BaseModel):
    """Bulk email schema for sending to multiple recipients"""
    recipients: List[EmailStr]
    subject: str
    body: str
    template_name: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None

async def send_email(email: EmailSchema) -> None:
    """
    Send an email using FastMail
    
    Args:
        email: Email schema with recipient, subject, body, and optional template
    """
    # Prepare message content
    if email.template_name and email.template_data:
        # Render template with provided data
        template = env.get_template(f"{email.template_name}.html")
        html_content = template.render(**email.template_data)
    else:
        # Use plain body text
        html_content = f"<html><body>{email.body}</body></html>"
    
    # Create message
    message = MessageSchema(
        subject=email.subject,
        recipients=email.recipient,
        body=html_content,
        subtype=MessageType.html
    )
    
    # Send email
    await mail.send_message(message)

async def send_bulk_email(bulk_email: BulkEmailSchema) -> None:
    """
    Send bulk emails to multiple recipients
    
    Args:
        bulk_email: Bulk email schema with recipients, subject, body, and optional template
    """
    # Prepare message content
    if bulk_email.template_name and bulk_email.template_data:
        # Render template with provided data
        template = env.get_template(f"{bulk_email.template_name}.html")
        html_content = template.render(**bulk_email.template_data)
    else:
        # Use plain body text
        html_content = f"<html><body>{bulk_email.body}</body></html>"
    
    # Create message
    message = MessageSchema(
        subject=bulk_email.subject,
        recipients=bulk_email.recipients,
        body=html_content,
        subtype=MessageType.html
    )
    
    # Send email
    await mail.send_message(message)

# Helper functions for common email types
async def send_welcome_email(recipient: EmailStr, user_name: str) -> None:
    """
    Send welcome email to a new user
    
    Args:
        recipient: User's email address
        user_name: User's name or email if name is not provided
    """
    email = EmailSchema(
        recipient=[recipient],
        subject="Welcome to FreelanceFlow!",
        body="",
        template_name="welcome",
        template_data={
            "user_name": user_name,
            "app_name": "FreelanceFlow",
            "login_url": "https://yourapp.com/login"
        }
    )
    
    await send_email(email)

async def send_password_reset_email(recipient: EmailStr, reset_token: str) -> None:
    """
    Send password reset email with token
    
    Args:
        recipient: User's email address
        reset_token: Password reset token
    """
    # Token URL would typically be constructed from your frontend URL
    reset_url = f"https://yourapp.com/reset-password?token={reset_token}"
    
    email = EmailSchema(
        recipient=[recipient],
        subject="Reset Your FreelanceFlow Password",
        body="",
        template_name="password_reset",
        template_data={
            "reset_url": reset_url,
            "app_name": "FreelanceFlow",
            "token_expiry": "24 hours"
        }
    )
    
    await send_email(email)

async def send_deal_notification_email(
    recipient: EmailStr, 
    user_name: str,
    deal_id: int,
    deal_title: str,
    client_name: str,
    status: str
) -> None:
    """
    Send notification email about deal status change
    
    Args:
        recipient: User's email address
        user_name: User's name or email if name is not provided
        deal_id: ID of the deal
        deal_title: Title or identifier of the deal
        client_name: Name of the client
        status: New status of the deal
    """
    # Deal URL would typically be constructed from your frontend URL
    deal_url = f"https://yourapp.com/deals/{deal_id}"
    
    email = EmailSchema(
        recipient=[recipient],
        subject=f"Deal Update: {deal_title}",
        body="",
        template_name="deal_notification",
        template_data={
            "user_name": user_name,
            "deal_title": deal_title,
            "client_name": client_name,
            "status": status,
            "deal_url": deal_url,
            "app_name": "FreelanceFlow"
        }
    )
    
    await send_email(email) 