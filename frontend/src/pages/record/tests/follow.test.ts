// The follow gate and the server's reason for a declined follow.
import { describe, expect, it } from "vitest";
import { canFollow, declinedMessage } from "../follow";

const session = (flag: boolean) =>
	({ user: { name: "me@example.com", document_follow_notify: flag } }) as any;

describe("canFollow", () => {
	it("needs both the doctype's tracking and the reader's setting", () => {
		expect(canFollow({ track_changes: 1 }, session(true))).toBe(true);
		expect(canFollow({ track_changes: 0 }, session(true))).toBe(false);
		expect(canFollow({ track_changes: 1 }, session(false))).toBe(false);
		expect(canFollow(null, session(true))).toBe(false);
	});
});

describe("declinedMessage", () => {
	it("is the first message when the follow did not take", () => {
		const answer = {
			data: { follows: false },
			messages: [{ message: "Can't follow since changes are not tracked." }],
		};
		expect(declinedMessage(answer, true)).toBe("Can't follow since changes are not tracked.");
	});

	it("is nothing when the follow took, or the server said nothing", () => {
		const took = { data: { follows: true }, messages: [{ message: "Following document D-1" }] };
		expect(declinedMessage(took, true)).toBeUndefined();
		expect(declinedMessage({ data: { follows: false } }, true)).toBeUndefined();
	});

	it("is nothing on an unfollow, whose answer also carries a message", () => {
		const answer = { data: { follows: false }, messages: [{ message: "Un-following document D-1" }] };
		expect(declinedMessage(answer, false)).toBeUndefined();
	});
});
