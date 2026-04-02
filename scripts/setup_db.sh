#!/bin/bash
# scripts/setup_db.sh — one-shot DB setup
set -e
echo "Creating database and user..."
psql -U postgres << SQL
  CREATE USER botuser WITH PASSWORD 'botpass';
  CREATE DATABASE ampbot OWNER botuser;
  GRANT ALL PRIVILEGES ON DATABASE ampbot TO botuser;
SQL
echo "Running schema..."
psql -U botuser -d ampbot -f scripts/schema.sql
echo "Database ready."
