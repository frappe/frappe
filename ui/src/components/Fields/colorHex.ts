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

/** Hue in degrees, saturation and value in 0..1. */
export type Hsv = { h: number; s: number; v: number };

export function hsvToHex({ h, s, v }: Hsv): string {
  const channel = (n: number) => {
    const k = (n + h / 60) % 6;
    return v - v * s * Math.max(0, Math.min(k, 4 - k, 1));
  };
  return `#${[channel(5), channel(3), channel(1)]
    .map((c) => Math.round(c * 255).toString(16).padStart(2, "0"))
    .join("")}`;
}

/** A gray has no hue of its own, so it keeps `hue` and the hue slider does not jump to red. */
export function hexToHsv(hex: string, hue = 0): Hsv {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const v = Math.max(r, g, b);
  const d = v - Math.min(r, g, b);
  const s = v ? d / v : 0;
  if (!d) return { h: hue, s, v };
  const sector = v === r ? (g - b) / d : v === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return { h: (sector * 60 + 360) % 360, s, v };
}
