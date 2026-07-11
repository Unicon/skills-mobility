"""Curated domain content for the seed generator (issue #23).

Hand-authored, **per-course** content the *seeded* generator composes
deterministically — so it adds realism without breaking the
generate → capture → replay guarantee (no LLM / RNG at generation time; same
inputs + seed → byte-identical fixtures).

Content is keyed by course code (not by subject bucket): each of the six roster
courses gets rubric criteria, submission bodies, grader comments, assignment
prompts, and pages that reflect *that course's* real topic — so ACCY-374 (Law,
Governance & Ethics) reads nothing like ACCY-491 (The Financial Audit), and the
Field Mapping / Field Synthesis LLM Decision Services see genuine variety rather
than one shared pool reused across three same-subject courses. `subject_for`
still classifies the prefix (and rejects unknown ones); `content_for` resolves
the specific course.
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
    """A single course's curated content pool (the name is historical — content is
    now per-course, see `_COURSES`)."""

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


def _crit(key: str, description: str, best: str, mid: str, low: str) -> CriterionSpec:
    """A 5/3/1-point criterion with three ratings (best → low)."""
    return CriterionSpec(key, description, 5.0, [(best, 5.0), (mid, 3.0), (low, 1.0)])


# ---------------------------------------------------------------------------
# ACCY-111 — Introduction to Accounting
# ---------------------------------------------------------------------------
_ACCY_111 = SubjectContent(
    label="intro-accounting",
    rubric_criteria=[
        _crit("entries", "Records transactions with the correct accounts, debits, and credits",
              "Every entry uses the right accounts with debits equal to credits",
              "Minor account or debit/credit errors", "Frequent posting errors"),
        _crit("equation",
              "Keeps the accounting equation (Assets = Liabilities + Equity) in balance",
              "Equation stays in balance through every transaction",
              "Balances with one traced error", "Equation does not balance"),
        _crit("statements", "Assembles the basic financial statements from the trial balance",
              "Income statement and balance sheet tie to the trial balance",
              "Statements mostly tie with small omissions", "Statements do not tie"),
        _crit("communication", "Explains each step using correct introductory terminology",
              "Clear explanation using correct terms", "Understandable with loose terms",
              "Unclear or imprecise"),
    ],
    submission_bodies=[
        "I journalized the month's transactions, posting each to T-accounts, and confirmed "
        "the accounting equation stayed in balance after every entry before footing the "
        "columns.",
        "For the owner's $10,000 cash investment I debited Cash and credited Owner's "
        "Capital, then walked through how the equation stays balanced as assets and equity "
        "both rise by the same amount.",
        "I prepared the unadjusted trial balance from the ledger, listed each account's "
        "debit or credit balance, and verified total debits equaled total credits at "
        "$47,300.",
        "From the adjusted trial balance I drafted a simple income statement — revenues "
        "less expenses — and carried net income into owner's equity on the balance sheet.",
        "I recorded a $600 cash sale and a $900 sale on account, explaining why Accounts "
        "Receivable is an asset and how it later converts to cash when the customer pays.",
        "I classified each account as an asset, liability, equity, revenue, or expense and "
        "used that classification to decide its normal debit or credit balance.",
    ],
    grader_comments=[
        "Entries are correct and the equation stays in balance — nice work.",
        "Trial balance ties; label each account's normal balance next time.",
        "Good statement draft; carry net income into equity explicitly.",
        "Correct classification; tighten the introductory terminology.",
    ],
    module_assignment_descriptions=[
        "Journalize the ten listed transactions for the month, post them to T-accounts, "
        "and show that the accounting equation stays in balance after each one.",
        "From the posted ledger, prepare an unadjusted trial balance and confirm that total "
        "debits equal total credits.",
        "Using the adjusted trial balance provided, prepare a simple income statement and "
        "balance sheet, and explain how net income flows into owner's equity.",
    ],
    final_assignment_description=(
        "Introductory accounting assessment: journalize a month of transactions for a small "
        "sole proprietorship, post to the ledger, prepare a trial balance, and produce a "
        "simple income statement and balance sheet with a short note on what each shows."
    ),
    pages=[
        ("Reading: The Accounting Equation",
         "Every transaction keeps Assets = Liabilities + Equity in balance. A cash sale "
         "raises an asset and equity; borrowing raises an asset and a liability. Seeing the "
         "two-sided effect is the foundation of double-entry accounting."),
        ("Reading: Debits and Credits",
         "Debits increase assets and expenses; credits increase liabilities, equity, and "
         "revenue. Every entry has equal debits and credits, which is why a trial balance "
         "should foot to equal totals."),
        ("Reading: The Trial Balance",
         "After posting to the ledger, the trial balance lists every account with its debit "
         "or credit balance. Equal totals are a check on the arithmetic — though they do not "
         "prove every entry was classified correctly."),
        ("Reading: The Basic Financial Statements",
         "The income statement reports revenues minus expenses for the period; the balance "
         "sheet reports assets, liabilities, and equity at a point in time. Net income links "
         "them by flowing into owner's equity."),
    ],
    competency_description=(
        "The learner can independently work the introductory accounting cycle — journalize "
        "transactions, post to the ledger, prepare a trial balance, and assemble the basic "
        "financial statements — keeping the accounting equation in balance throughout."
    ),
    sub_competency_description=(
        "The learner can complete one bounded introductory task accurately — such as "
        "journalizing a set of transactions or preparing a trial balance — using the "
        "correct accounts and normal balances."
    ),
)

# ---------------------------------------------------------------------------
# ACCY-374 — Law, Governance, & Ethics  (qualitative: legal/ethical analysis)
# ---------------------------------------------------------------------------
_ACCY_374 = SubjectContent(
    label="law-governance-ethics",
    rubric_criteria=[
        _crit("issue", "Identifies the governing rule, standard, or duty at stake",
              "Names the controlling law/standard and why it applies",
              "Identifies a relevant rule with gaps", "Misidentifies or omits the rule"),
        _crit("analysis", "Applies the rule to the facts with sound legal/ethical reasoning",
              "Rigorous application tied to the specific facts",
              "Partial application with unsupported leaps", "Little reasoning from the facts"),
        _crit("stakeholders", "Weighs the affected parties, duties, and conflicts of interest",
              "Balances all affected parties and duties", "Considers some stakeholders",
              "Ignores competing interests"),
        _crit("conclusion", "Reaches a defensible, ethically grounded recommendation",
              "Clear recommendation grounded in the analysis",
              "Recommendation only partly supported", "Unsupported or absent conclusion"),
    ],
    submission_bodies=[
        "I concluded the engagement impairs independence under the AICPA Code because the "
        "firm would be auditing balances it had itself recorded — a self-review threat with "
        "no safeguard short of declining the bookkeeping work.",
        "Applying the elements of an enforceable contract, I found no binding agreement: the "
        "'offer' was an invitation to negotiate and there was no consideration, so the "
        "counterparty cannot compel performance.",
        "I analyzed the director's conflict under the duty of loyalty and recommended the "
        "board approve the related-party transaction only after full disclosure, recusal, "
        "and a fairness review by disinterested directors.",
        "Under Sarbanes-Oxley §302 the CEO and CFO must certify the financials, so I "
        "recommended the disclosure-controls gap be remediated and documented before the "
        "next certification rather than certified around.",
        "Weighing the whistleblower's obligations, I concluded the accountant should escalate "
        "the suspected misstatement through the audit committee — the ethical duty to the "
        "public interest outweighs loyalty to the supervisor who resisted the adjustment.",
        "I assessed the agency relationship and found the employee acted with apparent "
        "authority, so the firm is bound to the third party even though the employee "
        "exceeded actual authority.",
    ],
    grader_comments=[
        "Correctly identifies the governing duty and applies it to the facts.",
        "Good stakeholder analysis; state the recommendation more decisively.",
        "Sound reasoning; cite the specific rule provision next time.",
        "Defensible conclusion that meets the ethical-reasoning standard.",
    ],
    module_assignment_descriptions=[
        "Given the client scenario, analyze whether the proposed engagement impairs auditor "
        "independence under the AICPA Code of Professional Conduct; identify the threat, any "
        "safeguards, and your conclusion.",
        "Evaluate the attached agreement against the elements of an enforceable contract and "
        "advise whether either party can compel performance, with reasoning from the facts.",
        "Assess the described board's handling of a related-party transaction against "
        "directors' fiduciary duties and recommend the governance steps required before "
        "approval.",
    ],
    final_assignment_description=(
        "Integrated law, governance, and ethics assessment: given a fact pattern involving a "
        "related-party transaction and a suspected misstatement, identify the legal duties "
        "and professional-conduct rules at stake, weigh the stakeholders, and recommend a "
        "defensible course of action with your reasoning."
    ),
    pages=[
        ("Reading: Elements of an Enforceable Contract",
         "A binding contract requires offer, acceptance, consideration, capacity, and a "
         "lawful purpose. Distinguishing a genuine offer from an invitation to negotiate, "
         "and identifying consideration, is where most disputes actually turn."),
        ("Reading: Fiduciary Duties and Corporate Governance",
         "Directors owe duties of care and loyalty to the corporation. Governance structures "
         "— an independent board, an audit committee, and internal controls — exist to hold "
         "those duties operational, especially around conflicts and related-party dealings."),
        ("Reading: The AICPA Code and Auditor Independence",
         "Independence is threatened by self-review, self-interest, advocacy, familiarity, and "
         "intimidation. The Code asks whether a reasonable, informed third party would "
         "conclude independence is impaired, and whether safeguards reduce the threat."),
        ("Reading: Sarbanes-Oxley and Professional Responsibility",
         "SOX made executives certify the financials (§302) and management assess internal "
         "control (§404). It reframed professional ethics from a private matter into an "
         "obligation to the investing public, backed by real accountability."),
    ],
    competency_description=(
        "The learner can independently analyze an unfamiliar business situation for the legal "
        "duties, governance obligations, and professional-conduct rules at stake, weigh the "
        "competing stakeholders and conflicts, and reach a defensible, ethically grounded "
        "recommendation."
    ),
    sub_competency_description=(
        "The learner can resolve one bounded law-or-ethics question accurately — such as "
        "assessing an independence threat or the elements of a contract — by naming the "
        "governing rule and applying it to the facts."
    ),
)

# ---------------------------------------------------------------------------
# ACCY-491 — The Financial Audit
# ---------------------------------------------------------------------------
_ACCY_491 = SubjectContent(
    label="financial-audit",
    rubric_criteria=[
        _crit("risk", "Assesses the risk of material misstatement at the assertion level",
              "Risk assessment is specific and tied to assertions",
              "General risk assessment with gaps", "Little or no risk assessment"),
        _crit("evidence", "Gathers sufficient appropriate audit evidence for the assertion",
              "Evidence is sufficient, relevant, and reliable",
              "Evidence has gaps in sufficiency or reliability", "Evidence is inadequate"),
        _crit("procedures", "Designs and executes procedures responsive to the assessed risk",
              "Procedures clearly respond to the identified risk",
              "Procedures only loosely tied to risk", "Procedures not responsive"),
        _crit("conclusion", "Draws a supportable conclusion and the right report implication",
              "Conclusion follows from the evidence and drives the opinion",
              "Conclusion partly supported", "Unsupported conclusion"),
    ],
    submission_bodies=[
        "I set overall materiality at 5% of pre-tax income and performance materiality at "
        "75% of that, then documented why the receivables balance carried a higher risk of "
        "material misstatement at the existence assertion.",
        "To test existence of accounts receivable I sent positive confirmations to a sample "
        "selected by monetary-unit sampling and performed alternative procedures — tracing to "
        "subsequent cash receipts — for the non-responses.",
        "I walked through the revenue cycle, identified the key controls over cutoff, and "
        "tested a sample of shipments around year-end to conclude whether revenue was "
        "recorded in the correct period.",
        "Evaluating the going-concern indicators — recurring losses and a working-capital "
        "deficiency — I concluded substantial doubt existed and that management's plans did "
        "not sufficiently mitigate it, driving an emphasis-of-matter paragraph.",
        "I recomputed the inventory obsolescence reserve, compared management's assumptions to "
        "historical write-offs, and found the estimate reasonable but under-documented, so I "
        "proposed an adjusting entry and a control-deficiency comment.",
        "Because controls over the estimate were not operating effectively, I lowered "
        "reliance on controls and expanded substantive testing of the warranty accrual, "
        "tracing inputs to third-party claims data.",
    ],
    grader_comments=[
        "Risk is assessed at the assertion level and the procedure responds to it.",
        "Confirmation approach is sound; document the alternative procedures fully.",
        "Good cutoff testing; tie the conclusion to the report implication.",
        "Correct going-concern reasoning that meets the standard.",
    ],
    module_assignment_descriptions=[
        "Set overall and performance materiality for the engagement, then assess the risk of "
        "material misstatement for accounts receivable at the assertion level and justify "
        "each rating.",
        "Design and document the substantive procedures to test the existence of accounts "
        "receivable, including your sampling approach and the alternative procedures for "
        "confirmation non-responses.",
        "Evaluate the provided going-concern indicators and management's plans, and conclude "
        "whether substantial doubt exists and what report implication follows.",
    ],
    final_assignment_description=(
        "Comprehensive audit assessment: for the assigned account, assess the risk of "
        "material misstatement by assertion, design responsive procedures, evaluate the "
        "evidence gathered, and state your conclusion and its effect on the audit opinion."
    ),
    pages=[
        ("Reading: The Audit Risk Model",
         "Audit risk is the risk of an unmodified opinion on materially misstated statements. "
         "It combines inherent risk, control risk, and detection risk — the auditor sets "
         "detection risk by choosing the nature, timing, and extent of procedures."),
        ("Reading: Materiality",
         "Materiality is the threshold above which a misstatement could influence a user's "
         "decisions. Overall materiality is set for the statements as a whole; performance "
         "materiality is lower, to leave room for undetected misstatements to aggregate."),
        ("Reading: Audit Evidence and Procedures",
         "Evidence must be sufficient (enough) and appropriate (relevant and reliable). "
         "Procedures — inspection, observation, confirmation, recalculation, analytics — are "
         "chosen to respond to the assessed risk at each assertion."),
        ("Reading: Internal Control and the COSO Framework",
         "COSO frames internal control as five components: control environment, risk "
         "assessment, control activities, information & communication, and monitoring. "
         "Testing whether controls operate effectively determines how much substantive work "
         "is needed."),
    ],
    competency_description=(
        "The learner can independently plan and execute an audit of an unfamiliar account — "
        "assessing the risk of material misstatement by assertion, designing responsive "
        "procedures, evaluating sufficiency and appropriateness of evidence, and reaching a "
        "supportable conclusion that drives the opinion."
    ),
    sub_competency_description=(
        "The learner can complete one bounded audit task accurately — such as setting "
        "materiality or designing a confirmation procedure — appropriate to the assessed "
        "risk for that assertion."
    ),
)

# ---------------------------------------------------------------------------
# FINC-106 — Introduction to Finance
# ---------------------------------------------------------------------------
_FINC_106 = SubjectContent(
    label="intro-finance",
    rubric_criteria=[
        _crit("tvm", "Applies time-value-of-money mechanics correctly",
              "Present/future value computed with the right rate and periods",
              "Minor rate or period errors", "Mechanics materially wrong"),
        _crit("setup", "Sets up the problem with the correct cash-flow timing and signs",
              "Cash flows are timed and signed correctly", "One timing/sign error",
              "Cash flows set up incorrectly"),
        _crit("interpretation", "Interprets the result in plain financial terms",
              "Clear, correct interpretation of the result", "Partial interpretation",
              "Little or no interpretation"),
        _crit("communication", "Presents the work clearly with correct introductory terms",
              "Clear and well organized", "Understandable with loose terms", "Disorganized"),
    ],
    submission_bodies=[
        "I found the present value of $5,000 received in three years at 6% by discounting: "
        "$5,000 / 1.06^3 = $4,198, and explained why money later is worth less than money "
        "today.",
        "For the savings goal I computed the future value of $200 monthly deposits at 4% "
        "annual interest compounded monthly, and showed how compounding accelerates the "
        "balance in the later years.",
        "I compared simple and compound interest on the same $1,000 over five years and "
        "explained why the compound path pulls ahead as interest earns interest.",
        "I built a simple personal budget separating fixed and variable costs, computed the "
        "monthly surplus, and showed how directing it to savings changes the future-value "
        "outcome.",
        "To evaluate the two payment options I discounted each stream to present value at the "
        "stated rate and recommended the lump sum because its present value exceeded the "
        "installments.",
        "I explained the risk-return tradeoff using a savings account versus a stock fund, "
        "noting that the higher expected return of the fund comes with a wider range of "
        "outcomes.",
    ],
    grader_comments=[
        "Discounting is set up correctly and the interpretation is clear.",
        "Good compounding work; label the periods and rate explicitly.",
        "Correct comparison; state the recommendation in plain terms.",
        "Clear budget; connect the surplus back to the savings goal.",
    ],
    module_assignment_descriptions=[
        "Compute the present and future value of the given cash flows at the stated rate, "
        "show your formulas, and explain in plain terms why the values differ.",
        "Build a simple monthly budget from the provided income and expenses, compute the "
        "surplus, and show how saving it changes a five-year future-value outcome.",
        "Given two payment options (a lump sum vs. installments), discount each to present "
        "value at the stated rate and recommend the better choice with reasoning.",
    ],
    final_assignment_description=(
        "Introductory finance assessment: given a short set of personal and business cash "
        "flows, apply time-value-of-money mechanics to value them, compare two options on a "
        "present-value basis, and explain the risk-return tradeoff in plain language."
    ),
    pages=[
        ("Reading: The Time Value of Money",
         "A dollar today is worth more than a dollar tomorrow because it can be invested. "
         "Present value discounts future amounts back to today; future value compounds "
         "today's amounts forward. The rate reflects opportunity cost and risk."),
        ("Reading: Simple vs. Compound Interest",
         "Simple interest is earned only on the principal; compound interest is earned on "
         "principal plus accumulated interest. Over time, and at higher rates, compounding "
         "produces a markedly larger balance."),
        ("Reading: Risk and Return, Intuitively",
         "Investors expect higher returns for bearing more risk. A savings account offers a "
         "small, near-certain return; equities offer a higher expected return with a much "
         "wider range of possible outcomes."),
        ("Reading: Budgeting and Cash Flow",
         "A budget separates income from fixed and variable spending to reveal the surplus or "
         "shortfall. Directing a monthly surplus into savings is where time-value mechanics "
         "turn small amounts into meaningful sums."),
    ],
    competency_description=(
        "The learner can independently apply introductory finance principles — the time value "
        "of money, simple and compound interest, and the risk-return tradeoff — to value cash "
        "flows, compare options on a present-value basis, and explain the result plainly."
    ),
    sub_competency_description=(
        "The learner can complete one bounded introductory finance task accurately — such as "
        "discounting a cash flow to present value or building a simple budget — using the "
        "correct rate, periods, and cash-flow signs."
    ),
)

# ---------------------------------------------------------------------------
# FINC-321 — Capital Markets
# ---------------------------------------------------------------------------
_FINC_321 = SubjectContent(
    label="capital-markets",
    rubric_criteria=[
        _crit("instruments", "Identifies the security and its cash-flow/claim structure",
              "Correctly characterizes the instrument and its claims",
              "Minor mischaracterization", "Misidentifies the instrument"),
        _crit("mechanics", "Explains the relevant market mechanics or pricing relationship",
              "Mechanics/pricing relationship explained correctly",
              "Partial or imprecise explanation", "Mechanics wrong"),
        _crit("efficiency", "Reasons about market efficiency, information, and participants",
              "Sound reasoning about information and price formation",
              "Some reasoning with gaps", "Little market reasoning"),
        _crit("conclusion", "Reaches a supported conclusion about the market question",
              "Conclusion well supported by the analysis", "Partly supported",
              "Unsupported conclusion"),
    ],
    submission_bodies=[
        "I explained why bond prices move inversely to yields and showed, for a 5% coupon "
        "bond, how a 50-basis-point rise in market yields pushes the price below par as "
        "future coupons are discounted at a higher rate.",
        "I distinguished the primary market (the issuer raises capital in the IPO) from the "
        "secondary market (investors trade existing shares among themselves), noting that "
        "secondary trading provides the liquidity that makes the primary issue viable.",
        "Testing the semi-strong form of the efficient-market hypothesis, I argued that "
        "the stock's near-instant reaction to the earnings surprise is consistent with prices "
        "already reflecting public information, so the announcement offered no easy profit.",
        "I described the shape of the yield curve and explained how an inversion — short "
        "rates above long rates — reflects market expectations of falling future rates and "
        "has historically preceded slowdowns.",
        "I compared how an exchange-traded equity and an over-the-counter corporate bond "
        "trade, contrasting the centralized order book and continuous pricing of the exchange "
        "with the dealer-quoted, negotiated nature of the bond market.",
        "I explained the role of market makers in providing liquidity, earning the bid-ask "
        "spread as compensation for inventory and adverse-selection risk, and how tighter "
        "spreads signal a more liquid, competitive market.",
    ],
    grader_comments=[
        "Instrument and its claim structure are characterized correctly.",
        "Good pricing-relationship explanation; quantify the move next time.",
        "Sound efficiency reasoning that meets the standard.",
        "Correct market-structure contrast; state the conclusion explicitly.",
    ],
    module_assignment_descriptions=[
        "For the assigned bond, explain the inverse price-yield relationship and quantify the "
        "price change for a 50-basis-point shift in market yields, showing the discounting.",
        "Contrast the primary and secondary markets for a recent IPO and explain how "
        "secondary-market liquidity supports the primary issuance.",
        "Evaluate the stock's price reaction to a public announcement against the semi-strong "
        "efficient-market hypothesis and conclude whether it offered an exploitable profit.",
    ],
    final_assignment_description=(
        "Capital-markets assessment: given a set of securities and a market event, "
        "characterize each instrument and its claims, explain the relevant pricing "
        "relationships and market structure, and reason about what an efficient market "
        "implies for the event."
    ),
    pages=[
        ("Reading: Primary and Secondary Markets",
         "Issuers raise capital in the primary market (e.g., an IPO); investors then trade "
         "those securities among themselves in the secondary market. Secondary liquidity is "
         "what makes investors willing to buy at issuance in the first place."),
        ("Reading: Bond Pricing and Interest Rates",
         "A bond's price is the present value of its coupons and face value. Because those "
         "cash flows are fixed, price moves inversely to market yields — and longer-maturity "
         "bonds move more for a given yield change."),
        ("Reading: The Efficient Market Hypothesis",
         "The EMH holds that prices reflect available information — weak (past prices), "
         "semi-strong (all public information), or strong (all information). Under semi-strong "
         "efficiency, public news is priced in almost immediately."),
        ("Reading: Market Structure and Liquidity",
         "Exchanges match orders in a central book with continuous pricing; OTC markets trade "
         "through dealer quotes. Market makers supply liquidity and earn the bid-ask spread as "
         "compensation for inventory and adverse-selection risk."),
    ],
    competency_description=(
        "The learner can independently analyze an unfamiliar capital-markets situation — "
        "characterizing the securities and their claims, explaining the relevant pricing "
        "relationships and market structure, and reasoning about information and efficiency — "
        "to reach a supported conclusion."
    ),
    sub_competency_description=(
        "The learner can resolve one bounded capital-markets question accurately — such as "
        "explaining the price-yield relationship or classifying a market as primary vs. "
        "secondary — with correct mechanics."
    ),
)

# ---------------------------------------------------------------------------
# FINC-439 — Applied Securities Analysis
# ---------------------------------------------------------------------------
_FINC_439 = SubjectContent(
    label="securities-analysis",
    rubric_criteria=[
        _crit("modeling", "Builds a sound valuation model with correct formulas and assumptions",
              "Model is correct, structured, and clearly documented",
              "Minor formula/assumption issues", "Material modeling errors"),
        _crit("statements", "Grounds the analysis in the financial statements and ratios",
              "Analysis is anchored in the statements and key ratios",
              "Some grounding with gaps", "Weakly grounded in the financials"),
        _crit("valuation", "Selects and reconciles appropriate valuation methods",
              "Methods appropriate and reconciled", "Reasonable method with execution gaps",
              "Inappropriate or misapplied method"),
        _crit("recommendation", "Reaches a defensible buy/hold/sell recommendation with risks",
              "Clear recommendation supported by the analysis and risks",
              "Recommendation partly supported", "Unsupported recommendation"),
    ],
    submission_bodies=[
        "I built a discounted-cash-flow model projecting free cash flow over five years with a "
        "terminal value at 2.5% growth; at an 8.4% WACC it implied equity of $268M, roughly "
        "12% above the market price, supporting a buy.",
        "I performed a comparables valuation using EV/EBITDA and P/E against a peer set, "
        "adjusted for the target's higher margins, and reconciled the multiple-based range "
        "with my DCF to triangulate fair value.",
        "Analyzing the financial statements, I decomposed ROE with the DuPont identity into "
        "margin, turnover, and leverage, and traced the recent ROE decline to margin "
        "compression rather than a change in leverage.",
        "I forecast the three statements from revenue-growth and margin assumptions, linked "
        "them through cash and retained earnings, and derived the free cash flow that feeds "
        "the DCF, checking that the balance sheet balanced.",
        "I stress-tested the recommendation with a sensitivity table over WACC and terminal "
        "growth and a bear scenario of margin compression, concluding the stock stays "
        "undervalued except in the most adverse case.",
        "I assessed earnings quality by comparing net income to operating cash flow and "
        "examining accruals, flagging that a growing receivables-to-sales ratio warranted "
        "discounting the reported growth.",
    ],
    grader_comments=[
        "Model is well structured and the valuation is appropriate.",
        "Good comparables work; reconcile the two methods more explicitly.",
        "Strong statement analysis that meets the competency standard.",
        "Defensible recommendation; sharpen the key risks.",
    ],
    module_assignment_descriptions=[
        "Build a five-year discounted-cash-flow model for the assigned company, derive WACC, "
        "and present the implied equity value with a sensitivity table over discount rate and "
        "terminal growth.",
        "Perform a comparables valuation against a peer set using EV/EBITDA and P/E, adjust "
        "for differences, and reconcile the multiple-based range with a DCF estimate.",
        "Analyze the company's financial statements — decompose ROE with the DuPont identity "
        "and assess earnings quality — and explain what the trends imply for the forecast.",
    ],
    final_assignment_description=(
        "Applied securities-analysis capstone: given a company's financials and market data, "
        "build an integrated three-statement model, value the equity by both DCF and "
        "comparables, reconcile the two, and issue a buy/hold/sell recommendation with the "
        "key risks and sensitivities."
    ),
    pages=[
        ("Reading: Financial Statement Analysis",
         "Security analysis starts in the financial statements: common-size statements and "
         "ratios reveal margin, turnover, leverage, and liquidity trends. The DuPont identity "
         "decomposes ROE to show what is actually driving returns."),
        ("Reading: Discounted Cash Flow Valuation",
         "DCF values equity as the present value of expected free cash flows plus a terminal "
         "value, discounted at WACC. The output is highly sensitive to the discount rate and "
         "terminal-growth assumption, so sensitivity analysis is essential."),
        ("Reading: Relative Valuation with Multiples",
         "Comparables value a company against peers using multiples such as EV/EBITDA and "
         "P/E. The art is choosing a truly comparable peer set and adjusting for differences "
         "in growth, margins, and risk before reconciling with an intrinsic estimate."),
        ("Reading: Earnings Quality",
         "Reported earnings can diverge from economic reality. Comparing net income to "
         "operating cash flow, and watching accruals like a rising receivables-to-sales "
         "ratio, helps an analyst judge whether reported growth is real and sustainable."),
    ],
    competency_description=(
        "The learner can independently value an unfamiliar company — grounding the analysis in "
        "its financial statements and ratios, building and reconciling DCF and comparables "
        "valuations, and reasoning about risks and sensitivities — to reach a defensible "
        "investment recommendation."
    ),
    sub_competency_description=(
        "The learner can complete one bounded securities-analysis task accurately — such as a "
        "DuPont ROE decomposition or a single DCF — selecting and applying the appropriate "
        "method for that task."
    ),
)


_COURSES: dict[str, SubjectContent] = {
    "ACCY-111": _ACCY_111,
    "ACCY-374": _ACCY_374,
    "ACCY-491": _ACCY_491,
    "FINC-106": _FINC_106,
    "FINC-321": _FINC_321,
    "FINC-439": _FINC_439,
}


def subject_for(course_code: str) -> str:
    prefix = course_code.upper()
    if prefix.startswith("ACCY"):
        return "accounting"
    if prefix.startswith("FINC"):
        return "finance"
    # Don't silently mislabel an unrecognized prefix — a new subject area must add
    # its own content, not inherit the wrong one.
    raise ValueError(f"Unrecognized course-code prefix: {course_code!r} (expected ACCY* or FINC*)")


def content_for(course_code: str) -> SubjectContent:
    """Per-course curated content. Validates the prefix (raises on an unknown
    subject), then resolves the specific course — raising if the course has no
    content block rather than reusing another course's pool (#34)."""
    subject_for(course_code)  # reject unknown prefixes with a clear message
    try:
        return _COURSES[course_code.upper()]
    except KeyError:
        raise ValueError(
            f"No curated content for course {course_code!r}; add a block in content.py "
            f"(known: {', '.join(sorted(_COURSES))})"
        ) from None
