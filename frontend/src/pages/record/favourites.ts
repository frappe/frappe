// Who has favourited the record: the `favourites` rows of `docinfo`, named by its `user_info`.
import { personOf, type DocInfo } from "./panel/context";
import type { Person } from "./panel/people";

/** Everyone who favourited the record, the reader first and named "You". */
export function favouritesOf(docinfo: DocInfo | null, reader: string): Person[] {
	return (docinfo?.favourites ?? [])
		.map((row) => row.user)
		.sort((one, two) => Number(two === reader) - Number(one === reader))
		.map((user) => (user === reader ? { id: user, name: "You" } : personOf(docinfo, user)));
}

export function hasFavourited(docinfo: DocInfo | null, reader: string): boolean {
	return (docinfo?.favourites ?? []).some((row) => row.user === reader);
}
