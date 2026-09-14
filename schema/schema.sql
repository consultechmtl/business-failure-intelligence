-- Business Failure Intelligence v0.2
-- SQLite-compatible analytical schema. Additive normalization retains legacy company labels.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS industries (
  industry_code TEXT PRIMARY KEY,
  label_en TEXT NOT NULL,
  label_fr TEXT NOT NULL,
  description TEXT
);

CREATE TABLE IF NOT EXISTS business_models (
  business_model_code TEXT PRIMARY KEY,
  label_en TEXT NOT NULL,
  label_fr TEXT NOT NULL,
  description TEXT
);

CREATE TABLE IF NOT EXISTS geographies (
  geography_code TEXT PRIMARY KEY,
  parent_geography_code TEXT REFERENCES geographies(geography_code),
  geography_type TEXT NOT NULL CHECK (geography_type IN ('country','region','municipality')),
  country_code TEXT,
  region_code TEXT,
  municipality TEXT,
  name_en TEXT NOT NULL,
  name_fr TEXT NOT NULL
);

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
  industry_code TEXT REFERENCES industries(industry_code),
  business_model_code TEXT REFERENCES business_models(business_model_code),
  geography_code TEXT REFERENCES geographies(geography_code),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entity_aliases (
  alias_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  alias_name TEXT NOT NULL,
  alias_type TEXT NOT NULL CHECK (alias_type IN ('canonical','legal','brand','former_legal','other')),
  language_code TEXT NOT NULL CHECK (language_code IN ('en','fr','und')),
  UNIQUE(company_id, alias_name, alias_type, language_code)
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

CREATE INDEX IF NOT EXISTS idx_companies_industry_code ON companies(industry_code);
CREATE INDEX IF NOT EXISTS idx_companies_business_model_code ON companies(business_model_code);
CREATE INDEX IF NOT EXISTS idx_companies_geography_code ON companies(geography_code);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_company ON entity_aliases(company_id);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_name ON entity_aliases(alias_name);
CREATE INDEX IF NOT EXISTS idx_outcomes_company ON outcomes(company_id);
CREATE INDEX IF NOT EXISTS idx_causes_company ON cause_assertions(company_id);
CREATE INDEX IF NOT EXISTS idx_causes_code ON cause_assertions(cause_code);
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);

-- Aggregate official statistics are deliberately separate from narrative companies.
CREATE TABLE IF NOT EXISTS datasets (
  dataset_id TEXT PRIMARY KEY,
  table_number TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  publisher TEXT NOT NULL,
  source_url TEXT NOT NULL,
  retrieval_date TEXT NOT NULL,
  license_notes TEXT NOT NULL,
  definition_notes TEXT NOT NULL,
  extraction_criteria TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sample_frames (
  sample_frame_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
  label TEXT NOT NULL,
  definition_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observation_units (
  observation_unit_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
  label TEXT NOT NULL,
  unit_of_measure TEXT NOT NULL,
  definition_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcome_definitions (
  outcome_definition_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
  label TEXT NOT NULL,
  definition_text TEXT NOT NULL,
  UNIQUE(dataset_id, label)
);

CREATE TABLE IF NOT EXISTS aggregate_observations (
  aggregate_observation_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
  sample_frame_id TEXT NOT NULL REFERENCES sample_frames(sample_frame_id),
  observation_unit_id TEXT NOT NULL REFERENCES observation_units(observation_unit_id),
  outcome_definition_id TEXT NOT NULL REFERENCES outcome_definitions(outcome_definition_id),
  reference_period TEXT NOT NULL,
  geo TEXT NOT NULL,
  naics TEXT NOT NULL,
  employment_size TEXT NOT NULL,
  business_dynamics TEXT NOT NULL,
  uom TEXT NOT NULL,
  value REAL NOT NULL,
  status TEXT,
  table_number TEXT NOT NULL,
  source_url TEXT NOT NULL,
  retrieval_date TEXT NOT NULL,
  UNIQUE(dataset_id, reference_period, geo, naics, employment_size, business_dynamics, uom, status)
);

CREATE INDEX IF NOT EXISTS idx_aggregate_observations_comparison
  ON aggregate_observations(dataset_id, reference_period, geo, employment_size, business_dynamics);

-- OSB insolvency proceedings are a distinct official outcome layer, never company-linked.
CREATE TABLE IF NOT EXISTS osb_insolvency_observations (
  osb_insolvency_observation_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
  reference_period TEXT NOT NULL,
  geo TEXT NOT NULL,
  geo_level TEXT NOT NULL,
  debtor_type TEXT NOT NULL CHECK (debtor_type IN ('all','business','consumer')),
  business_form TEXT NOT NULL,
  insolvency_type TEXT NOT NULL CHECK (insolvency_type IN ('Total','Bankruptcy','Proposal')),
  naics TEXT NOT NULL,
  measure TEXT NOT NULL,
  uom TEXT NOT NULL,
  value REAL NOT NULL,
  status TEXT,
  source_url TEXT NOT NULL,
  retrieval_date TEXT NOT NULL,
  UNIQUE(dataset_id, reference_period, geo, geo_level, debtor_type, business_form, insolvency_type, naics, measure)
);
CREATE INDEX IF NOT EXISTS idx_osb_insolvencies_query
  ON osb_insolvency_observations(reference_period, geo, debtor_type, insolvency_type);
