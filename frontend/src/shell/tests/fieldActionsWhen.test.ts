// A field action follows the `when` of the act it places, read from the real dispatcher.
import { describe, expect, it, vi } from "vitest";

const files = vi.hoisted(() => [] as { app: string; load: () => Promise<{ default?: unknown }> }[]);

vi.mock("@/contributions/registry", () => ({ fieldActionFiles: files }));
vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));

import { acts } from "@/acts/dispatcher";
import { FieldActionItems, fieldActions } from "../fieldActions";

describe("field actions and the act's when", () => {
	it("draw only while the act's when holds", async () => {
		let medium = "";
		acts.register({
			surfaces: {
				shell: () => [{ item: { name: "crm.call", label: "Call", when: () => medium === "twilio", run: () => {} }, hidden: false }],
			},
			context: () => null,
			passes: () => true,
			settled: () => undefined,
			hold: async (work) => work(),
			failed: () => {},
		});
		files.push({ app: "crm", load: async () => ({ default: [{ fieldtype: "Phone", act: "shell.crm.call" }] }) });
		const host = fieldActions({ openAway() {}, addRecipients() {} }, new FieldActionItems());
		const phone = { fieldname: "mobile_no", fieldtype: "Phone" } as never;
		host.for(phone, "123");
		await new Promise((resolve) => setTimeout(resolve));

		expect(host.for(phone, "123")).toHaveLength(0);
		medium = "twilio";
		expect(host.for(phone, "123")).toHaveLength(1);
	});
});
