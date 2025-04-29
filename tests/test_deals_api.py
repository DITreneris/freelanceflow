import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import Deal, Client, User

# Setup test database
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
        
        # Create test client
        test_client = Client(
            name="Test Client",
            email="client@example.com",
            phone="123-456-7890",
            user_id=test_user.id
        )
        session.add(test_client)
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

def test_create_deal(client: TestClient, session: Session):
    # Get the test client
    db_client = session.query(Client).first()
    
    # Create a new deal
    deal_data = {
        "client_id": db_client.id,
        "stage": "lead",
        "value": 10000  # $100.00
    }
    
    response = client.post("/api/deals/", json=deal_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["client_id"] == db_client.id
    assert data["stage"] == "lead"
    assert data["value"] == 10000
    
    # Check if deal was added to database
    db_deal = session.get(Deal, data["id"])
    assert db_deal is not None
    assert db_deal.value == 10000

def test_read_deals(client: TestClient, session: Session):
    # Get the test client
    db_client = session.query(Client).first()
    
    # Create test deals
    test_deals = [
        Deal(client_id=db_client.id, stage="lead", value=10000),
        Deal(client_id=db_client.id, stage="proposed", value=20000),
        Deal(client_id=db_client.id, stage="won", value=30000)
    ]
    
    session.add_all(test_deals)
    session.commit()
    
    # Get all deals
    response = client.get("/api/deals/")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 3
    
    # Test filtering by stage
    response = client.get("/api/deals/?stage=lead")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["stage"] == "lead"

def test_update_deal(client: TestClient, session: Session):
    # Get the test client
    db_client = session.query(Client).first()
    
    # Create a test deal
    test_deal = Deal(client_id=db_client.id, stage="lead", value=10000)
    session.add(test_deal)
    session.commit()
    
    # Update the deal
    update_data = {
        "stage": "proposed",
        "value": 15000
    }
    
    response = client.patch(f"/api/deals/{test_deal.id}", json=update_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["stage"] == "proposed"
    assert data["value"] == 15000
    
    # Verify in database
    db_deal = session.get(Deal, test_deal.id)
    assert db_deal.stage == "proposed"
    assert db_deal.value == 15000

def test_move_deal(client: TestClient, session: Session):
    # Get the test client
    db_client = session.query(Client).first()
    
    # Create a test deal
    test_deal = Deal(client_id=db_client.id, stage="lead", value=10000)
    session.add(test_deal)
    session.commit()
    
    # Move the deal to a new stage
    move_data = {
        "new_stage": "won"
    }
    
    response = client.patch(f"/api/deals/{test_deal.id}/move", json=move_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["stage"] == "won"
    
    # Verify in database
    db_deal = session.get(Deal, test_deal.id)
    assert db_deal.stage == "won"

def test_delete_deal(client: TestClient, session: Session):
    # Get the test client
    db_client = session.query(Client).first()
    
    # Create a test deal
    test_deal = Deal(client_id=db_client.id, stage="lead", value=10000)
    session.add(test_deal)
    session.commit()
    
    # Delete the deal
    response = client.delete(f"/api/deals/{test_deal.id}")
    assert response.status_code == 200
    
    # Verify it's deleted
    db_deal = session.get(Deal, test_deal.id)
    assert db_deal is None 