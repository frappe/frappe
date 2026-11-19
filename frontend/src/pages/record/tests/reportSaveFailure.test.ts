// A failure a dialog already explained shows no toast; any other failure toasts its message.
import { beforeEach, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/i18n", () => ({ __: (text: string) => text }));

import { toast } from "frappe-ui";
import { reportSaveFailure } from "../recordSave";
import { cancelledError, SAVE_CONFLICT } from "../saveResponse";

beforeEach(() => vi.mocked(toast.error).mockClear());

it("toasts the message of a failure no dialog explained", () => {
	reportSaveFailure(new Error("Mandatory: Title"));

	expect(toast.error).toHaveBeenCalledExactlyOnceWith("Mandatory: Title");
});

it.each([
	["a conflict", Object.assign(new Error("Saved elsewhere"), { name: SAVE_CONFLICT })],
	["a cancelled required-fields dialog", cancelledError()],
])("shows nothing for %s", (_what, error) => {
	reportSaveFailure(error);

	expect(toast.error).not.toHaveBeenCalled();
});
