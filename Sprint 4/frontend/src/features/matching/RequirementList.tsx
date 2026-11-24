import type { RequirementResult, RequirementStatus } from "./matchingApi";

// One row per listing requirement, with the seeker's status. Every status has
// an icon AND a text label, so it never depends on colour alone.

export const STATUS_DISPLAY: Record<RequirementStatus, { icon: string; label: string }> = {
  met: { icon: "✓", label: "Met" },
  missing: { icon: "✗", label: "Missing" },
  bonus_missing: { icon: "+", label: "Bonus — not on your profile" },
  possible: { icon: "?", label: "Possible match" },
};

interface RequirementListProps {
  items: RequirementResult[];
  // Called by "I have this" on a possible match. Omit to hide the button.
  onClaim?: (key: string) => void;
  claimingKey?: string | null;
}

export default function RequirementList({ items, onClaim, claimingKey = null }: RequirementListProps) {
  if (items.length === 0) {
    return <p className="cc-muted">This listing doesn't list specific qualifications.</p>;
  }

  return (
    <ul className="cc-reqs" aria-label="Listed qualifications">
      {items.map((item) => {
        const display = STATUS_DISPLAY[item.status];
        return (
          <li key={item.key} className={`cc-req cc-req--${item.status}`} data-status={item.status}>
            <span className="cc-req-icon" aria-hidden="true">
              {display.icon}
            </span>
            <span className="cc-req-body">
              <span className="cc-req-name">{item.name}</span>
              <span className="cc-req-kind">
                {item.is_required ? "Required" : `Bonus · weight ${item.weight}`}
              </span>
              <span className="cc-req-status">{display.label}</span>
              {item.status === "met" && item.exceeds && (
                <span className="cc-req-note">You exceed this requirement</span>
              )}
              {item.status === "possible" && item.possible_name && (
                <span className="cc-req-note">Your entry “{item.possible_name}” looks similar but isn't verified.</span>
              )}
            </span>
            {item.status === "possible" && onClaim && (
              <button
                type="button"
                className="cc-upload-btn cc-btn-secondary cc-req-claim"
                onClick={() => onClaim(item.key)}
                disabled={claimingKey === item.key}
              >
                {claimingKey === item.key ? "Adding…" : "I have this"}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
