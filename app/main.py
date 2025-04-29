from fastapi import FastAPI, Depends, HTTPException, Request, status, Body, Cookie
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response, RedirectResponse, JSONResponse
import httpx
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import csv
from io import StringIO
from sqlmodel import Session, select, col, or_
from typing import List, Optional, Dict, Any
import jwt
import pandas as pd
import base64
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

from app.database import create_db_and_tables, get_session, create_demo_data
from app.models import Client, Deal, Invoice, InvoiceItem, Task, Feedback, ClientCreate, ClientRead, ClientUpdate, User
from app.models import DealCreate, DealRead, DealUpdate, DealMoveUpdate, DealStage
from app import crud
from app.utils import format_money, format_date, generate_pipeline_summary_pdf, generate_client_distribution_pdf, generate_dashboard_pdf
from app.utils.excel_exports import generate_pipeline_excel, generate_clients_excel, generate_deals_excel
from app.auth import (
    authenticate_user, 
    create_access_token, 
    get_current_user, 
    create_token_from_google_user,
    Token,
    SECRET_KEY,
    ALGORITHM,
    get_password_hash,
    require_permission
)
from app.models import NotificationType, Notification, Permission, Role, RolePermission, UserRole
from app.utils.background_tasks import create_notification_with_email

# Initialize FastAPI app
app = FastAPI(
    title="FreelanceFlow",
    description="Lightweight SaaS for solo freelancers",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "auth", "description": "Authentication operations"},
        {"name": "clients", "description": "Client management operations"},
        {"name": "deals", "description": "Deal management operations"},
        {"name": "pipeline", "description": "Pipeline statistics and reporting"},
        {"name": "export", "description": "Data export operations"},
        {"name": "notifications", "description": "Notification management operations"},
        {"name": "analytics", "description": "Analytics operations"},
        {"name": "permissions", "description": "Permissions management operations"},
        {"name": "roles", "description": "Roles management operations"},
        {"name": "users", "description": "Users management operations"},
    ]
)

# Set up templates and static files
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# OAuth2 configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your-client-id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "your-client-secret")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&scope=email%20profile&access_type=offline",
    tokenUrl="https://oauth2.googleapis.com/token"
)

# Event handler to create tables on startup
@app.on_event("startup")
def on_startup():
    # Initialize roles and permissions
    from migrations.initialize_roles import run_migrations
    run_migrations()
    
    create_db_and_tables()
    create_demo_data()
    
    print("App started successfully!")

# Routes
@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_from_cookie)
):
    """Redirect to dashboard if authenticated, otherwise to login page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page with Google OAuth button"""
    auth_url = f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&scope=email%20profile&access_type=offline"
    return templates.TemplateResponse("login.html", {"request": request, "auth_url": auth_url})

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str):
    """Handle OAuth callback from Google"""
    # Exchange auth code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": GOOGLE_REDIRECT_URI
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Could not validate credentials")
        
        tokens = response.json()
        access_token = tokens.get("access_token")
        
        # Get user info with access token
        user_info_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info = user_info_response.json()
        
        # Check if user exists in our database, if not create them
        db = next(get_session())
        email = user_info.get("email")
        db_user = crud.get_user_by_email(db, email)
        
        if not db_user:
            # Create new user
            new_user = User(
                email=email,
                hashed_password="",  # No password for OAuth users
                is_active=True,
                full_name=user_info.get("name", ""),
            )
            db_user = crud.create(db, new_user)
        
        # Create our own JWT token
        jwt_token = create_token_from_google_user(user_info)
        
        # Set JWT as cookie
        response = RedirectResponse(url="/")
        response.set_cookie(
            key="access_token",
            value=f"Bearer {jwt_token}",
            httponly=True,
            max_age=60 * 60 * 24,  # 1 day
            expires=60 * 60 * 24,
        )
        
        return response

@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request):
    """Render the clients management page"""
    return templates.TemplateResponse("clients.html", {"request": request})

