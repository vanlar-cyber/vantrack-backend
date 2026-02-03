# VanTrack Backend API

FastAPI backend for VanTrack financial tracking application.

## Requirements

- Python 3.11+
- PostgreSQL 16+
- Docker & Docker Compose (recommended)

## Quick Start with Docker

1. Copy environment file:
```bash
cp .env.example .env
```

2. Update `.env` with your settings (especially `GEMINI_API_KEY`)

3. Start services:
```bash
docker-compose up -d
```

4. API will be available at `http://localhost:8000`
5. API docs at `http://localhost:8000/docs`

## Local Development (without Docker)

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start PostgreSQL (ensure it's running on localhost:5432)

4. Run migrations:
```bash
alembic upgrade head
```

5. Start the server:
```bash
uvicorn app.main:app --reload
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get JWT token
- `GET /api/v1/auth/me` - Get current user info

### Users
- `GET /api/v1/users/me` - Get current user
- `PATCH /api/v1/users/me` - Update current user

### Transactions
- `GET /api/v1/transactions` - List transactions
- `POST /api/v1/transactions` - Create transaction
- `GET /api/v1/transactions/balances` - Get balance summary
- `GET /api/v1/transactions/open-debts` - Get open debts
- `GET /api/v1/transactions/{id}` - Get transaction
- `PATCH /api/v1/transactions/{id}` - Update transaction
- `DELETE /api/v1/transactions/{id}` - Delete transaction

### Contacts
- `GET /api/v1/contacts` - List contacts
- `POST /api/v1/contacts` - Create contact
- `GET /api/v1/contacts/{id}` - Get contact
- `PATCH /api/v1/contacts/{id}` - Update contact
- `DELETE /api/v1/contacts/{id}` - Delete contact

### Messages
- `GET /api/v1/messages` - List chat messages
- `POST /api/v1/messages` - Create message
- `DELETE /api/v1/messages` - Clear all messages
- `DELETE /api/v1/messages/{id}` - Delete message

### AI
- `POST /api/v1/ai/parse` - Parse financial input with AI

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_SERVER` | PostgreSQL host | localhost |
| `POSTGRES_PORT` | PostgreSQL port | 5432 |
| `POSTGRES_USER` | PostgreSQL user | vantrack |
| `POSTGRES_PASSWORD` | PostgreSQL password | vantrack_secret |
| `POSTGRES_DB` | PostgreSQL database | vantrack |
| `SECRET_KEY` | JWT secret key | (change in production) |
| `GEMINI_API_KEY` | Google Gemini API key | (required for AI) |
