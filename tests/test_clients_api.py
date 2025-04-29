import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import Client, User

# Setup test database with the same fixtures
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Create test user
        test_user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            full_name="Test User"
        )
        session.add(test_user)
        session.commit()
        
        yield session

# Setup test client with dependency override
@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_create_client(client: TestClient, session: Session):
    """Test creating a new client"""
    # Get the test user
    db_user = session.query(User).first()
    
    # Create a new client
    client_data = {
        "name": "New Test Client",
        "email": "newclient@example.com",
        "phone": "555-1234",
        "notes": "Test notes",
        "user_id": db_user.id
    }
    
    response = client.post("/api/clients/", json=client_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "New Test Client"
    assert data["email"] == "newclient@example.com"
    assert data["phone"] == "555-1234"
    
    # Check if client was added to database
    db_client = session.get(Client, data["id"])
    assert db_client is not None
    assert db_client.name == "New Test Client"

def test_read_clients(client: TestClient, session: Session):
    """Test reading all clients"""
    # Get the test user
    db_user = session.query(User).first()
    
    # Create test clients
    test_clients = [
        Client(name="Client 1", email="client1@example.com", user_id=db_user.id),
        Client(name="Client 2", email="client2@example.com", user_id=db_user.id),
        Client(name="Client 3", email="client3@example.com", user_id=db_user.id)
    ]
    
    session.add_all(test_clients)
    session.commit()
    
    # Get all clients
    response = client.get("/api/clients/")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) >= 3  # We might have clients from other tests
    
    # Check if our test clients are in the response
    client_names = [c["name"] for c in data]
    assert "Client 1" in client_names
    assert "Client 2" in client_names
    assert "Client 3" in client_names

def test_read_client(client: TestClient, session: Session):
    """Test reading a single client"""
    # Get the test user
    db_user = session.query(User).first()
    
    # Create a test client
    test_client = Client(
        name="Single Client", 
        email="single@example.com", 
        phone="123-456-7890",
        notes="Test notes",
        user_id=db_user.id
    )
    session.add(test_client)
    session.commit()
    
    # Get the client
    response = client.get(f"/api/clients/{test_client.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "Single Client"
    assert data["email"] == "single@example.com"
    assert data["phone"] == "123-456-7890"
    assert data["notes"] == "Test notes"

def test_update_client(client: TestClient, session: Session):
    """Test updating a client"""
    # Get the test user
    db_user = session.query(User).first()
    
    # Create a test client
    test_client = Client(
        name="Update Client", 
        email="update@example.com", 
        user_id=db_user.id
    )
    session.add(test_client)
    session.commit()
    
    # Update the client
    update_data = {
        "name": "Updated Name",
        "email": "updated@example.com",
        "phone": "999-888-7777"
    }
    
    response = client.patch(f"/api/clients/{test_client.id}", json=update_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["email"] == "updated@example.com"
    assert data["phone"] == "999-888-7777"
    
    # Verify in database
    db_client = session.get(Client, test_client.id)
    assert db_client.name == "Updated Name"
    assert db_client.email == "updated@example.com"
    assert db_client.phone == "999-888-7777"

def test_delete_client(client: TestClient, session: Session):
    """Test deleting a client"""
    # Get the test user
    db_user = session.query(User).first()
    
    # Create a test client
    test_client = Client(
        name="Delete Client", 
        email="delete@example.com", 
        user_id=db_user.id
    )
    session.add(test_client)
    session.commit()
    
    # Delete the client
    response = client.delete(f"/api/clients/{test_client.id}")
    assert response.status_code == 200
    
    # Verify it's deleted
    db_client = session.get(Client, test_client.id)
    assert db_client is None 