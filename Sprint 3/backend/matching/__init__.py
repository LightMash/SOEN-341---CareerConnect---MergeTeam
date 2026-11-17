"""
Qualification matching and applicant standing.

  catalog.py / catalog_data.json  the standard qualification list
  normalize.py                    the one text-normalization function
  rules.py                        satisfies() / evaluate()  (pure)
  search.py                       alias search               (pure)
  standing.py                     "Your standing"            (pure)
  resume_scan.py / reviewer.py    resume import
  models.py / schemas.py / router.py   database tables and the /api/matching routes
  migrate.py / demo_data.py       local-only scripts

This file deliberately imports nothing, so the pure modules can be used
(and tested) without a database connection.
"""
