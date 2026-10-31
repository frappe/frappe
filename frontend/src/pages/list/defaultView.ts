// Sets or clears one layer's default view of a doctype, and keeps the answer in boot for the router.
import { runMethod } from "@framework/ui/api";
import type { Boot } from "@/boot";

const API = "frappe.desk.doctype.default_view.api";

export type DefaultScope = "user" | "site";

/** Points `scope`'s default at the view `key`, a view type's name for its plain view. */
export async function setDefaultView(boot: Boot, doctype: string, key: string, scope: DefaultScope) {
	const { data } = await runMethod<string>(`${API}.save`, { doctype, key, scope }, { nullable: true });
	remember(boot, doctype, data);
}

export async function clearDefaultView(boot: Boot, doctype: string, scope: DefaultScope) {
	const { data } = await runMethod<string>(`${API}.clear`, { doctype, scope }, { nullable: true });
	remember(boot, doctype, data);
}

/** The server answers with the person's default after the change, whichever layer now holds it. */
function remember(boot: Boot, doctype: string, view: string | null) {
	const defaults = (boot.default_views ??= {});
	if (view) defaults[doctype] = view;
	else delete defaults[doctype];
}
