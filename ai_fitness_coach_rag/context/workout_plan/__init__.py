"""Catalog-authoritative shortlisting, structured-output schemas, and the
deterministic safety validator for LLM-drafted workout plans.

The LLM proposes the plan (sequencing, variety, coaching notes); this package
guarantees it can only choose catalog-real, equipment/experience-compatible
exercises and that every persisted plan still passes a small set of
non-negotiable safety/integrity checks.
"""
