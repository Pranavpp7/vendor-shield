import { describe, expect, it } from "vitest";
import { needsAnalystJudgment, reviewQueue } from "./reviewQueue";
import { ControlResult } from "@/types/assessment";

const control = (over: Partial<ControlResult>): ControlResult => ({
  id: "X-001",
  category: "Test",
  name: "Test control",
  passed: false,
  status: "needs_info",
  comment: "",
  needsReview: false,
  analystScore: null,
  ...over,
});

describe("needsAnalystJudgment (shared by tab badge AND ReviewPanel list)", () => {
  it("queues NO_EVIDENCE (needs_info) controls", () => {
    expect(needsAnalystJudgment(control({ status: "needs_info" }))).toBe(true);
  });

  it("queues PARTIAL controls", () => {
    expect(needsAnalystJudgment(control({ status: "partial" }))).toBe(true);
  });

  it("queues low-confidence controls even when passed", () => {
    expect(needsAnalystJudgment(control({ status: "passed", needsReview: true }))).toBe(true);
  });

  it("does NOT force settled PASS/FAIL verdicts into the queue", () => {
    expect(needsAnalystJudgment(control({ status: "passed" }))).toBe(false);
    expect(needsAnalystJudgment(control({ status: "failed" }))).toBe(false);
  });

  it("removes controls once the analyst has ruled", () => {
    expect(
      needsAnalystJudgment(control({ status: "needs_info", analystScore: "PASS" }))
    ).toBe(false);
  });

  it("matches the reported bug scenario: 1P/0F/12NI/8Pa → queue = 20", () => {
    const controls = [
      control({ id: "P1", status: "passed" }),
      ...Array.from({ length: 12 }, (_, i) =>
        control({ id: `NI${i}`, status: "needs_info", needsReview: true })
      ),
      ...Array.from({ length: 8 }, (_, i) => control({ id: `PA${i}`, status: "partial" })),
    ];
    expect(controls).toHaveLength(21);
    expect(reviewQueue(controls)).toHaveLength(20); // badge AND list agree
  });
});
