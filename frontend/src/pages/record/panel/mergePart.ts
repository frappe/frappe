// Kept apart from peopleActions: the feed code in the shell chunk merges parts, and must not pull the tag writes in.
import type { Users } from "@framework/ui/api";
import type { DocInfo } from "./context";

export type PartAnswer = Partial<DocInfo> & { users?: Users; tag_colors?: Record<string, string> };

/** The answer's part over the old one; its `users` join the map, since a removed row keeps its name. */
export function mergePart(
	docinfo: DocInfo | null,
	{ users, tag_colors: _colors, ...part }: PartAnswer
): DocInfo {
	return { ...docinfo, ...part, users: { ...docinfo?.users, ...users } };
}
