// Shared by the sidebar avatar and the Profile tab's photo block so both show
// the same fallback when the user has no photo.

// Two-letter initials from a full name,
// falling back to "?" if the name somehow produces nothing.
export function getInitials(fullName: string): string {
  return (
    fullName
      .trim()
      .split(/\s+/)
      .map((part) => part.charAt(0))
      .join("")
      .slice(0, 2)
      .toUpperCase() || "?"
  );
}
