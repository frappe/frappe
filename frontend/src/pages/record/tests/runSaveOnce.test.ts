// The header's Save swallows a failure into a toast; two clicks that joined one save toast once.
import { beforeEach, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/i18n", () => ({ __: (text: string) => text }));

import { toast } from "frappe-ui";
import type { RecordPageApi } from "@/recordPage";
import { runSave } from "../recordSave";

beforeEach(() => vi.mocked(toast.error).mockClear());

function joinedSave() {
	const failure = new Error("Mandatory: Title");
	const running = Promise.reject(failure);
	return { page: { save: () => running } as unknown as RecordPageApi, failure };
}

it("toasts a failure once for two callers that joined one save, and both report failure", async () => {
	const { page } = joinedSave();

	const both = await Promise.all([runSave(page), runSave(page)]);

	expect(both).toEqual([false, false]);
	expect(toast.error).toHaveBeenCalledExactlyOnceWith("Mandatory: Title");
});

it("toasts again when a later save fails", async () => {
	await runSave(joinedSave().page);
	await runSave(joinedSave().page);

	expect(toast.error).toHaveBeenCalledTimes(2);
});