@app.get("/deals", response_class=HTMLResponse)
async def deals_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_from_cookie)
):
    """Render the deals/kanban page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("deals.html", {
        "request": request,
        "user": {
            "name": current_user.full_name,
            "email": current_user.email,
        }
    })

# Client API Routes
@app.post("/api/clients/", response_model=ClientRead, tags=["clients"])
def create_client(*, session: Session = Depends(get_session), client: ClientCreate):
    """
    Create a new client
    
    Creates a new client with the provided information and returns the client details
    """
    db_client = Client.from_orm(client)
    session.add(db_client)
    session.commit()
    session.refresh(db_client)
    return db_client

@app.get("/api/clients/", response_model=List[ClientRead], tags=["clients"])
def read_clients(*, session: Session = Depends(get_session)):
    """
    Get all clients
    
    Returns a list of all clients
    """
    clients = session.exec(select(Client)).all()
    return clients

@app.get("/api/clients/{client_id}", response_model=ClientRead)
def read_client(*, session: Session = Depends(get_session), client_id: int):
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@app.patch("/api/clients/{client_id}", response_model=ClientRead)
def update_client(
    *, session: Session = Depends(get_session), client_id: int, client: ClientUpdate
):
    db_client = session.get(Client, client_id)
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client_data = client.dict(exclude_unset=True)
    for key, value in client_data.items():
        setattr(db_client, key, value)
    
    session.add(db_client)
    session.commit()
    session.refresh(db_client)
    return db_client

@app.delete("/api/clients/{client_id}")
def delete_client(*, session: Session = Depends(get_session), client_id: int):
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    session.delete(client)
    session.commit()
    return {"ok": True}

# Deal API Routes
@app.post("/api/deals/", response_model=DealRead, tags=["deals"])
def create_deal(*, session: Session = Depends(get_session), deal: DealCreate):
    """
    Create a new deal
    
    Creates a new deal with the provided information and returns the deal details
    """
    db_deal = Deal.from_orm(deal)
    session.add(db_deal)
    session.commit()
    session.refresh(db_deal)
    return db_deal

@app.get("/api/deals/", response_model=List[DealRead], tags=["deals"])
def read_deals(
    *,
    session: Session = Depends(get_session),
    stage: str = None,
    client_id: int = None,
    min_value: int = None,
    max_value: int = None,
    sort_by: str = None,
    updated_after: str = None
):
    """
    Get all deals with advanced filtering
    
    Returns a list of all deals, optionally filtered by various parameters
    
    Parameters:
    - **stage**: Filter by deal stage (lead, proposed, won)
    - **client_id**: Filter by client ID
    - **min_value**: Minimum deal value (in dollars/euros, will be converted to cents)
    - **max_value**: Maximum deal value (in dollars/euros, will be converted to cents)
    - **sort_by**: Field to sort by (e.g., value, -value, updated_at, -updated_at)
    - **updated_after**: Filter deals updated after this date (ISO format YYYY-MM-DD)
    """
    query = select(Deal)
    
    # Apply filters if provided
    if stage:
        query = query.where(Deal.stage == stage)
    
    if client_id:
        query = query.where(Deal.client_id == client_id)
    
    if min_value:
        # Convert dollars to cents
        min_value_cents = int(float(min_value) * 100)
        query = query.where(Deal.value >= min_value_cents)
    
    if max_value:
        # Convert dollars to cents
        max_value_cents = int(float(max_value) * 100)
        query = query.where(Deal.value <= max_value_cents)
    
    if updated_after:
        try:
            # Parse the date string
            updated_after_date = datetime.fromisoformat(updated_after)
            query = query.where(Deal.updated_at >= updated_after_date)
        except ValueError:
            # If date parsing fails, ignore this filter
            pass
    
    # Apply sorting if provided
    if sort_by:
        if sort_by.startswith('-'):
            # Descending order
            field_name = sort_by[1:]
            if hasattr(Deal, field_name):
                query = query.order_by(getattr(Deal, field_name).desc())
        else:
            # Ascending order
            if hasattr(Deal, sort_by):
                query = query.order_by(getattr(Deal, sort_by))
    else:
        # Default sort: most recently updated first
        query = query.order_by(Deal.updated_at.desc())
    
    deals = session.exec(query).all()
    return deals

@app.get("/api/deals/{deal_id}", response_model=DealRead)
def read_deal(*, session: Session = Depends(get_session), deal_id: int):
    deal = session.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal

@app.patch("/api/deals/{deal_id}", response_model=DealRead)
def update_deal(
    *, 
    session: Session = Depends(get_session), 
    deal_id: int, 
    deal: DealUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Update a deal"""
    # Get the deal
    statement = select(Deal).where(Deal.id == deal_id)
    db_deal = session.exec(statement).first()
    if not db_deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal with ID {deal_id} not found"
        )
    
    # Check if stage is being updated
    stage_changed = deal.stage is not None and deal.stage != db_deal.stage
    
    # Update deal attributes
    for key, value in deal.dict(exclude_unset=True).items():
        setattr(db_deal, key, value)
    
    session.add(db_deal)
    session.commit()
    session.refresh(db_deal)
    
    # Create notification
    notification_type = NotificationType.DEAL_STAGE_CHANGED if stage_changed else NotificationType.DEAL_UPDATED
    
    # Get client info for notification
    statement = select(Client).where(Client.id == db_deal.client_id)
    client = session.exec(statement).first()
    client_name = client.name if client else "Unknown Client"
    
    # Create title and message based on notification type
    if stage_changed:
        title = f"Deal stage changed to {db_deal.stage}"
        message = f"Deal with {client_name} has been moved to {db_deal.stage} stage"
    else:
        title = "Deal updated"
        message = f"Deal with {client_name} has been updated"
    
    # Create notification and send email
    create_notification_with_email(
        background_tasks=background_tasks,
        db=session,
        user_id=current_user.id,
        notification_type=notification_type,
        title=title,
        message=message,
        entity_type="deal",
        entity_id=deal_id
    )
    
    return db_deal

