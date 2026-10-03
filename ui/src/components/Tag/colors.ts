export const TAG_COLORS: Record<string, string> = {
  Gray: "bg-surface-gray-5",
  Black: "bg-surface-gray-10",
  Blue: "bg-surface-blue-6",
  Green: "bg-surface-green-6",
  Red: "bg-surface-red-6",
  Pink: "bg-surface-pink-6",
  Orange: "bg-surface-orange-6",
  Amber: "bg-surface-amber-6",
  Yellow: "bg-surface-yellow-6",
  Cyan: "bg-surface-cyan-6",
  Teal: "bg-surface-teal-6",
  Violet: "bg-surface-violet-6",
  Purple: "bg-surface-purple-6",
};

export const TAG_COLOR_NAMES = Object.keys(TAG_COLORS);

export function colorToken(color?: string): string {
  return TAG_COLORS[color ?? ""] ?? TAG_COLORS.Gray;
}
