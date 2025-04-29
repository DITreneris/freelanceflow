import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import User
from app.auth import get_password_hash, create_access_token, verify_password

# Setup test database
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Create test user with known password
        test_user = User(
            email="test@example.com",
            hashed_password=get_password_hash("testpassword"),
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

def test_token_generation(session: Session):
    """Test JWT token generation"""
    token = create_access_token({"sub": "test@example.com"})
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0

def test_password_verification():
    """Test password verification works correctly"""
    password = "testpassword"
    hashed_password = get_password_hash(password)
    
    # Verify correct password
    assert verify_password(password, hashed_password) is True
    
    # Verify incorrect password
    assert verify_password("wrongpassword", hashed_password) is False

def test_login_success(client: TestClient):
    """Test successful login with correct credentials"""
    response = client.post(
        "/token",
        data={"username": "test@example.com", "password": "testpassword"},
    )
    assert response.status_code == 200
    
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"

def test_login_failure_wrong_password(client: TestClient):
    """Test login failure with wrong password"""
    response = client.post(
        "/token",
        data={"username": "test@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401

def test_login_failure_wrong_email(client: TestClient):
    """Test login failure with non-existent email"""
    response = client.post(
        "/token",
        data={"username": "nonexistent@example.com", "password": "testpassword"},
    )
    assert response.status_code == 401

def test_protected_route_with_token(client: TestClient, session: Session):
    """Test accessing a protected route with a valid token"""
    # First login to get a token
    response = client.post(
        "/token",
        data={"username": "test@example.com", "password": "testpassword"},
    )
    assert response.status_code == 200
    
    token_data = response.json()
    token = token_data["access_token"]
    
    # Now access a protected route
    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "test@example.com"

def test_protected_route_without_token(client: TestClient):
    """Test that protected routes require a token"""
    response = client.get("/api/me")
    assert response.status_code == 401 