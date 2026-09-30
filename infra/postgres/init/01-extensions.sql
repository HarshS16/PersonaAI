-- Enabled once when the Postgres data volume is first created.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- fuzzy / trigram matching for fact dedupe
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
