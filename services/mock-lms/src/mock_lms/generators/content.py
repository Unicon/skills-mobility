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
    # Rich assignment prompts (module-level) + the final/capstone prompt (#23 slice 2).
    module_assignment_descriptions: list[str]
    final_assignment_description: str
    # Instructional course material — (title, body) (#23 slice 3).
    pages: list[tuple[str, str]]
    # Fuller outcome descriptions (#23 slice 4).
    competency_description: str
    sub_competency_description: str


def pick[T](pool: list[T], i: int) -> T:
    """Deterministic element selection (no RNG) — wraps by modulo."""
    return pool[i % len(pool)]


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
    module_assignment_descriptions=[
        "Record the month-end adjusting entries for accrued wages, prepaid insurance, "
        "and straight-line depreciation, then prepare an adjusted trial balance. Submit "
        "the journal entries with a short explanation of each account's effect on the "
        "financial statements.",
        "Analyze the attached equipment lease under ASC 842: classify it, record the "
        "initial right-of-use asset and lease liability at the present value of the "
        "payments, and show how interest and amortization expense flow through the income "
        "statement over the term.",
        "Complete the bank reconciliation from the provided bank statement and cash "
        "ledger. Identify deposits in transit, outstanding checks, and any service "
        "charges or NSF items, and reconcile to an adjusted cash balance with supporting "
        "journal entries.",
        "Apply the five-step ASC 606 model to the multi-element software contract: "
        "identify the performance obligations, allocate the transaction price by "
        "standalone selling price, and determine the timing of revenue recognition for "
        "each obligation.",
    ],
    final_assignment_description=(
        "Comprehensive accounting assessment: from the provided trial balance and "
        "supporting schedules, prepare the adjusting entries, the income statement, the "
        "balance sheet, and the statement of cash flows, and write a brief memo "
        "interpreting the results for a non-accounting manager."
    ),
    pages=[
        ("Reading: The Accounting Cycle",
         "The accounting cycle runs from recording transactions in journals through "
         "posting to the ledger, preparing an unadjusted trial balance, making adjusting "
         "entries, and producing the financial statements. This module focuses on the "
         "adjusting-entry step, where accruals and deferrals align revenue and expense "
         "with the period in which they are earned or incurred."),
        ("Reading: Revenue Recognition (ASC 606)",
         "ASC 606 recognizes revenue when control of a good or service transfers to the "
         "customer, using a five-step model: identify the contract, identify the "
         "performance obligations, determine the transaction price, allocate it to the "
         "obligations, and recognize revenue as each obligation is satisfied."),
        ("Reading: Leases under ASC 842",
         "ASC 842 brings most leases onto the balance sheet as a right-of-use asset and "
         "a corresponding lease liability. Classification as a finance or operating "
         "lease determines whether the income-statement effect is front-loaded interest "
         "plus amortization or a single straight-line lease expense."),
        ("Reading: Inventory Costing Methods",
         "FIFO, LIFO, and weighted-average assign costs to inventory and cost of goods "
         "sold differently. In a period of rising prices, FIFO reports the highest "
         "ending inventory and gross margin, while LIFO reports the lowest — so method "
         "choice materially affects the financial statements and taxes."),
    ],
    competency_description=(
        "The learner can independently apply core accounting principles — accrual "
        "accounting, the governing GAAP standards, and the relationships among the "
        "financial statements — to analyze an unfamiliar business scenario and produce "
        "correct, well-supported financial information."
    ),
    sub_competency_description=(
        "The learner can complete a single bounded accounting task accurately — such as "
        "recording a set of adjusting entries or preparing a bank reconciliation — "
        "applying the correct accounts, amounts, and standard for that task."
    ),
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
    module_assignment_descriptions=[
        "Build a discounted-cash-flow model for the target company: project five years "
        "of free cash flow, estimate a terminal value, discount at the WACC you derive, "
        "and present the implied enterprise and equity value with a sensitivity table "
        "over the discount rate and growth rate.",
        "Evaluate the capital project using NPV and IRR at the stated hurdle rate. "
        "Include a payback estimate and a scenario analysis, and give a clear "
        "accept/reject recommendation supported by the numbers.",
        "Construct the efficient frontier from the provided asset return and covariance "
        "data, identify the tangency portfolio at the given risk-free rate, and explain "
        "how the optimal allocation shifts as the risk-free rate changes.",
        "Value the bond by discounting its cash flows at the yield to maturity, then "
        "quantify its interest-rate risk using modified duration and show the price "
        "change for a 50-basis-point move in yield.",
    ],
    final_assignment_description=(
        "Capstone valuation: given the company's financials and market data, build an "
        "integrated three-statement model, derive WACC, value the firm by both DCF and "
        "a comparables approach, reconcile the two, and recommend an investment "
        "decision with the key risks and sensitivities."
    ),
    pages=[
        ("Reading: Time Value of Money",
         "Every valuation rests on the time value of money: a dollar today is worth more "
         "than a dollar tomorrow because it can be invested. Present value discounts "
         "future cash flows back to today at a rate reflecting their risk; future value "
         "compounds them forward."),
        ("Reading: Discounted Cash Flow Valuation",
         "DCF values an asset as the present value of its expected future free cash "
         "flows plus a terminal value, discounted at the weighted average cost of "
         "capital. The output is highly sensitive to the discount rate and the terminal "
         "growth assumption, so sensitivity analysis is essential."),
        ("Reading: Risk, Return, and Diversification",
         "Expected return compensates investors for bearing risk. Combining imperfectly "
         "correlated assets lowers portfolio variance without proportionally lowering "
         "return — the basis of the efficient frontier and the case for diversification."),
        ("Reading: Capital Structure and WACC",
         "WACC blends the after-tax cost of debt and the cost of equity by their weights "
         "in the capital structure. Moderate leverage can lower WACC through the tax "
         "shield, but beyond a point rising financial-distress costs push it back up."),
    ],
    competency_description=(
        "The learner can independently apply core finance principles — the time value "
        "of money, risk and return, and valuation — to model an unfamiliar decision, "
        "reason about its risks and sensitivities, and reach a defensible recommendation."
    ),
    sub_competency_description=(
        "The learner can complete a single bounded finance task accurately — such as "
        "pricing a bond or computing a project's NPV — selecting and applying the "
        "appropriate method for that task."
    ),
)

_SUBJECTS = {"accounting": _ACCOUNTING, "finance": _FINANCE}


def subject_for(course_code: str) -> str:
    prefix = course_code.upper()
    if prefix.startswith("ACCY"):
        return "accounting"
    if prefix.startswith("FINC"):
        return "finance"
    # Don't silently mislabel an unrecognized prefix as accounting — a new subject
    # area must add its own content block, not inherit the wrong one.
    raise ValueError(f"Unrecognized course-code prefix: {course_code!r} (expected ACCY* or FINC*)")


def content_for(course_code: str) -> SubjectContent:
    return _SUBJECTS[subject_for(course_code)]
