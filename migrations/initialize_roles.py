"""
Initialize roles and permissions for the application.
"""

from sqlmodel import Session, select
from app.database import engine
from app.models import User, Role, Permission, RolePermission
from app.auth import get_password_hash

def initialize_permissions(session: Session):
    """Create initial permissions"""
    # Define permissions
    permissions = [
        # User management
        {"name": "view_users", "description": "View all users"},
        {"name": "manage_users", "description": "Create, update, and delete users"},
        
        # Role management
        {"name": "view_roles", "description": "View all roles"},
        {"name": "manage_roles", "description": "Create, update, and delete roles"},
        {"name": "manage_permissions", "description": "Create and assign permissions"},
        
        # Client management
        {"name": "view_clients", "description": "View all clients"},
        {"name": "create_clients", "description": "Create new clients"},
        {"name": "update_clients", "description": "Update existing clients"},
        {"name": "delete_clients", "description": "Delete clients"},
        
        # Deal management
        {"name": "view_deals", "description": "View all deals"},
        {"name": "create_deals", "description": "Create new deals"},
        {"name": "update_deals", "description": "Update existing deals"},
        {"name": "delete_deals", "description": "Delete deals"},
        
        # Invoice management
        {"name": "view_invoices", "description": "View all invoices"},
        {"name": "create_invoices", "description": "Create new invoices"},
        {"name": "update_invoices", "description": "Update existing invoices"},
        {"name": "delete_invoices", "description": "Delete invoices"},
        
        # Analytics
        {"name": "view_analytics", "description": "View analytics data"},
        {"name": "export_reports", "description": "Export reports (PDF, Excel, CSV)"},
    ]
    
    # Create permissions
    created_permissions = {}
    for perm in permissions:
        # Check if permission already exists
        statement = select(Permission).where(Permission.name == perm["name"])
        existing_permission = session.exec(statement).first()
        
        if not existing_permission:
            permission = Permission(
                name=perm["name"],
                description=perm["description"]
            )
            session.add(permission)
            session.commit()
            session.refresh(permission)
            created_permissions[perm["name"]] = permission
        else:
            created_permissions[perm["name"]] = existing_permission
    
    return created_permissions

def initialize_roles(session: Session, permissions: dict):
    """Create initial roles and assign permissions"""
    # Define roles with permissions
    roles = [
        {
            "name": "Admin",
            "description": "Full access to all features",
            "is_default": False,
            "permissions": [perm for perm in permissions.values()]
        },
        {
            "name": "Manager",
            "description": "Can manage clients, deals, and view analytics",
            "is_default": False,
            "permissions": [
                permissions.get("view_users"),
                permissions.get("view_clients"),
                permissions.get("create_clients"),
                permissions.get("update_clients"),
                permissions.get("delete_clients"),
                permissions.get("view_deals"),
                permissions.get("create_deals"),
                permissions.get("update_deals"),
                permissions.get("delete_deals"),
                permissions.get("view_invoices"),
                permissions.get("create_invoices"),
                permissions.get("update_invoices"),
                permissions.get("view_analytics"),
                permissions.get("export_reports")
            ]
        },
        {
            "name": "Sales",
            "description": "Can manage deals and clients",
            "is_default": True,
            "permissions": [
                permissions.get("view_clients"),
                permissions.get("create_clients"),
                permissions.get("update_clients"),
                permissions.get("view_deals"),
                permissions.get("create_deals"),
                permissions.get("update_deals"),
                permissions.get("view_invoices"),
                permissions.get("view_analytics")
            ]
        },
        {
            "name": "Finance",
            "description": "Can manage invoices and view analytics",
            "is_default": False,
            "permissions": [
                permissions.get("view_clients"),
                permissions.get("view_deals"),
                permissions.get("view_invoices"),
                permissions.get("create_invoices"),
                permissions.get("update_invoices"),
                permissions.get("delete_invoices"),
                permissions.get("view_analytics"),
                permissions.get("export_reports")
            ]
        },
        {
            "name": "Viewer",
            "description": "Read-only access to clients and deals",
            "is_default": False,
            "permissions": [
                permissions.get("view_clients"),
                permissions.get("view_deals"),
                permissions.get("view_invoices"),
                permissions.get("view_analytics")
            ]
        }
    ]
    
    # Create roles and assign permissions
    created_roles = {}
    for role_data in roles:
        # Check if role already exists
        statement = select(Role).where(Role.name == role_data["name"])
        existing_role = session.exec(statement).first()
        
        if not existing_role:
            # Create new role
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                is_default=role_data["is_default"]
            )
            session.add(role)
            session.commit()
            session.refresh(role)
            
            # Assign permissions to role
            for permission in role_data["permissions"]:
                if permission:
                    role_permission = RolePermission(
                        role_id=role.id,
                        permission_id=permission.id
                    )
                    session.add(role_permission)
            
            session.commit()
            created_roles[role_data["name"]] = role
        else:
            created_roles[role_data["name"]] = existing_role
    
    return created_roles

def create_admin_user(session: Session, admin_role: Role):
    """Create an admin user if one doesn't exist"""
    # Check if admin user already exists
    statement = select(User).where(User.is_superuser == True)
    admin_user = session.exec(statement).first()
    
    if not admin_user:
        # Create admin user
        admin_email = "admin@example.com"
        admin_user = User(
            email=admin_email,
            hashed_password=get_password_hash("admin123"),  # Change in production
            is_active=True,
            is_superuser=True,
            full_name="System Administrator"
        )
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        
        print(f"Created admin user: {admin_email}")
        return admin_user
    
    return admin_user

def run_migrations():
    """Run all migrations"""
    with Session(engine) as session:
        print("Initializing permissions...")
        permissions = initialize_permissions(session)
        
        print("Initializing roles...")
        roles = initialize_roles(session, permissions)
        
        print("Creating admin user...")
        admin_user = create_admin_user(session, roles.get("Admin"))
        
        print("Migrations completed successfully!")

if __name__ == "__main__":
    run_migrations() 