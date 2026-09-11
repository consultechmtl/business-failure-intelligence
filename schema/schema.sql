-- Business Failure Intelligence v0.1
-- SQLite-compatible analytical schema.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  legal_name TEXT,
  country_code TEXT,
  region_code TEXT,
  city TEXT,
  founded_year INTEGER,
  industry TEXT,
  business_model TEXT,
  description TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outcomes (
  outcome_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  outcome_type TEXT NOT NULL CHECK (outcome_type IN ('shutdown','bankruptcy','insolvency','distress','acquisition','asset_sale','pivot','dormant','unknown')),
  outcome_date TEXT,
  jurisdiction TEXT,
  status TEXT NOT NULL DEFAULT 'reported' CHECK (status IN ('reported','verified','disputed','inferred')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  source_url TEXT NOT NULL UNIQUE,
  title TEXT,
  publisher TEXT,
  source_type TEXT NOT NULL CHECK (source_type IN ('founder_postmortem','company_statement','journalism','court_filing','regulatory_filing','academic','official_statistics','aggregator','dataset','interview','other')),
  published_date TEXT,
  accessed_date TEXT NOT NULL,
  evidence_quality TEXT CHECK (evidence_quality IN ('A','B','C','D','unknown')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS failure_causes (
  cause_code TEXT PRIMARY KEY,
  parent_code TEXT REFERENCES failure_causes(cause_code),
  label TEXT NOT NULL UNIQUE,
  definition TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cause_assertions (
  assertion_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  cause_code TEXT NOT NULL REFERENCES failure_causes(cause_code),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  assertion_type TEXT NOT NULL CHECK (assertion_type IN ('explicit_founder_statement','court_or_regulatory_finding','contemporaneous_reporting','editorial_classification','analyst_inference')),
  confidence TEXT NOT NULL CHECK (confidence IN ('high','medium','low')),
  evidence_quote TEXT,
  analyst_note TEXT,
  UNIQUE(company_id, cause_code, source_id)
);

CREATE TABLE IF NOT EXISTS warning_signs (
  warning_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  signal_code TEXT NOT NULL,
  observed_text TEXT NOT NULL,
  observed_date TEXT,
  source_id TEXT REFERENCES sources(source_id),
  confidence TEXT NOT NULL CHECK (confidence IN ('high','medium','low'))
);

CREATE TABLE IF NOT EXISTS lessons (
  lesson_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  lesson TEXT NOT NULL,
  applicability TEXT,
  action_for_founder TEXT,
  confidence TEXT NOT NULL CHECK (confidence IN ('high','medium','low'))
);

CREATE INDEX IF NOT EXISTS idx_outcomes_company ON outcomes(company_id);
CREATE INDEX IF NOT EXISTS idx_causes_company ON cause_assertions(company_id);
CREATE INDEX IF NOT EXISTS idx_causes_code ON cause_assertions(cause_code);
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
