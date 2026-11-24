import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import StandingPanel from "./StandingPanel";
import type { Standing } from "./matchingApi";

afterEach(cleanup);

const NOTE = "Based only on listed qualifications, not experience, interviews or other factors.";

function standing(overrides: Partial<Standing>): Standing {
  return {
    status: "percentile",
    label: null,
    percentile: null,
    fraction: null,
    score: null,
    max_score: null,
    pool_size: 1,
    other_applicants: 0,
    as_of: "2026-11-11T15:00:00",
    message: null,
    breakdown: [],
    suggestions: [],
    missing: [],
    profile_nudge: null,
    note: NOTE,
    ...overrides,
  };
}

function expectNoProbabilityWording(container: HTMLElement) {
  const text = container.textContent?.toLowerCase() ?? "";
  expect(text).not.toContain("chance");
  expect(text).not.toContain("probability");
}

describe("StandingPanel", () => {
  it("renders percentile mode", () => {
    const { container } = render(
      <StandingPanel
        standing={standing({
          status: "percentile",
          label: "Below most applicants",
          percentile: 39,
          score: 2,
          max_score: 9,
          pool_size: 9,
          other_applicants: 8,
          breakdown: [
            { key: "skill.docker", name: "Docker", weight: 2, has: true, share: 0.67, highlight: null },
            { key: "skill.aws", name: "AWS", weight: 1, has: false, share: 0.33, highlight: null },
            { key: "skill.k8s", name: "Kubernetes", weight: 3, has: false, share: 0.67, highlight: "Most applicants have this" },
          ],
          suggestions: [{ key: "skill.k8s", name: "Kubernetes", current: 39, new: 67, improvement: 28 }],
        })}
      />
    );
    expect(screen.getByText("Below most applicants")).toBeTruthy();
    expect(screen.getByText(/Ahead of 39% of qualified applicants/)).toBeTruthy();
    expect(screen.getByText(/8 other qualified applicants/)).toBeTruthy();
    expect(screen.getByText("Most applicants have this")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Applicants with it" })).toBeTruthy();
    // A low result always comes with its suggestions.
    expect(screen.getByText("What would help most")).toBeTruthy();
    expect(screen.getByText(/from 39% to\s+67%/)).toBeTruthy();
    expect(screen.getByText(NOTE)).toBeTruthy();
    expectNoProbabilityWording(container);
  });

  it("renders fraction mode", () => {
    const { container } = render(
      <StandingPanel
        standing={standing({
          status: "fraction",
          label: "Partial match",
          fraction: 0.5,
          score: 2,
          max_score: 4,
          pool_size: 3,
          other_applicants: 2,
          message: "Not enough applicants yet to compare.",
          breakdown: [{ key: "skill.bi", name: "Power BI", weight: 2, has: true, share: null, highlight: null }],
          suggestions: [{ key: "skill.excel", name: "Microsoft Excel", current: 0.5, new: 0.75, improvement: 0.25 }],
          profile_nudge: "Your profile lists 3 qualifications. Make sure everything from your resume is added.",
        })}
      />
    );
    expect(screen.getByText("Partial match")).toBeTruthy();
    expect(screen.getByText(/You have 50% of\s+the bonus points/)).toBeTruthy();
    expect(screen.getByText("Not enough applicants yet to compare.")).toBeTruthy();
    expect(screen.queryByText(/Ahead of/)).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Applicants with it" })).toBeNull();
    expect(screen.getByText(/2 other qualified applicants/)).toBeTruthy();
    expect(screen.getByText(/from 50% to\s+75%/)).toBeTruthy();
    expect(screen.getByText(/Your profile lists 3 qualifications/)).toBeTruthy();
    expect(screen.getByText(NOTE)).toBeTruthy();
    expectNoProbabilityWording(container);
  });

  it("renders equal_on_paper", () => {
    const { container } = render(
      <StandingPanel
        standing={standing({
          status: "equal_on_paper",
          score: 0,
          max_score: 0,
          other_applicants: 1,
          message:
            "This listing has no bonus qualifications, so all qualified applicants are equal on paper",
        })}
      />
    );
    expect(
      screen.getByText(
        "This listing has no bonus qualifications, so all qualified applicants are equal on paper."
      )
    ).toBeTruthy();
    expect(screen.getByText(/1 other qualified applicant ·/)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText(NOTE)).toBeTruthy();
    expectNoProbabilityWording(container);
  });

  it("shows what's missing when not qualified", () => {
    render(
      <StandingPanel
        standing={standing({
          status: "not_qualified",
          missing: [{ key: "degree.phd.cs", name: "PhD — Computer Science", status: "missing", possible_name: null }],
        })}
      />
    );
    expect(screen.getByText("No standing yet")).toBeTruthy();
    expect(screen.getByText("PhD — Computer Science")).toBeTruthy();
    expect(screen.queryByText(/Ahead of/)).toBeNull();
  });
});
