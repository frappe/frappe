import { expect } from "@playwright/test";

// A dialog moves focus to its first input once it has faded in, so anything typed before that
// is lost.
export async function shown_dialog(dialog) {
	await expect.poll(() => dialog.evaluate((d) => d.display)).toBe(true);
	return dialog;
}
