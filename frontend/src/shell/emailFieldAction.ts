// The email button of a Data field with options Email: the shell's own field action, as the apps' call button is theirs.
import { isEmailField } from "@framework/ui/fields";
import type { FieldAction, FieldMeta, FieldRecord } from "@framework/ui/fields/types";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { doctypeRight } from "@/acts/doctypeRight";
import { __ } from "@/i18n";
import { composerRecordFor, keptWriters } from "./composer";

/** What the button needs of the email writer, which the shell does not import: the app hands it in. */
export interface EmailOpeners {
	/** Opens the email writer floating on a record whose page is not mounted. */
	openAway(doctype: string, name: string, to: string[], perms: Record<string, unknown>): void;
	/** Adds the addresses to the To of the record's unsent email draft, if it has one. */
	addRecipients(doctype: string, name: string, to: string[]): void;
}

const ADDRESS = /^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/;

/** The addresses a value holds, or none when any part of it is not an address. */
function addressesOf(value: string): string[] {
	const parts = value.split(/[,;\n]/).map((part) => part.trim()).filter(Boolean);
	return parts.length && parts.every((part) => ADDRESS.test(part)) ? parts : [];
}

/** The button for an Email field that holds an address, when the reader holds the `email` right on its doctype. */
export function emailFieldAction(
	field: FieldMeta,
	value: string,
	record: FieldRecord | undefined,
	openers: EmailOpeners
): FieldAction[] {
	if (!record || !isEmailField(field)) return [];
	const to = addressesOf(value);
	if (!to.length) return [];
	if (!doctypeRight.passes({ doctype: record.doctype, ptype: "email" })) return [];
	if (record.surface === "record") {
		// The record page's own rights are narrower than the doctype's.
		const context = composerRecordFor(record.doctype, record.name);
		const page = context?.page;
		// A script may hide the email writer: then the button has nothing to open.
		if (!page || !context.perms.email || !context.writers?.some((writer) => writer.name === "email")) return [];
		return [
			button(() => {
				openers.addRecipients(record.doctype, record.name, to);
				page.composer.open("email", { draft: { to } });
			}),
		];
	}
	// A page the reader visited may have hidden the email writer for good.
	if (keptWriters(record.doctype, record.name)?.some((writer) => writer.name === "email") === false) return [];
	const perms = { email: true, write: useDocPermissions(record.doctype).holds("write") };
	return [button(() => openers.openAway(record.doctype, record.name, to, perms))];
}

function button(run: () => void): FieldAction {
	return { act: "shell.email", label: __("Email"), icon: "lucide-mail", run };
}
