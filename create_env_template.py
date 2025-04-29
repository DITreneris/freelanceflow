#!/usr/bin/env python
"""
Script to generate environment templates for development and production
"""

development_template = """# FreelanceFlow Development Environment Configuration
# For local development with SQLite

# Database Configuration
DATABASE_URL=sqlite:///./app.db
DATABASE_CONNECT_ARGS={"check_same_thread": false}

# Security Settings
SECRET_KEY=dev_secret_key_replace_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours for development
SECURE_COOKIES=false  # false for development

# Google OAuth2 Settings
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Email Settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_FROM=FreelanceFlow Development <your_email@gmail.com>
EMAIL_TLS=true
EMAIL_SSL=false

# Application Settings
APP_NAME=FreelanceFlow
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
WORKERS=1

# Analytics Settings
ENABLE_ANALYTICS_CACHING=false
"""

production_template = """# FreelanceFlow Production Environment Configuration
# For deployment on Render with Neon PostgreSQL
# IMPORTANT: Replace placeholder values with actual secure values

# Database Configuration
# Format for Neon PostgreSQL: postgresql://user:password@endpoint-id.us-west-2.aws.neon.tech/neondb
DATABASE_URL=postgresql://your-user:your-password@your-db-hostname/your-db-name
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_RECYCLE=300
DATABASE_SSL_REQUIRED=true

# Security Settings
SECRET_KEY=replace_with_secure_random_string_min_32_chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
SECURE_COOKIES=true
CORS_ORIGINS=https://your-render-app-name.onrender.com

# Google OAuth2 Settings
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://your-render-app-name.onrender.com/auth/callback

# Email Settings
EMAIL_HOST=smtp.provider.com
EMAIL_PORT=587
EMAIL_USERNAME=notifications@your-domain.com
EMAIL_PASSWORD=your_secure_email_password
EMAIL_FROM=FreelanceFlow <notifications@your-domain.com>
EMAIL_TLS=true
EMAIL_SSL=false

# Application Settings
APP_NAME=FreelanceFlow
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
WORKERS=4

# Render Specific Settings
PORT=10000  # Render assigns a port via the PORT environment variable

# Performance Settings
ENABLE_RESPONSE_COMPRESSION=true
CACHE_TTL=300
RATE_LIMIT_PER_MINUTE=60

# Analytics Settings
ENABLE_ANALYTICS_CACHING=true
ANALYTICS_CACHE_TTL=3600
"""

render_yaml = """# Render configuration file (render.yaml)
services:
  - type: web
    name: freelanceflow
    env: python
    buildCommand: pip install -r requirements.txt && python -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" >> .env
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DATABASE_URL
        fromDatabase:
          name: freelanceflow-db
          property: connectionString
      - key: GOOGLE_CLIENT_ID
        sync: false
      - key: GOOGLE_CLIENT_SECRET
        sync: false
      - key: EMAIL_USERNAME
        sync: false
      - key: EMAIL_PASSWORD
        sync: false
    autoDeploy: true

databases:
  - name: freelanceflow-db
    databaseName: freelanceflow
    user: freelanceflow_user
    plan: free
"""

with open('.env.development.template', 'w') as f:
    f.write(development_template)

with open('.env.production.template', 'w') as f:
    f.write(production_template)

with open('render.yaml', 'w') as f:
    f.write(render_yaml)

print("Environment templates created:")
print("- .env.development.template (SQLite)")
print("- .env.production.template (Neon PostgreSQL)")
print("- render.yaml (Render deployment configuration)") 