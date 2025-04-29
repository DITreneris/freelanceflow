from sqlmodel import Session, select, func
from typing import List, Optional, Type, TypeVar, Dict, Any
from app.models import Client, Deal, Invoice, InvoiceItem, Task, Feedback, User
from app.utils import format_money, format_date, truncate_text

T = TypeVar('T')

# Generic CRUD operations
def get_by_id(db: Session, model: Type[T], id: int) -> Optional[T]:
    """Get a record by ID"""
    try:
        return db.get(model, id)
    except Exception as e:
        # Log the error for debugging
        print(f"Error getting {model.__name__} with id {id}: {str(e)}")
        return None

def get_all(db: Session, model: Type[T], skip: int = 0, limit: int = 100, order_by: str = None) -> List[T]:
    """
    Get all records of a model with pagination and optional ordering
    
    Args:
        db: Database session
        model: The model class
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        order_by: Field name to order results by (prefix with '-' for descending order)
    """
    try:
        statement = select(model)
        
        # Add ordering if specified
        if order_by:
            # Handle descending order (field name prefixed with '-')
            if order_by.startswith('-'):
                field_name = order_by[1:]
                statement = statement.order_by(getattr(model, field_name).desc())
            else:
                statement = statement.order_by(getattr(model, order_by))
        
        # Add pagination
        statement = statement.offset(skip).limit(limit)
        
        return db.exec(statement).all()
    except Exception as e:
        # Log the error for debugging
        print(f"Error getting all {model.__name__}: {str(e)}")
        return []

def create(db: Session, obj_in: T) -> T:
    """Create a new record"""
    try:
        db.add(obj_in)
        db.commit()
        db.refresh(obj_in)
        return obj_in
    except Exception as e:
        db.rollback()
        # Log the error for debugging
        print(f"Error creating {type(obj_in).__name__}: {str(e)}")
        raise

def update(db: Session, db_obj: T, update_data: dict) -> T:
    """Update an existing record"""
    try:
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    except Exception as e:
        db.rollback()
        # Log the error for debugging
        print(f"Error updating {type(db_obj).__name__} with id {getattr(db_obj, 'id', 'unknown')}: {str(e)}")
        raise

def delete(db: Session, model: Type[T], id: int) -> bool:
    """
    Delete a record by ID
    
    Returns True if the record was deleted, False otherwise
    """
    try:
        obj = db.get(model, id)
        if obj:
            db.delete(obj)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        # Log the error for debugging
        print(f"Error deleting {model.__name__} with id {id}: {str(e)}")
        raise

# Specific operations
def get_clients_with_export_data(db: Session) -> List[dict]:
    """Get clients with data formatted for CSV export"""
    statement = select(Client)
    clients = db.exec(statement).all()
    
    # Convert clients to dict for CSV export
    result = []
    for client in clients:
        client_dict = {
            "id": client.id,
            "name": client.name, 
            "email": client.email or "",
            "phone": client.phone or "",
            "notes": client.notes or "",
            "created_at": client.created_at.isoformat() if client.created_at else ""
        }
        result.append(client_dict)
    
    return result

def get_invoices_with_export_data(db: Session) -> List[dict]:
    """Get invoices with data formatted for CSV export"""
    statement = select(Invoice)
    invoices = db.exec(statement).all()
    
    # Convert invoices to dict for CSV export
    result = []
    for invoice in invoices:
        client = invoice.client
        invoice_dict = {
            "id": invoice.id,
            "client_name": client.name if client else "",
            "invoice_number": invoice.number,
            "total": invoice.total / 100,  # Convert cents to dollars/euros
            "status": invoice.status,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else ""
        }
        result.append(invoice_dict)
    
    return result

def get_deals_with_export_data(db: Session) -> List[dict]:
    """Get deals with data formatted for CSV export"""
    statement = select(Deal)
    deals = db.exec(statement).all()
    
    # Convert deals to dict for CSV export
    result = []
    for deal in deals:
        client = deal.client
        deal_dict = {
            "id": deal.id,
            "client_name": client.name if client else "",
            "stage": deal.stage,
            "value": deal.value / 100,  # Convert cents to dollars/euros
            "value_formatted": format_money(deal.value),
            "updated_at": format_date(deal.updated_at) if deal.updated_at else ""
        }
        result.append(deal_dict)
    
    return result

def get_deals_by_stage(db: Session) -> Dict[str, List[Dict[str, Any]]]:
    """Get all deals organized by stage with client information"""
    try:
        # More efficient query: join once and organize in Python
        statement = select(Deal, Client).join(Client, Deal.client_id == Client.id)
        results = db.exec(statement).all()
        
        # Initialize result dictionary with empty lists for each stage
        deals_by_stage = {
            "lead": [],
            "proposed": [],
            "won": []
        }
        
        # Organize deals by stage
        for deal, client in results:
            deal_dict = {
                "id": deal.id,
                "client_id": deal.client_id,
                "client_name": client.name,
                "value": deal.value,
                "value_formatted": format_money(deal.value),
                "updated_at": format_date(deal.updated_at) if deal.updated_at else "",
                # Add any other needed fields
            }
            deals_by_stage[deal.stage].append(deal_dict)
        
        return deals_by_stage
    except Exception as e:
        # Log the error for debugging
        print(f"Error getting deals by stage: {str(e)}")
        # Return empty structure on error
        return {"lead": [], "proposed": [], "won": []}

def calculate_pipeline_value(db: Session) -> Dict[str, int]:
    """Calculate the total value of deals in each stage"""
    try:
        # More efficient: use SQL aggregation instead of Python iteration
        lead_value = db.query(func.sum(Deal.value)).filter(Deal.stage == "lead").scalar() or 0
        proposed_value = db.query(func.sum(Deal.value)).filter(Deal.stage == "proposed").scalar() or 0
        won_value = db.query(func.sum(Deal.value)).filter(Deal.stage == "won").scalar() or 0
        
        # Return dictionary with values
        total = lead_value + proposed_value + won_value
        return {
            "lead": lead_value,
            "proposed": proposed_value,
            "won": won_value,
            "total": total
        }
    except Exception as e:
        # Log the error for debugging
        print(f"Error calculating pipeline value: {str(e)}")
        # Return zeroes on error
        return {"lead": 0, "proposed": 0, "won": 0, "total": 0}

# User operations
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email"""
    statement = select(User).where(User.email == email)
    return db.exec(statement).first()

def get_client_distribution(db: Session) -> List[Dict[str, Any]]:
    """Get client distribution for reporting"""
    try:
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
                "total_value": data["total_value"],
                "total_value_formatted": format_money(data["total_value"])
            }
            for client_id, data in client_data.items()
        ]
        
        clients_list.sort(key=lambda x: x["total_value"], reverse=True)
        
        return clients_list
    except Exception as e:
        # Log the error for debugging
        print(f"Error getting client distribution: {str(e)}")
        return [] 