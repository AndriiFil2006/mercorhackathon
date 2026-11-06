import { describe, it, expect } from "vitest";
import { overall, reviewers, type Review } from "./types";
import { parseReview } from "./api";
const complete = (scores: number[]): Review[] =>
  reviewers.map((r, i) => ({ id: r.id, status: "complete", score: scores[i]! }));
describe("Three-reviewer assessment", () => {
  it("averages only three distinct completed reviewers", () => {
    expect(overall(complete([58, 72, 64]))).toBe(65);
    expect(overall(complete([70, 70, 70]))).toBe(70);
    expect(overall(complete([90, 91, 92]))).toBe(91);
  });
  it("withholds the overall score for partial, failed, duplicate or invalid results", () => {
    expect(overall(complete([90, 80, 70]).slice(0, 2))).toBeNull();
    const reviews = complete([90, 80, 70]);
    reviews[0]!.status = "error";
    expect(overall(reviews)).toBeNull();
    expect(
      overall([complete([90, 80, 70])[0]!, complete([90, 80, 70])[0]!, complete([90, 80, 70])[0]!]),
    ).toBeNull();
    expect(overall(complete([NaN, 80, 90]))).toBeNull();
    expect(overall(complete([101, 80, 90]))).toBeNull();
  });
  it("rejects invalid scores and unsafe citation links from the service", () => {
    const good = {
      score: 88,
      model: "Model A",
      explanation: "Finding",
      findings: ["One"],
      sources: [{ title: "Authority", url: "https://example.org" }],
    };
    expect(parseReview("authority", good).score).toBe(88);
    expect(() => parseReview("authority", { ...good, score: "88" })).toThrow();
    expect(() =>
      parseReview("authority", {
        ...good,
        sources: [{ title: "Bad", url: "javascript:alert(1)" }],
      }),
    ).toThrow();
    expect(() => parseReview("authority", { ...good, model: "" })).toThrow();
  });
});
