// The reader's open sections, remembered through the shell's section memory.
import { beforeEach, describe, expect, it } from "vitest";
import { ref } from "vue";
import { useDisclosure } from "../disclosure";

const READER = "reader@example.com";

beforeEach(() => localStorage.clear());

describe("useDisclosure", () => {
	it("answers the section's own default until the reader decides", () => {
		const disclosure = useDisclosure(READER, "Record:CRM Deal", [
			{ name: "organization_section", opened: true },
			{ name: "audit", opened: false },
		]);
		expect(disclosure.isOpen("organization_section")).toBe(true);
		expect(disclosure.isOpen("audit")).toBe(false);
	});

	it("remembers a toggle across a fresh instance, per doctype and per reader", () => {
		const first = useDisclosure(READER, "Record:CRM Deal", [{ name: "a", opened: true }]);
		first.toggle("a");
		expect(first.isOpen("a")).toBe(false);

		const again = useDisclosure(READER, "Record:CRM Deal", [{ name: "a", opened: true }]);
		expect(again.isOpen("a")).toBe(false);

		const other = useDisclosure(READER, "Record:CRM Lead", [{ name: "a", opened: true }]);
		expect(other.isOpen("a")).toBe(true);
		const someone = useDisclosure("else@example.com", "Record:CRM Deal", [{ name: "a", opened: true }]);
		expect(someone.isOpen("a")).toBe(true);
	});

	it("keeps a script's act on the page and out of the reader's memory", () => {
		const disclosure = useDisclosure(READER, "Record:CRM Deal", [{ name: "a", opened: true }]);
		disclosure.disclose("a", false);
		expect(disclosure.isOpen("a")).toBe(false);
		expect(useDisclosure(READER, "Record:CRM Deal", [{ name: "a", opened: true }]).isOpen("a")).toBe(true);

		// The reader's click outranks the act, and a new record starts clean.
		disclosure.toggle("a");
		expect(disclosure.isOpen("a")).toBe(true);
		disclosure.disclose("a", false);
		disclosure.reset();
		expect(disclosure.isOpen("a")).toBe(true);
	});

	it("follows the sections as a replay changes them", () => {
		const sections = ref([{ name: "a", opened: true }]);
		const disclosure = useDisclosure(READER, "Record:CRM Deal", sections);
		disclosure.set("a", false);

		sections.value = [
			{ name: "a", opened: true },
			{ name: "added", opened: false },
		];
		expect(disclosure.isOpen("a")).toBe(false);
		expect(disclosure.isOpen("added")).toBe(false);
		disclosure.set("added", true);
		expect(disclosure.isOpen("added")).toBe(true);
	});
});
