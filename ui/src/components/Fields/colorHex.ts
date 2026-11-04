/** Desk v1's color swatches, in its order. */
export const SWATCHES = [
  "#171717",
  "#7c7c7c",
  "#ce2c2c",
  "#d35a09",
  "#ca7e0c",
  "#ab790d",
  "#268c5c",
  "#0a857b",
  "#1f8cad",
  "#077ddf",
  "#6e57d1",
  "#8e49ca",
  "#cf3a96",
];

/** A typed color as the stored lowercase `#rrggbb`; `null` when it is not a hex color. */
export function normalizeHex(text: string): string | null {
  const digits = text.trim().replace(/^#/, "").toLowerCase();
  if (/^[0-9a-f]{6}$/.test(digits)) return `#${digits}`;
  if (/^[0-9a-f]{3}$/.test(digits)) return `#${[...digits].map((d) => d + d).join("")}`;
  return null;
}
