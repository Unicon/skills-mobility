"""Curated domain content for the seed generator (issue #23).

Hand-authored, subject-specific content the *seeded* generator composes
deterministically — so it adds realism without breaking the
generate → capture → replay guarantee (no LLM / RNG at generation time; same
inputs + seed → byte-identical fixtures). Subject is derived from the course
code prefix (ACCY → accounting, FINC → finance).

The volume + variety here is what lets the Field Mapping / Field Synthesis LLM
Decision Services be exercised: rubric criteria the mapping service must triage
and learner submission bodies the synthesis service must summarize.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriterionSpec:
    key: str  # stable suffix for the criterion id
    description: str
    points: float
    ratings: list[tuple[str, float]]  # (description, points), best first


@dataclass(frozen=True)
class SubjectContent:
    label: str
    rubric_criteria: list[CriterionSpec]
    submission_bodies: list[str]
    grader_comments: list[str]


_ACCOUNTING = SubjectContent(
    label="accounting",
    rubric_criteria=[
        CriterionSpec(
            "accuracy",
            "Records transactions accurately using the correct accounts and amounts",
            5.0,
            [
                ("Postings are complete and accurate with correct debits and credits", 5.0),
                ("Minor posting or classification errors", 3.0),
                ("Frequent errors in accounts or amounts", 1.0),
            ],
        ),
        CriterionSpec(
            "standards",
            "Applies the relevant accounting standard (GAAP) to the scenario",
            5.0,
            [
                ("Correctly identifies and applies the governing standard", 5.0),
                ("Applies a standard with minor misinterpretation", 3.0),
                ("Misapplies or omits the governing standard", 1.0),
            ],
        ),
        CriterionSpec(
            "analysis",
            "Interprets results and explains the effect on the financial statements",
            5.0,
            [
                ("Clear, well-supported interpretation of statement impact", 5.0),
                ("Partial interpretation with gaps", 3.0),
                ("Little or no interpretation", 1.0),
            ],
        ),
        CriterionSpec(
            "communication",
            "Presents the work clearly using appropriate accounting terminology",
            5.0,
            [
                ("Clear and well organized, uses correct terminology", 5.0),
                ("Understandable with some unclear terminology", 3.0),
                ("Disorganized or imprecise", 1.0),
            ],
        ),
    ],
    submission_bodies=[
        "For the year-end adjusting entries I recognized accrued wages of $4,200 by "
        "debiting Wages Expense and crediting Wages Payable, and recorded $1,800 of "
        "straight-line depreciation on the delivery equipment. I then prepared an "
        "adjusted trial balance and confirmed total debits equaled total credits "
        "before drafting the income statement.",
        "I analyzed the lease under ASC 842 and concluded it is a finance lease because "
        "the term covers 80% of the asset's useful life. I recorded the right-of-use "
        "asset and lease liability at the present value of the payments and traced how "
        "interest and amortization expense flow through the income statement.",
        "To prepare the bank reconciliation I added deposits in transit of $2,350 and "
        "subtracted outstanding checks of $1,975 from the bank balance, then adjusted "
        "the book balance for a $35 service charge and a $60 NSF check. After the "
        "adjustments the reconciled cash balance agreed at $18,410.",
        "I computed cost of goods sold under both FIFO and weighted-average and "
        "explained why FIFO produced a higher gross margin in a period of rising "
        "prices. I reconciled ending inventory in the subsidiary ledger to the general "
        "ledger control account.",
        "For the revenue-recognition memo I applied the five-step model under ASC 606 "
        "to a multi-element software contract, allocating the transaction price to the "
        "license and support obligations by standalone selling price and recognizing "
        "support revenue ratably over the service period.",
        "I prepared the statement of cash flows using the indirect method, reconciling "
        "net income to operating cash flow by adjusting for depreciation, the change in "
        "working capital, and the gain on the equipment sale, which I reclassified to "
        "investing activities.",
    ],
    grader_comments=[
        "Postings are accurate and the governing standard is applied correctly.",
        "Good interpretation of the statement impact; tighten the terminology.",
        "Reconciliation balances; show the adjusting entries explicitly next time.",
        "Solid allocation; double-check the standalone-selling-price basis.",
        "Clear, well-organized work that meets the competency standard.",
        "Correct treatment; label the investing reclassification more clearly.",
    ],
)

_FINANCE = SubjectContent(
    label="finance",
    rubric_criteria=[
        CriterionSpec(
            "modeling",
            "Builds a sound quantitative model with correct formulas and assumptions",
            5.0,
            [
                ("Model is correct, well structured, and clearly documented", 5.0),
                ("Model works with minor formula or assumption issues", 3.0),
                ("Model has material errors", 1.0),
            ],
        ),
        CriterionSpec(
            "valuation",
            "Selects and applies an appropriate valuation method",
            5.0,
            [
                ("Method is appropriate and applied correctly", 5.0),
                ("Reasonable method with execution gaps", 3.0),
                ("Inappropriate or misapplied method", 1.0),
            ],
        ),
        CriterionSpec(
            "risk",
            "Identifies and reasons about the relevant risks and sensitivities",
            5.0,
            [
                ("Thorough risk and sensitivity analysis", 5.0),
                ("Identifies some risks without analysis", 3.0),
                ("Little risk consideration", 1.0),
            ],
        ),
        CriterionSpec(
            "recommendation",
            "Reaches a defensible recommendation supported by the analysis",
            5.0,
            [
                ("Clear recommendation well supported by the analysis", 5.0),
                ("Recommendation only partially supported", 3.0),
                ("Unsupported or absent recommendation", 1.0),
            ],
        ),
    ],
    submission_bodies=[
        "I built a discounted-cash-flow model projecting free cash flows over five years "
        "with a terminal value at a 2.5% perpetual growth rate. Using an 8.4% WACC I "
        "arrived at an enterprise value of $312M and, after netting debt, implied equity "
        "of $268M, then ran a sensitivity table over the discount rate and growth.",
        "For the capital-budgeting decision I computed an NPV of $1.42M at the 10% hurdle "
        "rate and a 14.7% IRR and recommended proceeding. I included a 3.6-year payback "
        "and a scenario analysis showing the project stays NPV-positive unless volumes "
        "fall more than 18%.",
        "I estimated the portfolio's expected return and standard deviation from the "
        "covariance matrix, plotted the efficient frontier, and identified the tangency "
        "portfolio at a 4% risk-free rate, explaining why the Sharpe-maximizing "
        "allocation shifts toward equities as the risk-free rate falls.",
        "To value the bond I discounted the semiannual coupons and face value at the "
        "yield to maturity, pricing the 5% coupon bond at $1,043, and showed how the "
        "price moves inversely with a 50-basis-point yield change given a modified "
        "duration of 7.2.",
        "I analyzed the firm's capital structure and computed WACC before and after a "
        "proposed debt issuance, concluding that moderate added leverage lowers WACC but "
        "that the marginal benefit reverses past a 45% debt-to-capital ratio as financial "
        "distress costs rise.",
        "I forecast the three financial statements from revenue-growth and margin "
        "assumptions, linked them through the cash and retained-earnings balances, and "
        "verified the balance sheet balanced before computing the implied free cash flow.",
    ],
    grader_comments=[
        "Model is well structured and the valuation method is appropriate.",
        "Good sensitivity analysis; state the recommendation more explicitly.",
        "Correct method; document the assumptions more fully.",
        "Strong risk reasoning that meets the competency standard.",
        "Clear and defensible recommendation.",
        "Statements link correctly; show the balancing check explicitly.",
    ],
)

_SUBJECTS = {"accounting": _ACCOUNTING, "finance": _FINANCE}


def subject_for(course_code: str) -> str:
    return "finance" if course_code.upper().startswith("FINC") else "accounting"


def content_for(course_code: str) -> SubjectContent:
    return _SUBJECTS[subject_for(course_code)]
