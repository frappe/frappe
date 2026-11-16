// A dialog that mounts without joining the readable list would let the `dialog` act surface reach the one behind it.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SOURCE = join(__dirname, "../..");
const DIALOG_TAG = /<(Dialog|SettingsDialog|CommandPalette)\b/;
const LISTED = /useReadableDialog|useDialogHandle|entry\.listed/;

function vueFiles(directory: string): string[] {
	return readdirSync(directory).flatMap((name) => {
		const path = join(directory, name);
		if (statSync(path).isDirectory()) return name === "tests" ? [] : vueFiles(path);
		return path.endsWith(".vue") ? [path] : [];
	});
}

describe("every dialog component", () => {
	it("joins the readable list", () => {
		const unlisted = vueFiles(SOURCE)
			.filter((path) => DIALOG_TAG.test(readFileSync(path, "utf8")) && !LISTED.test(readFileSync(path, "utf8")))
			.map((path) => path.slice(SOURCE.length + 1));
		expect(unlisted).toEqual([]);
	});
});
