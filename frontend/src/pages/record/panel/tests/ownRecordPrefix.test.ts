import { describe, expect, it } from "vitest";
import { withoutOwnRecordPrefix } from "../ownRecordPrefix";

const strip = (message: string, name = "TASK-1", doctype = "Task") =>
	withoutOwnRecordPrefix(message, [doctype], name);

describe("withoutOwnRecordPrefix", () => {
	it("drops the doctype and name of this record", () => {
		expect(strip("Task TASK-1: 'Title' (x) will get truncated")).toBe(
			"'Title' (x) will get truncated"
		);
	});

	it("keeps a message that names another record", () => {
		const message = "Task TASK-2: 'Title' (x) will get truncated";
		expect(strip(message)).toBe(message);
		expect(strip("Project TASK-1: 'Title' (x)")).toBe("Project TASK-1: 'Title' (x)");
	});

	it("keeps a message with no prefix, or a name that only starts like this one", () => {
		expect(strip("Title is required")).toBe("Title is required");
		expect(strip("Task TASK-10: bad")).toBe("Task TASK-10: bad");
		expect(strip("The Task TASK-1: bad")).toBe("The Task TASK-1: bad");
	});

	it("drops a prefix whose names the server HTML-escaped", () => {
		expect(strip("Q&amp;A R&amp;D&#39;s: 'Title' (x)", "R&D's", "Q&A")).toBe("'Title' (x)");
		expect(strip("Task &lt;b&gt;1&lt;/b&gt;: bad", "<b>1</b>")).toBe("bad");
	});

	it("drops a prefix whose names are not escaped", () => {
		expect(strip("Q&A R&D's: 'Title' (x)", "R&D's", "Q&A")).toBe("'Title' (x)");
	});

	it("keeps the message when nothing follows the prefix or the record is unknown", () => {
		expect(strip("Task TASK-1: ")).toBe("Task TASK-1: ");
		expect(withoutOwnRecordPrefix("Task TASK-1: bad", [undefined], "TASK-1")).toBe("Task TASK-1: bad");
		expect(withoutOwnRecordPrefix("Task TASK-1: bad", ["Task"], "")).toBe("Task TASK-1: bad");
	});

	it("drops the doctype in the user's language when it is listed", () => {
		expect(withoutOwnRecordPrefix("Aufgabe TASK-1: bad", ["Task", "Aufgabe"], "TASK-1")).toBe("bad");
	});
});
