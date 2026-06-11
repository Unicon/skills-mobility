"""Seeded data generator for the Mock LMS.

This is an **authoring tool**, not part of the runtime. It builds a realistic
``Catalog`` + ``Scenario`` set from a fixed seed, which the CLI captures to the
committed ``fixtures/*.json``. The service then loads that frozen snapshot — it
never runs the generator. Same seed -> same data, so the committed fixtures are
reproducible (generate -> capture -> commit -> deterministic replay).

Requires the dev dependency group (Faker).
"""

from mock_lms.generators.catalog import GenerationResult, generate

__all__ = ["generate", "GenerationResult"]
