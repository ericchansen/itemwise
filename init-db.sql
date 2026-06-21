-- Initialize pgvector extension for the app database.
CREATE EXTENSION IF NOT EXISTS vector;

-- Local pytest defaults to inventory_test on port 5433.
SELECT 'CREATE DATABASE inventory_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'inventory_test')\gexec
\connect inventory_test
CREATE EXTENSION IF NOT EXISTS vector;
