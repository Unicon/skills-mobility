"""Seeded data generator for the Mock LMS.

This is an **authoring tool**, not part of the runtime. It assembles a realistic
``Catalog`` from a roster-CSV subset + a generated academic/credential layer,
which the CLI captures to the committed ``fixtures/catalog.json``. The service
then loads that frozen snapshot — it never runs the generator. Same inputs ->
same data (assemble -> capture -> commit -> deterministic replay).

Requires the dev dependency group (Faker).
"""

from mock_lms.generators.catalog import GenerationResult, generate

__all__ = ["generate", "GenerationResult"]
