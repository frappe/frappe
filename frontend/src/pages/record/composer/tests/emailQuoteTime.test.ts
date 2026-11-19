// The "On …, … wrote:" line names the email's time on the site's clock, not the browser's.
import { resetSession, setSession } from "@framework/ui/useSession";
import { afterEach, describe, expect, it } from "vitest";
import { quoteEmail } from "../emailQuote";

const email = { sender: "bob@example.com", content: "<p>Hi</p>" } as never;

afterEach(resetSession);

describe("quoteEmail time", () => {
	it("reads the stamp as written, whatever the browser's zone, in the site's zone", () => {
		setSession({ user: {}, roles: [], lang: "en", timezone: "Asia/Kolkata", defaults: {} } as never);
		expect(quoteEmail(email, "2026-11-04 10:00:00")).toContain("On November 4, 2026 10:00 AM, bob@example.com wrote:");
	});

	it("leaves the time out for a row with no stamp", () => {
		expect(quoteEmail(email)).toContain("bob@example.com wrote:");
	});
});