@app.patch("/api/deals/{deal_id}/move", response_model=DealRead, tags=["deals"])
def move_deal(
    *, 
    session: Session = Depends(get_session), 
    deal_id: int, 
    move: DealMoveUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Move a deal to a different stage
    
    Updates the stage of a deal and creates a notification
    
    Parameters:
    - **new_stage**: The new stage to move the deal to (lead, proposed, won)
    """
    db_deal = session.get(Deal, deal_id)
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    # Get the client name for the notification
    client = session.get(Client, db_deal.client_id)
    client_name = client.name if client else "Unknown Client"
    
    # Save the old stage for the notification
    old_stage = db_deal.stage
    
    # Update the deal
    db_deal.stage = move.new_stage
    db_deal.updated_at = datetime.utcnow()
    
    session.add(db_deal)
    session.commit()
    session.refresh(db_deal)
    
    # Create a notification for the stage change
    stage_labels = {
        "lead": "Lead",
        "proposed": "Proposed",
        "won": "Won"
    }
    
    old_stage_label = stage_labels.get(old_stage, old_stage.capitalize())
    new_stage_label = stage_labels.get(move.new_stage, move.new_stage.capitalize())
    
    notification_title = f"Deal Moved: {client_name}"
    notification_message = f"Deal with {client_name} moved from {old_stage_label} to {new_stage_label}"
    
    # Create notification and send email
    create_notification_with_email(
        background_tasks=background_tasks,
        db=session,
        user_id=current_user.id,
        notification_type=NotificationType.DEAL_STAGE_CHANGED,
        title=notification_title,
        message=notification_message,
        entity_type="deal",
        entity_id=deal_id
    )
    
    return db_deal

@app.delete("/api/deals/{deal_id}")
def delete_deal(*, session: Session = Depends(get_session), deal_id: int):
    deal = session.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    session.delete(deal)
    session.commit()
    return {"ok": True}

# Pipeline statistics endpoint
@app.get("/api/pipeline/summary", tags=["pipeline"])
def get_pipeline_summary(db: Session = Depends(get_session)):
    """
    Get summary statistics for the deal pipeline
    
    Returns counts and values for deals in each stage and the total pipeline value
    """
    # Get all deals
    deals = crud.get_all(db, Deal)
    
    # Calculate total value by stage
    lead_value = sum(deal.value for deal in deals if deal.stage == "lead")
    proposed_value = sum(deal.value for deal in deals if deal.stage == "proposed")
    won_value = sum(deal.value for deal in deals if deal.stage == "won")
    
    # Count deals by stage
    lead_count = sum(1 for deal in deals if deal.stage == "lead")
    proposed_count = sum(1 for deal in deals if deal.stage == "proposed")
    won_count = sum(1 for deal in deals if deal.stage == "won")
    
    # Total pipeline value
    total_pipeline = lead_value + proposed_value + won_value
    
    return {
        "stages": {
            "lead": {
                "count": lead_count,
                "value": lead_value,
                "value_formatted": format_money(lead_value)
            },
            "proposed": {
                "count": proposed_count,
                "value": proposed_value,
                "value_formatted": format_money(proposed_value)
            },
            "won": {
                "count": won_count,
                "value": won_value,
                "value_formatted": format_money(won_value)
            }
        },
        "total": {
            "count": lead_count + proposed_count + won_count,
            "value": total_pipeline,
            "value_formatted": format_money(total_pipeline)
        }
    }

# CSV Export endpoint
@app.get("/export/csv", tags=["export"])
async def export_csv(db: Session = Depends(get_session)):
    """
    Export clients data to CSV
    
    Returns a downloadable CSV file with client information
    """
    # Get client data from database
    clients = crud.get_clients_with_export_data(db)
    
    # If no clients exist yet, provide sample data
    if not clients:
        clients = [
            {"id": 1, "name": "Acme Corp", "email": "contact@acme.com", "phone": "123-456-7890"},
            {"id": 2, "name": "Globex", "email": "info@globex.com", "phone": "555-123-4567"},
            {"id": 3, "name": "Initech", "email": "hello@initech.com", "phone": "987-654-3210"},
        ]
    
    # Create CSV
    output = StringIO()
    if clients:
        fieldnames = clients[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clients)
    
    # Return as downloadable file
    csv_content = output.getvalue()
    
    response = Response(content=csv_content, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=clients.csv"
    return response

@app.post("/token", response_model=Token, tags=["auth"])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session)
):
    """
    Login with username/password for JWT token
    
    Returns an access token and user information upon successful authentication
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    
    # Return the token and user info
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        }
    }

@app.get("/api/me", response_model=dict, tags=["auth"])
async def read_users_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    
    Returns the user details for the currently authenticated user
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
    }

@app.get("/logout", tags=["auth"])
async def logout():
    """
    Logout the current user
    
    Clears the authentication cookie and redirects to the login page
    """
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

# Auth middleware to get current user from cookie
async def get_current_user_from_cookie(
    request: Request,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
) -> Optional[User]:
    """Get current user from cookie for templates"""
    if not access_token:
        return None
    
    try:
        token = access_token.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        
        statement = select(User).where(User.email == email)
        user = db.exec(statement).first()
        return user
    except:
        return None

# Add notification endpoints
@app.get("/api/notifications/", tags=["notifications"])
def get_notifications(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    unread_only: bool = False,
    limit: int = 10
):
    """
    Get user notifications
    
    Returns a list of notifications for the current user
    
    Parameters:
    - **unread_only**: If true, returns only unread notifications
    - **limit**: Maximum number of notifications to return
    """
    query = select(Notification).where(Notification.user_id == current_user.id)
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    
    notifications = session.exec(query).all()
    return notifications

@app.patch("/api/notifications/{notification_id}/read", tags=["notifications"])
def mark_notification_read(
    *,
    session: Session = Depends(get_session),
    notification_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Mark a notification as read
    
    Updates the specified notification to mark it as read
    """
    notification = session.get(Notification, notification_id)
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this notification")
    
    notification.is_read = True
    session.add(notification)
    session.commit()
    
    return {"success": True}

@app.patch("/api/notifications/read-all", tags=["notifications"])
def mark_all_notifications_read(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Mark all notifications as read
    
    Updates all notifications for the current user to mark them as read
    """
    query = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    )
    
    unread_notifications = session.exec(query).all()
    
    for notification in unread_notifications:
        notification.is_read = True
        session.add(notification)
    
    session.commit()
    
    return {"success": True, "count": len(unread_notifications)}

