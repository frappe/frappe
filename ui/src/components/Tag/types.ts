import type { TAG_COLORS } from "./colors";

export type TagColor = keyof typeof TAG_COLORS;

export interface Tag {
  name: string;
  color?: TagColor | null;
}
