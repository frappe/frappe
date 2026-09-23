// Who an email goes out as: read once a session, and the four cases the writer draws from it.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { runMethod } = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { chooseSender, loadSenders, resetSenders, searchRecipients } from "../emailSenders";

const ME = "ann@example.com";

beforeEach(() => {
	vi.clearAllMocks();
	resetSenders();
});

describe("chooseSender", () => {
	it("offers a From row with two or more, the user's own address picked", () => {
		const answer = { senders: ["sales@example.com", ME], default: null };
		expect(chooseSender(answer, ME, "")).toEqual({
			senders: ["sales@example.com", ME],
			from: ME,
			blocked: false,
		});
		expect(chooseSender(answer, "zed@example.com", "").from).toBe("sales@example.com");
		expect(chooseSender(answer, ME, "sales@example.com").from).toBe("sales@example.com");
	});

	it("sends as the one sender there is, with no From row", () => {
		expect(chooseSender({ senders: [ME], default: null }, ME, "")).toEqual({
			senders: [ME],
			from: ME,
			blocked: false,
		});
	});

	it("leaves the sender to the server when only a default account exists", () => {
		expect(chooseSender({ senders: [], default: "notify@example.com" }, ME, "")).toEqual({
			senders: [],
			from: "",
			blocked: false,
		});
	});

	it("blocks sending with no sender and no default", () => {
		expect(chooseSender({ senders: [], default: null }, ME, "")).toEqual({
			senders: [],
			from: "",
			blocked: true,
		});
	});
});

describe("loadSenders", () => {
	it("asks once a session by GET", async () => {
		runMethod.mockResolvedValue({ data: { senders: [ME], default: null } });
		await loadSenders();
		await loadSenders();
		expect(runMethod).toHaveBeenCalledTimes(1);
		expect(runMethod).toHaveBeenCalledWith(
			"frappe.email.inbox.get_outgoing_senders",
			{},
			{ http: "GET" }
		);
	});

	it("asks again after a failure", async () => {
		runMethod.mockRejectedValueOnce(new Error("Offline"));
		await expect(loadSenders()).rejects.toThrow("Offline");
		runMethod.mockResolvedValue({ data: { senders: [], default: null } });
		await expect(loadSenders()).resolves.toEqual({ senders: [], default: null });
		expect(runMethod).toHaveBeenCalledTimes(2);
	});
});

describe("searchRecipients", () => {
	it("reads the contact list and names each address by its contact", async () => {
		runMethod.mockResolvedValue({
			data: [
				{ value: "bob@example.com", label: "bob@example.com", description: "Bob" },
				{ value: "carl@example.com", label: "carl@example.com", description: null },
			],
		});
		expect(await searchRecipients("bo")).toEqual([
			{ email: "bob@example.com", label: "Bob" },
			{ email: "carl@example.com", label: undefined },
		]);
		expect(runMethod).toHaveBeenCalledWith(
			"frappe.email.get_contact_list",
			{ txt: "bo" },
			{ http: "GET" }
		);
	});
});