# Add dashboard page
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, current_user: Optional[User] = Depends(get_current_user_from_cookie)):
    """Render the dashboard page with analytics"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": {
            "name": current_user.full_name,
            "email": current_user.email,
        }
    })

# Add advanced analytics page
@app.get("/advanced-analytics", response_class=HTMLResponse)
async def advanced_analytics_page(
    request: Request, 
    current_user: Optional[User] = Depends(get_current_user_from_cookie)
):
    """Render the advanced analytics page with predictive features"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("advanced_analytics.html", {
        "request": request,
        "user": {
            "name": current_user.full_name,
            "email": current_user.email,
        }
    })

# Add analytics endpoints
@app.get("/api/analytics/pipeline-trends", tags=["analytics"])
def get_pipeline_trends(
    db: Session = Depends(get_session),
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get pipeline trends over time
    
    Returns pipeline value trends for the specified number of days
    
    Parameters:
    - **days**: Number of days to analyze
    """
    # Calculate the start date
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get all deals updated within the date range
    statement = select(Deal).where(Deal.updated_at >= start_date)
    deals = db.exec(statement).all()
    
    # Convert to DataFrame for easier analysis
    deals_data = [{
        'id': deal.id,
        'value': deal.value,
        'stage': deal.stage,
        'updated_at': deal.updated_at.date()
    } for deal in deals]
    
    if not deals_data:
        return {
            "dates": [],
            "lead_values": [],
            "proposed_values": [],
            "won_values": []
        }
    
    df = pd.DataFrame(deals_data)
    
    # Get unique dates in the range
    date_range = pd.date_range(start=start_date.date(), end=datetime.utcnow().date())
    date_strings = [d.strftime('%Y-%m-%d') for d in date_range]
    
    # Initialize results
    lead_values = []
    proposed_values = []
    won_values = []
    
    # For each date, calculate the pipeline value
    for date in date_range:
        date_deals = df[df['updated_at'] <= date]
        
        # Sum values by stage
        lead_value = date_deals[date_deals['stage'] == 'lead']['value'].sum() / 100
        proposed_value = date_deals[date_deals['stage'] == 'proposed']['value'].sum() / 100
        won_value = date_deals[date_deals['stage'] == 'won']['value'].sum() / 100
        
        lead_values.append(float(lead_value))
        proposed_values.append(float(proposed_value))
        won_values.append(float(won_value))
    
    return {
        "dates": date_strings,
        "lead_values": lead_values,
        "proposed_values": proposed_values,
        "won_values": won_values
    }

@app.get("/api/analytics/conversion-rates", tags=["analytics"])
def get_conversion_rates(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get deal conversion rates
    
    Returns conversion rates between deal stages
    """
    # Get all deals
    deals = db.exec(select(Deal)).all()
    
    # Count deals in each stage
    lead_count = sum(1 for deal in deals if deal.stage == 'lead')
    proposed_count = sum(1 for deal in deals if deal.stage == 'proposed')
    won_count = sum(1 for deal in deals if deal.stage == 'won')
    
    # Calculate conversion rates
    lead_to_proposed = 0
    proposed_to_won = 0
    
    if lead_count > 0:
        lead_to_proposed = (proposed_count / lead_count) * 100
    
    if proposed_count > 0:
        proposed_to_won = (won_count / proposed_count) * 100
    
    return {
        "lead_count": lead_count,
        "proposed_count": proposed_count,
        "won_count": won_count,
        "lead_to_proposed": round(lead_to_proposed, 1),
        "proposed_to_won": round(proposed_to_won, 1),
        "overall_conversion": round((won_count / lead_count * 100) if lead_count > 0 else 0, 1)
    }

@app.get("/api/analytics/client-distribution", tags=["analytics"])
def get_client_distribution(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get deal distribution by client
    
    Returns the number and value of deals for top clients
    """
    # Get all deals with client information
    statement = select(Deal, Client).join(Client, Deal.client_id == Client.id)
    results = db.exec(statement).all()
    
    # Organize data by client
    client_data = {}
    for deal, client in results:
        if client.id not in client_data:
            client_data[client.id] = {
                "name": client.name,
                "deal_count": 0,
                "total_value": 0
            }
        
        client_data[client.id]["deal_count"] += 1
        client_data[client.id]["total_value"] += deal.value
    
    # Convert to list and sort by total value
    clients_list = [
        {
            "id": client_id,
            "name": data["name"],
            "deal_count": data["deal_count"],
            "total_value": data["total_value"] / 100,  # Convert to dollars
            "total_value_formatted": format_money(data["total_value"])
        }
        for client_id, data in client_data.items()
    ]
    
    clients_list.sort(key=lambda x: x["total_value"], reverse=True)
    
    # Take top 10 clients only
    return clients_list[:10]

@app.get("/api/analytics/deals-by-stage-chart", tags=["analytics"])
def get_deals_by_stage_chart(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get a chart of deals by stage
    
    Returns a base64-encoded PNG image of a pie chart showing deal distribution by stage
    """
    # Get all deals
    deals = db.exec(select(Deal)).all()
    
    # Count deals in each stage
    lead_count = sum(1 for deal in deals if deal.stage == 'lead')
    proposed_count = sum(1 for deal in deals if deal.stage == 'proposed')
    won_count = sum(1 for deal in deals if deal.stage == 'won')
    
    # Create pie chart
    labels = ['Lead', 'Proposed', 'Won']
    sizes = [lead_count, proposed_count, won_count]
    colors = ['#3498db', '#f39c12', '#2ecc71']
    
    # Skip empty data
    if sum(sizes) == 0:
        return {"error": "No deals data available"}
    
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
    plt.title('Deals by Stage')
    
    # Save to a BytesIO object
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    
    # Encode to base64
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return {"image": f"data:image/png;base64,{img_base64}"}

@app.get("/api/analytics/pipeline-value-chart", tags=["analytics"])
def get_pipeline_value_chart(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get a chart of pipeline value by stage
    
    Returns a base64-encoded PNG image of a bar chart showing pipeline value by stage
    """
    # Get pipeline summary
    pipeline = crud.calculate_pipeline_value(db)
    
    # Create bar chart
    labels = ['Lead', 'Proposed', 'Won', 'Total']
    values = [
        pipeline['lead'] / 100,
        pipeline['proposed'] / 100,
        pipeline['won'] / 100,
        pipeline['total'] / 100
    ]
    colors = ['#3498db', '#f39c12', '#2ecc71', '#9b59b6']
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, values, color=colors)
    
    # Add data labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'${height:,.2f}',
                   xy=(bar.get_x() + bar.get_width() / 2, height),
                   xytext=(0, 3),  # 3 points vertical offset
                   textcoords="offset points",
                   ha='center', va='bottom')
    
    plt.title('Pipeline Value by Stage')
    plt.xlabel('Stage')
    plt.ylabel('Value ($)')
    
    # Save to a BytesIO object
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    
    # Encode to base64
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return {"image": f"data:image/png;base64,{img_base64}"}

# Add advanced analytics endpoints
@app.get("/api/analytics/forecast", tags=["analytics"])
def get_pipeline_forecast(
    db: Session = Depends(get_session),
    days_history: int = 90,
    days_forecast: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get pipeline value forecast
    
    Returns a forecast of pipeline value for the next n days
    
    Parameters:
    - **days_history**: Number of days of historical data to use
    - **days_forecast**: Number of days to forecast
    """
    from app.utils.predictive_analytics import PredictiveAnalytics
    
    forecast = PredictiveAnalytics.forecast_pipeline_value(
        db, 
        days_history=days_history, 
        days_forecast=days_forecast
    )
    
    return forecast

@app.get("/api/analytics/sales-velocity", tags=["analytics"])
def get_sales_velocity(
    db: Session = Depends(get_session),
    days: int = 90,
    current_user: User = Depends(get_current_user)
):
    """
    Get sales velocity metrics
    
    Returns sales velocity metrics for the specified period
    
    Parameters:
    - **days**: Number of days to analyze
    """
    from app.utils.predictive_analytics import PredictiveAnalytics
    
    velocity_metrics = PredictiveAnalytics.analyze_sales_velocity(
        db, 
        days=days
    )
    
    return velocity_metrics

@app.get("/api/analytics/churn-risk", tags=["analytics"])
def get_churn_risk(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get client churn risk analysis
    
    Returns a list of clients with churn risk scores
    """
    from app.utils.predictive_analytics import PredictiveAnalytics
    
    client_risks = PredictiveAnalytics.predict_churn_risk(db)
    
    return client_risks

@app.get("/api/analytics/deal-predictions", tags=["analytics"])
def get_deal_predictions(
    db: Session = Depends(get_session),
    stage: str = 'proposed',
    current_user: User = Depends(get_current_user)
):
    """
    Get outcome predictions for deals
    
    Returns a list of deals with predicted outcomes
    
    Parameters:
    - **stage**: Deal stage to analyze (default: proposed)
    """
    from app.utils.predictive_analytics import PredictiveAnalytics
    
    deal_predictions = PredictiveAnalytics.forecast_deal_outcomes(
        db, 
        stage=stage
    )
    
    return deal_predictions

# Add PDF export endpoints
@app.get("/api/export/pipeline-summary-pdf", tags=["export"])
def export_pipeline_summary_pdf(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export pipeline summary as PDF
    
    Returns a downloadable PDF file with pipeline summary information
    """
    # Get pipeline summary
    pipeline_summary = crud.calculate_pipeline_value(db)
    
    # Format for the PDF generator
    pipeline_stats = {
        "stages": {
            "lead": {
                "count": sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "lead"),
                "value": pipeline_summary["lead"],
                "value_formatted": format_money(pipeline_summary["lead"])
            },
            "proposed": {
                "count": sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "proposed"),
                "value": pipeline_summary["proposed"],
                "value_formatted": format_money(pipeline_summary["proposed"])
            },
            "won": {
                "count": sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "won"),
                "value": pipeline_summary["won"],
                "value_formatted": format_money(pipeline_summary["won"])
            }
        },
        "total": {
            "count": len(crud.get_all(db, Deal)),
            "value": pipeline_summary["total"],
            "value_formatted": format_money(pipeline_summary["total"])
        }
    }
    
    # Company name (could be user's name or organization)
    company_name = f"{current_user.full_name}'s FreelanceFlow"
    
    # Generate PDF
    pdf_data = generate_pipeline_summary_pdf(pipeline_stats, company_name)
    
    # Return as downloadable file
    response = Response(content=pdf_data, media_type="application/pdf")
    response.headers["Content-Disposition"] = "attachment; filename=pipeline_summary.pdf"
    return response

@app.get("/api/export/client-distribution-pdf", tags=["export"])
def export_client_distribution_pdf(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export client distribution as PDF
    
    Returns a downloadable PDF file with client distribution information
    """
    # Get client distribution
    client_distribution = crud.get_client_distribution(db)
    
    # Company name
    company_name = f"{current_user.full_name}'s FreelanceFlow"
    
    # Generate PDF
    pdf_data = generate_client_distribution_pdf(client_distribution, company_name)
    
    # Return as downloadable file
    response = Response(content=pdf_data, media_type="application/pdf")
    response.headers["Content-Disposition"] = "attachment; filename=client_distribution.pdf"
    return response

@app.get("/api/export/dashboard-pdf", tags=["export"])
async def export_dashboard_pdf(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export complete dashboard as PDF
    
    Returns a downloadable PDF file with comprehensive dashboard information
    """
    # Get pipeline summary
    pipeline_summary = crud.calculate_pipeline_value(db)
    
    # Format for the PDF generator
    pipeline_stats = {
        "stages": {
            "lead": {
                "count": sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "lead"),
                "value": pipeline_summary["lead"],
                "value_formatted": format_money(pipeline_summary["lead"])
            },
            "proposed": {
                "count": sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "proposed"),
                "value": pipeline_summary["proposed"],
                "value_formatted": format_money(pipeline_summary["proposed"])
            },
            "won": {
                "count": sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "won"),
                "value": pipeline_summary["won"],
                "value_formatted": format_money(pipeline_summary["won"])
            }
        },
        "total": {
            "count": len(crud.get_all(db, Deal)),
            "value": pipeline_summary["total"],
            "value_formatted": format_money(pipeline_summary["total"])
        }
    }
    
    # Get client distribution
    client_distribution = crud.get_client_distribution(db)
    
    # Get chart images
    deals_chart_response = await get_deals_by_stage_chart(db, current_user)
    pipeline_chart_response = await get_pipeline_value_chart(db, current_user)
    
    deals_chart_url = deals_chart_response.get("image") if isinstance(deals_chart_response, dict) else None
    pipeline_chart_url = pipeline_chart_response.get("image") if isinstance(pipeline_chart_response, dict) else None
    
    # Company name
    company_name = f"{current_user.full_name}'s FreelanceFlow"
    
    # Generate PDF
    pdf_data = generate_dashboard_pdf(
        pipeline_stats, 
        client_distribution, 
        deals_chart_url, 
        pipeline_chart_url,
        company_name
    )
    
    # Return as downloadable file
    response = Response(content=pdf_data, media_type="application/pdf")
    response.headers["Content-Disposition"] = "attachment; filename=dashboard_report.pdf"
    return response

