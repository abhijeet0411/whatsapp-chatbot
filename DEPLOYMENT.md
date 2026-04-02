# Deployment Guide
See CONFIGURATION.md for full setup instructions.

## Quick Start
```bash
cp .env.example .env
docker-compose up postgres redis -d
psql postgresql://botuser:botpass@localhost:5432/ampbot -f scripts/schema.sql
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest tests/test_flow_engine.py -v
```

## Production
```bash
docker-compose up --build -d
```
