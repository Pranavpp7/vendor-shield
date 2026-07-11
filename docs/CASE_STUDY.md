# VendorShield — Case Study

*How an AI vendor-risk tool went from RAG demo to a field-tested product — and
what it took to make the AI's judgments trustworthy.*

## The problem

Before a company onboards a third-party vendor, a security analyst reads a
stack of SOC 2 reports, whitepapers, and policy PDFs, then fills in a control
checklist by hand — hours per vendor, hundreds of vendors, procurement blocked
until it's done. This is third-party risk management (TPRM), the market served
by Vanta (~$2.4B), Drata, Whistic, and UpGuard, several of which now ship AI
document review as a headline feature.

## What was built

A self-hosted assessment platform: upload a vendor's security documents, pick
a control framework (NIST SP 800-53 — 21 controls, SOC 2 TSC — 10, or **your
own**: upload any security standard and the system drafts it as a framework
for human review). A LangGraph agent retrieves evidence per control from a
local vector store and has an LLM score each control PASS / PARTIAL / FAIL /
NO_EVIDENCE with a verbatim quote, auditor-style reasoning, and an actionable
gap. Analysts review a queue of uncertain verdicts and can override any score
— the AI verdict is preserved as an audit trail and every total recalculates.
Gaps become auto-drafted follow-up questions to send the vendor. Everything
exports to PDF and CSV, and every run is metered: **~$0.006 and 1–3 minutes
per assessment**.

## What makes it trustworthy (the actual engineering story)

**1. Model changes are eval-gated.** A golden dataset of fictional vendors
with expected per-control scores runs against the real pipeline. On its first
run it caught a production bug: one LLM provider wrapped JSON in bare
```` ``` ```` fences the parser didn't strip, silently converting correct PASS
verdicts into NO_EVIDENCE — agreement jumped **75% → 100%** after the fix. The
gate later **rejected two free-tier model configurations** (both 19/30) that
returned malformed output under load, before a single real assessment ran on
them.

**2. Evidence must be the vendor's own claim.** Field testing on Cloudflare's
public documents exposed a classic RAG failure: a vendor-agnostic "Roadmap to
Zero Trust" buyer's guide was quoted as if the vendor itself used the products
it merely listed ("SIEM: Datadog, Splunk, SolarWinds"). Fixes: an explicit
**attribution rule** in the scoring prompt (generic reader-directed guidance
is never self-attestation — pinned by its own eval case), and
**document-diversified retrieval** after measuring that the generic guide had
won **71% of all evidence slots** and was the top match for 18 of 20 controls
(now capped at ≤50%; the vendor's actual security summary went from 4 slots to
26).

**3. The score is honest about uncertainty.** Scoring semantics went through
three documented iterations, driven by two real, contradictory field reports:
a SOC 2 + ISO 27001 certified vendor scored 28/100 High Risk because unknowns
were counted as failures (v1); after over-correcting, a vendor with 11 of 20
controls unverifiable scored a comfortable 50/100 Medium (v2). The final
design (v3) reports **three numbers**: an evidence-weighted headline where an
unverifiable control counts as unaccepted risk, a *verified average* showing
how the checkable controls performed, and *coverage* — because one number
cannot carry both "how good is what we verified" and "how much we verified."

**4. Field testing is the QA strategy.** A single day of real-document
click-through produced a 7-bug fix batch (dead chat rendering, score
semantics, mislabeled confidence bars, an executive summary that called
unverified controls "failed", retrieval starvation, a stubbed PDF button,
broken dates) — every fix landed with a regression test. Suites: **131
backend + 23 frontend tests**, CI on every push.

## Honest limitations

Single-analyst scope; self-hosted by design (vendor documents are sensitive —
only LLM inference leaves the machine); judgment quality bounded by a 70B
open-weight model; usage history of a handful of real vendors, not thousands.

## The one-line takeaway

The interesting work in AI products isn't the model call — it's the scoring
semantics, the attribution rules, the human-override loop, and the evals that
catch the model lying before a user does.
