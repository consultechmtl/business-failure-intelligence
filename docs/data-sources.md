# Data sources and evidence policy

## Source layers

### Qualitative case discovery

- CB Insights startup failure reasons and post-mortem index
- Failory Startup Cemetery
- FailCode by eChai Ventures
- Awesome Startup Postmortems
- Postmortem.io

These are discovery and hypothesis sources. They are not representative samples. Important claims must be traced to a founder statement, filing, court record, or contemporaneous reporting.

### Official and legal data

- U.S. Census Business Dynamics Statistics: https://www.census.gov/programs-surveys/bds.html
- U.S. Bureau of Labor Statistics Business Dynamics: https://www.bls.gov/bdm/
- SEC EDGAR: https://www.sec.gov/edgar/search/
- Florida-UCLA LoPucki Bankruptcy Research Database: https://lopucki.law.ufl.edu/
- CourtListener RECAP: https://www.courtlistener.com/recap/
- UCI bankruptcy benchmarks: https://archive.ics.uci.edu/dataset/365/polish+companies+bankruptcy+data

These provide stronger outcome and financial evidence but usually do not explain product-market or founder decisions.

## Quebec and Canada expansion

The first Canadian expansion should prioritize:

- Corporations Canada federal corporate search and annual corporate statistics
- Statistics Canada business demography, openings, closures, and insolvencies
- Innovation, Science and Economic Development Canada insolvency statistics
- Office of the Superintendent of Bankruptcy Canada
- Quebec Registraire des entreprises
- Institut de la statistique du Québec
- Canadian Securities Administrators / SEDAR+ public-company filings
- Quebec court and insolvency records where legally and technically accessible
- Founder post-mortems and local reporting, coded with the same evidence policy

Quebec records require careful entity matching across French and English names, numbered companies, subsidiaries, and brand names. Coverage and access will be documented before ingestion; no claim of completeness will be made.

### Reviewed Quebec expansion (September 2026)

The curated corpus includes outcome-confirmed records for Taiga Motors, Lion Electric, UCG Canada Holdings Inc. (doing business as Frank And Oak), Gestion Juste Pour Rire Inc. (Just for Laughs), Le Château, and Beyond The Rack. Their legal-process outcomes are linked to monitor, trustee, court, or company materials in `data/curated/sources.csv`.

These filings establish proceedings and transactions, not automatically the businesses’ root causes. Consequently, the expansion codes one narrowly supported Taiga terminal funding assertion from contemporaneous reporting; the other five cases have no cause assertions. Their lessons explicitly retain this evidence boundary. This is a coverage increment, not a representative sample of Quebec failures or insolvencies.

## Evidence grades

- **A:** primary founder/company statement, court/regulatory finding, or official record directly supporting the claim
- **B:** strong secondary reporting with named evidence and traceable references
- **C:** curated aggregator or editorial classification useful for discovery
- **D:** unverified summary, snippet, or analyst inference

## Non-negotiable provenance

Every assertion in `cause_assertions` must have a source URL. Preserve an exact quote when possible. Never turn a category label into a causal fact without recording its assertion type and confidence.
