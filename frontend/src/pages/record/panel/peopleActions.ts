// The six writes the people editors make, each followed by a re-read of `docinfo`.
import { errorMessage } from "@/recordPage";
import type { PanelContext } from "./context";

export function peopleActions(context: PanelContext) {
	const { doctype, docname, controller, reloadDocinfo } = context;
	const page = controller.page;

	// The answer is discarded: only the re-read paints, so the row never disagrees with the server.
	// A failed re-read toasts too: the write landed, and the row is now stale.
	async function send(method: string, params: Record<string, any>) {
		try {
			await page.call(method, params);
			await reloadDocinfo();
		} catch (caught) {
			page.toast.error(errorMessage(caught));
		}
	}

	return {
		assign: (user: string) =>
			send("frappe.desk.form.assign_to.add", { doctype, name: docname, assign_to: [user] }),
		unassign: (user: string) =>
			send("frappe.desk.form.assign_to.remove", { doctype, name: docname, assign_to: user }),
		share: (user: string) =>
			send("frappe.share.add", { doctype, name: docname, user, read: 1, write: 1 }),
		// Dropping read drops the higher rights with it, and the empty share deletes itself.
		unshare: (user: string, everyone = false) =>
			send("frappe.share.set_permission", {
				doctype,
				name: docname,
				user: everyone ? null : user,
				permission_to: "read",
				value: 0,
				everyone: everyone ? 1 : 0,
			}),
		addTag: (tag: string) =>
			send("frappe.desk.doctype.tag.tag.add_tag", { tag, dt: doctype, dn: docname }),
		removeTag: (tag: string) =>
			send("frappe.desk.doctype.tag.tag.remove_tag", { tag, dt: doctype, dn: docname }),
	};
}

export type PeopleActions = ReturnType<typeof peopleActions>;
