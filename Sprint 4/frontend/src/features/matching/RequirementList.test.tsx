import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import RequirementList from "./RequirementList";
import type { RequirementResult } from "./matchingApi";

afterEach(cleanup);

function item(key: string, overrides: Partial<RequirementResult>): RequirementResult {
  return {
    key,
    name: key,
    category: "skill",
    is_required: true,
    weight: 1,
    status: "met",
    exceeds: false,
    possible_name: null,
    ...overrides,
  };
}

const ITEMS: RequirementResult[] = [
  item("Python", { status: "met" }),
  item("Bachelor's degree (any field)", { status: "met", exceeds: true, category: "degree" }),
  item("Docker", { status: "missing" }),
  item("Kubernetes", { status: "bonus_missing", is_required: false, weight: 3 }),
  item("WHMIS (SIMDUT)", { status: "possible", category: "certification", possible_name: "WHMISS" }),
];

function row(name: string) {
  return screen.getByText(name).closest("li") as HTMLElement;
}

describe("RequirementList", () => {
  it.each([
    ["Python", "met", "✓", "Met"],
    ["Docker", "missing", "✗", "Missing"],
    ["Kubernetes", "bonus_missing", "+", "Bonus — not on your profile"],
    ["WHMIS (SIMDUT)", "possible", "?", "Possible match"],
  ])("shows %s as %s with an icon and a text label", (name, status, icon, label) => {
    render(<RequirementList items={ITEMS} />);
    const li = row(name);
    expect(li.dataset.status).toBe(status);
    expect(li.querySelector(".cc-req-icon")?.textContent).toBe(icon);
    // The text label is there, not just the colour.
    expect(within(li).getByText(label)).toBeTruthy();
  });

  it("notes when a requirement is exceeded", () => {
    render(<RequirementList items={ITEMS} />);
    expect(within(row("Bachelor's degree (any field)")).getByText("You exceed this requirement")).toBeTruthy();
    expect(within(row("Python")).queryByText("You exceed this requirement")).toBeNull();
  });

  it("labels required and bonus items", () => {
    render(<RequirementList items={ITEMS} />);
    expect(within(row("Docker")).getByText("Required")).toBeTruthy();
    expect(within(row("Kubernetes")).getByText("Bonus · weight 3")).toBeTruthy();
  });

  it("offers 'I have this' only on possible matches", () => {
    const onClaim = vi.fn();
    render(<RequirementList items={ITEMS} onClaim={onClaim} />);
    const buttons = screen.getAllByRole("button", { name: "I have this" });
    expect(buttons).toHaveLength(1);
    expect(within(row("WHMIS (SIMDUT)")).getByText(/WHMISS/)).toBeTruthy();
    fireEvent.click(buttons[0]);
    expect(onClaim).toHaveBeenCalledWith("WHMIS (SIMDUT)");
  });

  it("says so when a listing has no requirements", () => {
    render(<RequirementList items={[]} />);
    expect(screen.getByText("This listing doesn't list specific qualifications.")).toBeTruthy();
  });
});
