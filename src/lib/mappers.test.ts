import { describe, expect, it } from "vitest";
import { mapBackendAssessment, mapControl, mapDomainScores, scoreToStatus } from "./mappers";

const rawControl = (overrides: Record<string, unknown> = {}) => ({
  control_id: "GR-001",
  score: "FAIL",
  confidence: 0.8,
  reasoning: "because",
  evidence_quote: "quote",
  domain: "Governance & Risk",
  title: "Security governance",
  citations: [],
  ...overrides,
});

describe("scoreToStatus", () => {
  it.each([
    ["PASS", "passed"],
    ["FAIL", "failed"],
    ["PARTIAL", "partial"],
    ["NO_EVIDENCE", "needs_info"],
    ["anything-else", "needs_info"],
  ])("maps %s → %s", (input, expected) => {
    expect(scoreToStatus(input)).toBe(expected);
  });
});

describe("mapControl", () => {
  it("shows the AI score when there is no override", () => {
    const c = mapControl(rawControl());
    expect(c.status).toBe("failed");
    expect(c.aiScore).toBe("FAIL");
    expect(c.analystScore).toBeNull();
  });

  it("analyst override supersedes the AI score but preserves it", () => {
    const c = mapControl(rawControl({ analyst_score: "PASS", analyst_comment: "verified" }));
    expect(c.status).toBe("passed");
    expect(c.passed).toBe(true);
    expect(c.aiScore).toBe("FAIL");       // audit trail intact
    expect(c.analystComment).toBe("verified");
  });

  it("carries the needs_review flag through", () => {
    expect(mapControl(rawControl({ needs_review: true })).needsReview).toBe(true);
    expect(mapControl(rawControl()).needsReview).toBe(false);
  });
});

describe("mapDomainScores", () => {
  it("counts effective (override-aware) scores per domain", () => {
    const raw = [
      rawControl(),                                        // FAIL
      rawControl({ control_id: "GR-002", analyst_score: "PASS" }), // FAIL→PASS
    ];
    const [domain] = mapDomainScores({ "Governance & Risk": 50 }, raw);
    expect(domain.failed).toBe(1);
    expect(domain.passed).toBe(1);
  });

  it("returns empty for missing dict", () => {
    expect(mapDomainScores(undefined, [])).toEqual([]);
  });
});

describe("mapBackendAssessment", () => {
  it("maps the enriched backend record", () => {
    const assessment = mapBackendAssessment({
      id: "a1",
      vendor_name: "Acme",
      status: "completed",
      overall_score: 85,
      risk_level: "Low",
      control_results: [rawControl({ score: "PASS" })],
      framework_id: "soc2-tsc",
      review_queue: ["GR-001"],
      risk_profile: { data_sensitivity: "high", business_criticality: "high", access_scope: "high" },
      inherent_risk: { tier: "Critical", points: 9 },
      residual_risk: "Medium",
      created_at: "2026-07-03",
    });
    expect(assessment.status).toBe("Completed");
    expect(assessment.frameworkId).toBe("soc2-tsc");
    expect(assessment.reviewQueue).toEqual(["GR-001"]);
    expect(assessment.inherentRisk?.tier).toBe("Critical");
    expect(assessment.residualRisk).toBe("Medium");
  });

  it("defaults framework and enrichment fields for legacy records", () => {
    const assessment = mapBackendAssessment({ id: "old", vendor_name: "Legacy" });
    expect(assessment.frameworkId).toBe("nist-800-53");
    expect(assessment.reviewQueue).toEqual([]);
    expect(assessment.residualRisk).toBeNull();
  });
});
