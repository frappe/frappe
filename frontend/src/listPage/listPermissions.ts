// What the list page's handlers and acts ask about rights: the doctype's rights at level 0 and the roles.
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useSession } from "@framework/ui/useSession";
import { useUserRoles } from "@framework/ui/useUserRoles";
import type { ActRight } from "@/acts/dispatcher";
import { doctypeRight, whenLoaded } from "@/acts/doctypeRight";
import { useCreateRight } from "@/createRight";

// A list has no record to read rights from, so `page.perms` names the standard ones from the roles.
const RIGHTS = [
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"import",
	"export",
	"share",
];

export interface ListPermissions {
	perms: () => Record<string, 0 | 1>;
	roles: () => string[];
	/** A name is the list doctype's right (create follows the list's Create rule); `{ doctype, ptype }` is that doctype's. */
	passes: (right: ActRight) => boolean;
	/** A promise while `passes` cannot answer for the right yet; else nothing. */
	settled: (right: ActRight) => Promise<void> | undefined;
	loading: () => boolean;
	/** Resolves once roles and meta are in. */
	ready: () => Promise<void>;
}

export function useListPermissions(doctype: string): ListPermissions {
	const canCreate = useCreateRight(doctype);
	const { holds, loading } = useDocPermissions(doctype);
	const { roles } = useUserRoles();
	const { session } = useSession();
	const passes = (right: ActRight): boolean => {
		if (typeof right !== "string")
			return right.doctype === doctype ? passes(right.ptype) : doctypeRight.passes(right);
		if (right === "create") return canCreate.value;
		return session.value?.user.name === "Administrator" || holds(right);
	};
	return {
		perms: () => Object.fromEntries(RIGHTS.map((right) => [right, passes(right) ? 1 : 0])),
		roles: () => [...(roles.value ?? [])],
		passes,
		settled: (right) =>
			typeof right === "string" || right.doctype === doctype
				? loading.value
					? whenLoaded(loading)
					: undefined
				: doctypeRight.settled(right),
		loading: () => loading.value,
		ready: () => whenLoaded(loading),
	};
}