# Add Excel export endpoints
@app.get("/api/export/pipeline-summary-excel", tags=["export"])
def export_pipeline_summary_excel(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export pipeline summary as Excel
    
    Returns a downloadable Excel file with pipeline summary information
    """
    # Get pipeline summary
    pipeline_summary = crud.calculate_pipeline_value(db)
    
    # Format for the Excel generator
    pipeline_data = {
        'lead_count': sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "lead"),
        'proposed_count': sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "proposed"),
        'won_count': sum(1 for deal in crud.get_all(db, Deal) if deal.stage == "won"),
        'lead_value': pipeline_summary["lead"],
        'proposed_value': pipeline_summary["proposed"],
        'won_value': pipeline_summary["won"],
        'total_count': len(crud.get_all(db, Deal)),
        'total_value': pipeline_summary["total"]
    }
    
    # Generate Excel
    excel_data = generate_pipeline_excel(pipeline_data)
    
    # Return as downloadable file
    response = Response(content=excel_data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response.headers["Content-Disposition"] = "attachment; filename=pipeline_summary.xlsx"
    return response

@app.get("/api/export/client-distribution-excel", tags=["export"])
def export_client_distribution_excel(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export client distribution as Excel
    
    Returns a downloadable Excel file with client distribution information
    """
    # Get client distribution
    client_distribution = crud.get_client_distribution(db)
    
    # Generate Excel
    excel_data = generate_clients_excel(client_distribution)
    
    # Return as downloadable file
    response = Response(content=excel_data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response.headers["Content-Disposition"] = "attachment; filename=client_distribution.xlsx"
    return response

@app.get("/api/export/deals-excel", tags=["export"])
def export_deals_excel(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export deals as Excel
    
    Returns a downloadable Excel file with all deals information
    """
    # Get deals data
    deals_data = crud.get_deals_with_export_data(db)
    
    # Generate Excel
    excel_data = generate_deals_excel(deals_data)
    
    # Return as downloadable file
    response = Response(content=excel_data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response.headers["Content-Disposition"] = "attachment; filename=deals.xlsx"
    return response

# Role and Permission API endpoints
@app.get("/api/permissions/", response_model=List[PermissionRead], tags=["permissions"])
def get_permissions(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_permission("manage_permissions"))
):
    """Get all available permissions"""
    statement = select(Permission)
    permissions = db.exec(statement).all()
    return permissions

@app.post("/api/permissions/", response_model=PermissionRead, tags=["permissions"])
def create_permission(
    *,
    db: Session = Depends(get_session),
    permission_data: dict,
    current_user: User = Depends(require_permission("manage_permissions"))
):
    """Create a new permission"""
    # Check if permission already exists
    statement = select(Permission).where(Permission.name == permission_data["name"])
    existing_permission = db.exec(statement).first()
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Permission with name '{permission_data['name']}' already exists"
        )
    
    # Create new permission
    permission = Permission(
        name=permission_data["name"],
        description=permission_data["description"]
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    
    return permission

@app.get("/api/roles/", response_model=List[RoleRead], tags=["roles"])
def get_roles(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_permission("manage_roles"))
):
    """Get all roles with their permissions"""
    # Get all roles
    statement = select(Role)
    roles = db.exec(statement).all()
    
    # For each role, get its permissions
    result = []
    for role in roles:
        # Get role permissions
        statement = select(RolePermission).where(RolePermission.role_id == role.id)
        role_permissions = db.exec(statement).all()
        permission_ids = [rp.permission_id for rp in role_permissions]
        
        # Get permission details
        permissions = []
        if permission_ids:
            statement = select(Permission).where(Permission.id.in_(permission_ids))
            permissions = db.exec(statement).all()
        
        # Create response object
        role_data = {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_default": role.is_default,
            "permissions": permissions
        }
        result.append(role_data)
    
    return result

@app.post("/api/roles/", response_model=RoleRead, tags=["roles"])
def create_role(
    *,
    db: Session = Depends(get_session),
    role_data: RoleCreate,
    current_user: User = Depends(require_permission("manage_roles"))
):
    """Create a new role with permissions"""
    # Check if role already exists
    statement = select(Role).where(Role.name == role_data.name)
    existing_role = db.exec(statement).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{role_data.name}' already exists"
        )
    
    # Check if permissions exist
    if role_data.permissions:
        statement = select(Permission).where(Permission.id.in_(role_data.permissions))
        permissions = db.exec(statement).all()
        if len(permissions) != len(role_data.permissions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more permissions do not exist"
            )
    
    # Create new role
    role = Role(
        name=role_data.name,
        description=role_data.description,
        is_default=role_data.is_default
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    
    # Add permissions to role
    if role_data.permissions:
        for permission_id in role_data.permissions:
            role_permission = RolePermission(role_id=role.id, permission_id=permission_id)
            db.add(role_permission)
        db.commit()
    
    # Get permissions for response
    permissions = []
    if role_data.permissions:
        statement = select(Permission).where(Permission.id.in_(role_data.permissions))
        permissions = db.exec(statement).all()
    
    # Create response
    response = {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "is_default": role.is_default,
        "permissions": permissions
    }
    
    return response

@app.put("/api/roles/{role_id}", response_model=RoleRead, tags=["roles"])
def update_role(
    *,
    db: Session = Depends(get_session),
    role_id: int,
    role_data: RoleUpdate,
    current_user: User = Depends(require_permission("manage_roles"))
):
    """Update a role and its permissions"""
    # Get the role
    statement = select(Role).where(Role.id == role_id)
    role = db.exec(statement).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found"
        )
    
    # Update role attributes
    if role_data.name is not None:
        # Check if the new name already exists for another role
        statement = select(Role).where(Role.name == role_data.name, Role.id != role_id)
        existing_role = db.exec(statement).first()
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role with name '{role_data.name}' already exists"
            )
        role.name = role_data.name
    
    if role_data.description is not None:
        role.description = role_data.description
    
    if role_data.is_default is not None:
        role.is_default = role_data.is_default
    
    # Update permissions if provided
    if role_data.permissions is not None:
        # Check if all permissions exist
        if role_data.permissions:
            statement = select(Permission).where(Permission.id.in_(role_data.permissions))
            permissions = db.exec(statement).all()
            if len(permissions) != len(role_data.permissions):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more permissions do not exist"
                )
        
        # Remove existing role-permission relations
        statement = select(RolePermission).where(RolePermission.role_id == role_id)
        existing_role_permissions = db.exec(statement).all()
        for rp in existing_role_permissions:
            db.delete(rp)
        
        # Add new role-permission relations
        for permission_id in role_data.permissions:
            role_permission = RolePermission(role_id=role_id, permission_id=permission_id)
            db.add(role_permission)
    
    db.commit()
    db.refresh(role)
    
    # Get permissions for response
    permissions = []
    statement = select(RolePermission).where(RolePermission.role_id == role_id)
    role_permissions = db.exec(statement).all()
    permission_ids = [rp.permission_id for rp in role_permissions]
    
    if permission_ids:
        statement = select(Permission).where(Permission.id.in_(permission_ids))
        permissions = db.exec(statement).all()
    
    # Create response
    response = {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "is_default": role.is_default,
        "permissions": permissions
    }
    
    return response

@app.delete("/api/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["roles"])
def delete_role(
    *,
    db: Session = Depends(get_session),
    role_id: int,
    current_user: User = Depends(require_permission("manage_roles"))
):
    """Delete a role"""
    # Get the role
    statement = select(Role).where(Role.id == role_id)
    role = db.exec(statement).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found"
        )
    
    # Check if it's assigned to any users
    statement = select(UserRole).where(UserRole.role_id == role_id)
    user_roles = db.exec(statement).all()
    if user_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete role that is assigned to users"
        )
    
    # Delete role-permission relations
    statement = select(RolePermission).where(RolePermission.role_id == role_id)
    role_permissions = db.exec(statement).all()
    for rp in role_permissions:
        db.delete(rp)
    
    # Delete the role
    db.delete(role)
    db.commit()
    
    return None

@app.get("/api/users/{user_id}/roles", tags=["users", "roles"])
def get_user_roles(
    *,
    db: Session = Depends(get_session),
    user_id: int,
    current_user: User = Depends(require_permission("manage_users"))
):
    """Get roles assigned to a user"""
    # Check if user exists
    statement = select(User).where(User.id == user_id)
    user = db.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Get user roles
    statement = select(UserRole).where(UserRole.user_id == user_id)
    user_roles = db.exec(statement).all()
    role_ids = [ur.role_id for ur in user_roles]
    
    # Get role details
    roles = []
    if role_ids:
        statement = select(Role).where(Role.id.in_(role_ids))
        roles = db.exec(statement).all()
    
    return roles

@app.post("/api/users/{user_id}/roles", tags=["users", "roles"])
def assign_role_to_user(
    *,
    db: Session = Depends(get_session),
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_permission("manage_users"))
):
    """Assign a role to a user"""
    # Check if user exists
    statement = select(User).where(User.id == user_id)
    user = db.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Check if role exists
    statement = select(Role).where(Role.id == role_id)
    role = db.exec(statement).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found"
        )
    
    # Check if user already has this role
    statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    existing_user_role = db.exec(statement).first()
    if existing_user_role:
        return {"message": f"User already has role: {role.name}"}
    
    # Assign role to user
    user_role = UserRole(user_id=user_id, role_id=role_id)
    db.add(user_role)
    db.commit()
    
    return {"message": f"Role '{role.name}' assigned to user"}

@app.delete("/api/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["users", "roles"])
def remove_role_from_user(
    *,
    db: Session = Depends(get_session),
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_permission("manage_users"))
):
    """Remove a role from a user"""
    # Check if user exists
    statement = select(User).where(User.id == user_id)
    user = db.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Check if role exists
    statement = select(Role).where(Role.id == role_id)
    role = db.exec(statement).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found"
        )
    
    # Check if user has this role
    statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    user_role = db.exec(statement).first()
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User does not have role with ID {role_id}"
        )
    
    # Remove role from user
    db.delete(user_role)
    db.commit()
    
    return None

# Email notification settings endpoints
@app.get("/api/users/me/email-preferences", tags=["users", "email"])
def get_email_preferences(
    current_user: User = Depends(get_current_user)
):
    """Get current user's email notification preferences"""
    return {
        "email_notifications_enabled": current_user.email_notifications_enabled,
        "notify_on_deal_created": current_user.notify_on_deal_created,
        "notify_on_deal_updated": current_user.notify_on_deal_updated,
        "notify_on_deal_stage_changed": current_user.notify_on_deal_stage_changed,
        "notify_on_client_created": current_user.notify_on_client_created,
        "notify_on_client_updated": current_user.notify_on_client_updated,
        "notify_on_invoice_created": current_user.notify_on_invoice_created,
        "notify_on_invoice_paid": current_user.notify_on_invoice_paid,
        "notify_on_task_completed": current_user.notify_on_task_completed
    }

@app.patch("/api/users/me/email-preferences", tags=["users", "email"])
def update_email_preferences(
    preferences: Dict[str, bool],
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update current user's email notification preferences"""
    # Get the user to update
    statement = select(User).where(User.id == current_user.id)
    user = db.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update notification preferences
    valid_fields = [
        "email_notifications_enabled",
        "notify_on_deal_created",
        "notify_on_deal_updated",
        "notify_on_deal_stage_changed",
        "notify_on_client_created",
        "notify_on_client_updated",
        "notify_on_invoice_created",
        "notify_on_invoice_paid",
        "notify_on_task_completed"
    ]
    
    for field_name, value in preferences.items():
        if field_name in valid_fields:
            setattr(user, field_name, value)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "email_notifications_enabled": user.email_notifications_enabled,
        "notify_on_deal_created": user.notify_on_deal_created,
        "notify_on_deal_updated": user.notify_on_deal_updated,
        "notify_on_deal_stage_changed": user.notify_on_deal_stage_changed,
        "notify_on_client_created": user.notify_on_client_created,
        "notify_on_client_updated": user.notify_on_client_updated,
        "notify_on_invoice_created": user.notify_on_invoice_created,
        "notify_on_invoice_paid": user.notify_on_invoice_paid,
        "notify_on_task_completed": user.notify_on_task_completed
    }

# Add this route for the email preferences page
@app.get("/email-preferences", response_class=HTMLResponse)
async def email_preferences_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_from_cookie)
):
    """Email preferences page"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse(
        "email_preferences.html",
        {"request": request, "current_user": current_user}
    )

# Add this endpoint for sending a test email
@app.post("/api/users/me/send-test-email", tags=["users", "email"])
async def send_test_email(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Send a test email to the current user"""
    if not current_user.email_notifications_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email notifications are disabled"
        )
    
    from app.utils.email_service import EmailSchema, send_email
    
    # Create test email
    email = EmailSchema(
        recipient=[current_user.email],
        subject="FreelanceFlow Test Email",
        body="",
        template_name="test_email",
        template_data={
            "user_name": current_user.full_name or current_user.email,
            "app_name": "FreelanceFlow",
            "preferences_url": "https://yourapp.com/email-preferences"
        }
    )
    
    # Send email in background
    background_tasks.add_task(send_email, email)
    
    return {"message": "Test email sent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 