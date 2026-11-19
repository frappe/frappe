import { describe, expect, it } from "vitest";
import {
	allVersionsBlock,
	appLine,
	headerApp,
	listedApps,
	versionText,
	type AppVersion,
	type AppVersions,
} from "../about";

const app = (version: string, extra: Partial<AppVersion> = {}): AppVersion => ({
	title: version,
	description: "",
	version,
	branch: "",
	logo: null,
	...extra,
});

const VERSIONS: AppVersions = {
	erpnext: app("16.0.0"),
	frappe: app("17.0.0", { branch: "develop", branch_version: "17.x.x-develop (abc1234)" }),
	crm: app("2.0.0"),
};

describe("about", () => {
	it("shows the branch after the version, except a pr branch", () => {
		expect(versionText(app("1.2.3", { branch: "version-15" }))).toBe("1.2.3 (version-15)");
		expect(versionText(app("1.2.3", { branch: "pr-123" }))).toBe("1.2.3");
		expect(versionText(app("1.2.3"))).toBe("1.2.3");
	});

	it("heads with the current app, and with Frappe Framework when it is not installed or none is open", () => {
		expect(headerApp(VERSIONS, "crm")?.name).toBe("crm");
		expect(headerApp(VERSIONS, null)?.name).toBe("frappe");
		expect(headerApp(VERSIONS, "gone")?.name).toBe("frappe");
	});

	it("lists Frappe Framework first, then the rest, less the header", () => {
		expect(listedApps(VERSIONS, "crm").map((one) => one.name)).toEqual(["frappe", "erpnext"]);
		expect(listedApps(VERSIONS, "frappe").map((one) => one.name)).toEqual(["erpnext", "crm"]);
	});

	it("copies an app as `app: version`", () => {
		expect(appLine("crm", VERSIONS.crm)).toBe("crm: 2.0.0");
	});

	it("copies every version as a fenced JSON block, a branch build by its branch version", () => {
		expect(JSON.parse(allVersionsBlock(VERSIONS).split("\n").slice(1, -1).join("\n"))).toEqual({
			erpnext: "16.0.0",
			frappe: "17.x.x-develop (abc1234)",
			crm: "2.0.0",
		});
		expect(allVersionsBlock(VERSIONS).startsWith("```json\n")).toBe(true);
		expect(allVersionsBlock(VERSIONS).endsWith("\n```")).toBe(true);
	});
});
