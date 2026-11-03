// `shell.record`: the saved record open on the page, read from the page's own act scope.
import { afterEach, describe, expect, it } from "vitest";
import { acts, type ActScope } from "@/acts/dispatcher";
import { openRecord } from "../shellActs";

const releases: (() => void)[] = [];

function openPage(page: Record<string, any>, surface = "header") {
	const scope: ActScope = {
		surfaces: { [surface]: () => [] },
		context: () => page,
		passes: () => true,
		settled: () => undefined,
		hold: async (work) => work(),
		failed: () => {},
	};
	releases.push(acts.register(scope));
}

afterEach(() => releases.splice(0).forEach((release) => release()));

describe("shell.record", () => {
	it("is null with no page open", () => {
		expect(openRecord()).toBeNull();
	});

	it("reads the doctype, name, draft and field labels of a saved record", () => {
		openPage({
			doctype: "CRM Lead",
			docname: "CRM-LEAD-1",
			isNew: false,
			doc: { mobile_no: "+1 555 0100" },
			meta: {
				fields: [
					{
						fieldname: "mobile_no",
						label: "Mobile No",
						fieldtype: "Data",
						options: "Phone",
						reqd: 1,
					},
					{
						fieldname: "source",
						label: "Source",
						fieldtype: "Link",
						options: "CRM Lead Source",
					},
				],
			},
		});
		expect(openRecord()).toEqual({
			doctype: "CRM Lead",
			name: "CRM-LEAD-1",
			doc: { mobile_no: "+1 555 0100" },
			fields: [
				{ fieldname: "mobile_no", label: "Mobile No", fieldtype: "Phone" },
				{ fieldname: "source", label: "Source", fieldtype: "Link" },
			],
		});
	});

	it("is null on a new record, and a page with no meta has no fields", () => {
		openPage({
			doctype: "Contact",
			docname: "new",
			isNew: true,
			doc: {},
			meta: null,
		});
		expect(openRecord()).toBeNull();
		releases.splice(0).forEach((release) => release());
		openPage({
			doctype: "Contact",
			docname: "C-1",
			isNew: false,
			doc: {},
			meta: null,
		});
		expect(openRecord()?.fields).toEqual([]);
	});
});
