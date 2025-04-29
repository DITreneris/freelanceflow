from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, Dict
from datetime import datetime, date
from enum import Enum

class Permission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str
    
    # Relationships
    roles: List["RolePermission"] = Relationship(back_populates="permission")

class Role(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str
    is_default: bool = Field(default=False)
    
    # Relationships
    users: List["UserRole"] = Relationship(back_populates="role")
    permissions: List["RolePermission"] = Relationship(back_populates="role")

class RolePermission(SQLModel, table=True):
    role_id: int = Field(foreign_key="role.id", primary_key=True)
    permission_id: int = Field(foreign_key="permission.id", primary_key=True)
    
    # Relationships
    role: Role = Relationship(back_populates="permissions")
    permission: Permission = Relationship(back_populates="roles")

class UserRole(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role_id: int = Field(foreign_key="role.id", primary_key=True)
    
    # Relationships
    user: "User" = Relationship(back_populates="roles")
    role: Role = Relationship(back_populates="users")

class UserBase(SQLModel):
    email: str
    is_active: bool = True
    is_superuser: bool = False
    full_name: Optional[str] = None
    email_notifications_enabled: bool = True  # Enable email notifications by default

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    email: str = Field(index=True)
    
    # Email notification preferences
    email_notifications_enabled: bool = Field(default=True)  # Master toggle for all email notifications
    notify_on_deal_created: bool = Field(default=True)
    notify_on_deal_updated: bool = Field(default=True)
    notify_on_deal_stage_changed: bool = Field(default=True)
    notify_on_client_created: bool = Field(default=False)
    notify_on_client_updated: bool = Field(default=False)
    notify_on_invoice_created: bool = Field(default=True)
    notify_on_invoice_paid: bool = Field(default=True)
    notify_on_task_completed: bool = Field(default=False)
    
    # Relationships
    clients: List["Client"] = Relationship(back_populates="user")
    notifications: List["Notification"] = Relationship(back_populates="user")
    roles: List[UserRole] = Relationship(back_populates="user")

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    email_notifications_enabled: bool
    notify_on_deal_created: bool
    notify_on_deal_updated: bool
    notify_on_deal_stage_changed: bool
    notify_on_client_created: bool
    notify_on_client_updated: bool
    notify_on_invoice_created: bool
    notify_on_invoice_paid: bool
    notify_on_task_completed: bool

class UserUpdate(SQLModel):
    email: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    email_notifications_enabled: Optional[bool] = None
    notify_on_deal_created: Optional[bool] = None
    notify_on_deal_updated: Optional[bool] = None
    notify_on_deal_stage_changed: Optional[bool] = None
    notify_on_client_created: Optional[bool] = None
    notify_on_client_updated: Optional[bool] = None
    notify_on_invoice_created: Optional[bool] = None
    notify_on_invoice_paid: Optional[bool] = None
    notify_on_task_completed: Optional[bool] = None

# Roles and permissions schemas
class PermissionRead(SQLModel):
    id: int
    name: str
    description: str

class RoleCreate(SQLModel):
    name: str
    description: str
    is_default: bool = False
    permissions: List[int] = []  # List of permission IDs

class RoleRead(SQLModel):
    id: int
    name: str
    description: str
    is_default: bool
    permissions: List[PermissionRead] = []

class RoleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    permissions: Optional[List[int]] = None  # List of permission IDs

class ClientBase(SQLModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    user_id: int = Field(foreign_key="user.id")

class Client(ClientBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    name: str = Field(index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    # Relationships
    user: User = Relationship(back_populates="clients")
    deals: List["Deal"] = Relationship(back_populates="client")
    invoices: List["Invoice"] = Relationship(back_populates="client")
    tasks: List["Task"] = Relationship(back_populates="client")

class ClientCreate(ClientBase):
    pass

class ClientRead(ClientBase):
    id: int
    created_at: datetime
    updated_at: datetime

class ClientUpdate(SQLModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DealStage(str, Enum):
    LEAD = "lead"
    PROPOSED = "proposed"
    WON = "won"

class DealBase(SQLModel):
    client_id: int = Field(foreign_key="client.id")
    stage: str = Field(default=DealStage.LEAD)
    value: int  # Stored in cents

class Deal(DealBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    stage: str = Field(index=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    
    # Relationships
    client: Client = Relationship(back_populates="deals")

class DealCreate(DealBase):
    pass

class DealRead(DealBase):
    id: int
    created_at: datetime
    updated_at: datetime

class DealUpdate(SQLModel):
    stage: Optional[str] = None
    value: Optional[int] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DealMoveUpdate(SQLModel):
    new_stage: str

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    number: str = Field(index=True)
    total: int  # cents
    pdf_url: str
    due_date: date = Field(index=True)
    status: str = Field(index=True)
    
    # Relationships
    client: Client = Relationship(back_populates="invoices")
    items: List["InvoiceItem"] = Relationship(back_populates="invoice")

class InvoiceItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    description: str
    qty: int
    unit_price: int  # cents
    
    # Relationships
    invoice: Invoice = Relationship(back_populates="items")

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="client.id", index=True)
    title: str
    due_date: Optional[date] = Field(default=None, index=True)
    done: bool = Field(default=False, index=True)
    
    # Relationships
    client: Optional[Client] = Relationship(back_populates="tasks")

class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = None
    path: str
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class NotificationType(str, Enum):
    DEAL_CREATED = "deal_created"
    DEAL_UPDATED = "deal_updated"
    DEAL_STAGE_CHANGED = "deal_stage_changed"
    CLIENT_CREATED = "client_created"
    CLIENT_UPDATED = "client_updated"
    INVOICE_CREATED = "invoice_created"
    INVOICE_PAID = "invoice_paid"
    TASK_COMPLETED = "task_completed"

class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    type: str = Field(index=True)  # Use NotificationType values
    title: str
    message: str
    entity_type: str  # e.g., "deal", "client", "invoice"
    entity_id: int
    is_read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="notifications") 