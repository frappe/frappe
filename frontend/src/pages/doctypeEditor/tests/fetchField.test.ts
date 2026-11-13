import { afterEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import { canvasMenu } from "../canvasMenu";
import { fetchAsked, fetchFromText, fetchSources, linkFields, parseFetchFrom } from "../fetchFrom";
import { mountEditor, taskNote } from "./editorFixture";

let stop: () => void;
afterEach(() => stop());

function mount() {
	const mounted = mountEditor(taskNote());
	stop = mounted.stop;
	return mounted;
}

const FULL_NAME = { fieldname: "full_name", label: "Full Name", fieldtype: "Data" };

async function withOwner() {
	const mounted = mount();
	await acts.run("fields.add_field", {
		label: "Owner",
		fieldtype: "Link",
		options: "User",
		section: "main",
		column: "column_1",
		index: 1,
	});
	return mounted;
}

describe("Fetch a field…", () => {
	it("adds a read-only field fetched from the Link, after it, in one undo step", async () => {
		const { canvas, edits } = await withOwner();
		await acts.run("fields.fetch_field", { link: "owner", source: FULL_NAME });
		expect(canvas.field("full_name")).toMatchObject({
			label: "Full Name",
			fieldtype: "Data",
			read_only: 1,
			fetch_from: "owner.full_name",
		});
		expect(canvas.place("full_name")).toMatchObject({ section: "main", column: "column_1", index: 2 });
		expect(canvas.selection.value).toEqual({ kind: "field", fieldname: "full_name" });
		expect(edits.steps).toHaveLength(2);
		edits.undo();
		expect([canvas.field("full_name"), canvas.place("full_name"), edits.steps.length]).toEqual([
			undefined,
			null,
			1,
		]);
		edits.redo();
		expect(canvas.field("full_name")?.fetch_from).toBe("owner.full_name");
	});

	it("keeps a Link source's DocType, and names a second fetch of one field apart", async () => {
		const { canvas } = await withOwner();
		const language = { fieldname: "language", label: "Language", fieldtype: "Link", options: "Language" };
		await acts.run("fields.fetch_field", { link: "owner", source: language });
		await acts.run("fields.fetch_field", { link: "owner", source: language });
		expect([canvas.field("language")?.options, canvas.field("language_1")?.fetch_from]).toEqual([
			"Language",
			"owner.language",
		]);
	});
});

describe("the canvas menu's Fetch a field…", () => {
	it("shows on a Link field, and selects it and asks the panel to open its picker", async () => {
		const { canvas } = await withOwner();
		const labels = (fieldname: string) => canvasMenu(canvas, { kind: "field", fieldname }).map((one) => one.label);
		expect(labels("subject")).not.toContain("Fetch a field…");
		const fetch = canvasMenu(canvas, { kind: "field", fieldname: "owner" }).find(
			(one) => one.label === "Fetch a field…",
		);
		fetch!.onClick();
		await vi.waitFor(() => expect(fetchAsked.value).toBe("owner"));
		expect(canvas.selection.value).toEqual({ kind: "field", fieldname: "owner" });
		fetchAsked.value = null;
	});

	it("asks once the closing menu has put focus back, so the picker does not close at once", async () => {
		const { canvas } = await withOwner();
		const fetch = canvasMenu(canvas, { kind: "field", fieldname: "owner" }).find(
			(one) => one.label === "Fetch a field…",
		);
		fetch!.onClick();
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(canvas.selection.value).toEqual({ kind: "field", fieldname: "owner" });
		expect(fetchAsked.value).toBeNull();
		document.body.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
		await vi.waitFor(() => expect(fetchAsked.value).toBe("owner"));
		fetchAsked.value = null;
	});
});

describe("the Fetch from picker", () => {
	const user = [
		{ fieldname: "full_name", label: "Full Name", fieldtype: "Data" },
		{ fieldname: "sb0", label: "", fieldtype: "Section Break" },
		{ fieldname: "roles", label: "Roles", fieldtype: "Table", options: "Has Role" },
		{ fieldname: "block_modules", label: "Modules", fieldtype: "Table MultiSelect", options: "Block Module" },
		{ fieldname: "column_break_1", label: "", fieldtype: "Column Break" },
		{ fieldname: "about", label: "About", fieldtype: "HTML" },
		{ fieldname: "reference_name", label: "Reference", fieldtype: "Dynamic Link", options: "reference_doctype" },
		{ fieldname: "language", label: "Language", fieldtype: "Link", options: "Language" },
	];

	it("offers the target's fields that hold a value, not tables, breaks or a Dynamic Link", () => {
		expect(fetchSources(user).map((field) => field.fieldname)).toEqual(["full_name", "language"]);
	});

	it("offers this DocType's Link fields, other than the field itself", () => {
		const fields = [
			{ fieldname: "owner", label: "Owner", fieldtype: "Link", options: "User" },
			{ fieldname: "assignee", label: "Assignee", fieldtype: "Link", options: "User" },
			{ fieldname: "unset", label: "Unset", fieldtype: "Link" },
			{ fieldname: "subject", label: "Subject", fieldtype: "Data" },
		];
		expect(linkFields(fields, "assignee").map((field) => field.fieldname)).toEqual(["owner"]);
	});

	it("stores `<link>.<field>` and reads it back", () => {
		expect(fetchFromText({ link: "owner", source: "full_name" })).toBe("owner.full_name");
		expect(parseFetchFrom("owner.full_name")).toEqual({ link: "owner", source: "full_name" });
		expect([parseFetchFrom(""), parseFetchFrom("owner")]).toEqual([null, null]);
	});
});
