# FreelanceFlow

An all-in-one freelance business management system that helps freelancers and small agencies track clients, deals, and finances.

## Features

- **Authentication**: Google OAuth2 with JWT tokens
- **Client Management**: Comprehensive CRUD operations for managing clients
- **Deal Management**: Kanban board for visualizing and managing deal pipeline
- **Analytics Dashboard**: Advanced analytics with predictive capabilities
  - Sales forecasting
  - Client churn risk analysis
  - Deal outcome predictions
  - Sales velocity metrics
- **Email Notifications**: Customizable email notifications for deal updates
- **Data Export**: PDF, CSV, and Excel export functionality
- **Role-based Access Control**: Different permission levels for team members
- **Responsive Design**: Optimized for both desktop and mobile devices

## Tech Stack

- **Backend**: FastAPI, SQLModel, Python 3.11+
- **Frontend**: Alpine.js, HTMX, Tailwind CSS, Jinja2
- **Database**: SQLite (development), PostgreSQL (production)
- **Authentication**: Google OAuth2, JWT
- **Analytics**: NumPy, pandas, matplotlib
- **Testing**: pytest, pytest-cov

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Installation

1. Clone the repository
   ```
   git clone https://github.com/DITreneris/freelanceflow.git
   cd freelanceflow
   ```

2. Create and activate a virtual environment
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables (create a `.env` file)
   ```
   DATABASE_URL=sqlite:///./app.db
   SECRET_KEY=your_secret_key_here
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   EMAIL_HOST=smtp.example.com
   EMAIL_PORT=587
   EMAIL_USERNAME=your_email@example.com
   EMAIL_PASSWORD=your_email_password
   ```

5. Run the application
   ```
   uvicorn app.main:app --reload
   ```

6. Open your browser and navigate to `http://localhost:8000`

## Development

### Running Tests

```
pytest
```

### Code Quality

We use pre-commit hooks to ensure code quality:

```
pre-commit install
pre-commit run --all-files
```

## Documentation

API documentation is available at `/docs` or `/redoc` when the application is running.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all contributors who have helped shape FreelanceFlow. 