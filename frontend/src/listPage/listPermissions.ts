// What the list page's handlers and acts ask about rights: the doctype's rights at level 0 and the roles.
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useSession } from "@framework/ui/useSession";
import { useUserRoles } from "@framework/ui/useUserRoles";
import type { ActRight } from "@/acts/dispatcher";
import { whenLoaded } from "@/acts/doctypeRight";
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
	/** An act's right on the list's doctype; its create right is the list's Create rule. */
	passes: (right: ActRight) => boolean;
	loading: () => boolean;
	/** Resolves once roles and meta are in. */
	ready: () => Promise<void>;
}

export function useListPermissions(doctype: string): ListPermissions {
	const canCreate = useCreateRight(doctype);
	const { holds, loading } = useDocPermissions(doctype);
	const { roles } = useUserRoles();
	const { session } = useSession();
	const passes = (right: ActRight) => {
		if (typeof right !== "string") return false;
		if (right === "create") return canCreate.value;
		return session.value?.user.name === "Administrator" || holds(right);
	};
	return {
		perms: () => Object.fromEntries(RIGHTS.map((right) => [right, passes(right) ? 1 : 0])),
		roles: () => [...(roles.value ?? [])],
		passes,
		loading: () => loading.value,
		ready: () => whenLoaded(loading),
	};
}
