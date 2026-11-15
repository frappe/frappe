// The section menu's move labels are translated when the menu opens, not when the module loads.
import { expect, it, vi } from "vitest";

const lang = vi.hoisted(() => ({ prefix: "" }));
vi.mock("@/i18n", () => ({ __: (text: string) => lang.prefix + text }));

import { canvasMenu } from "../canvasMenu";
import { mountEditor, taskNote } from "./editorFixture";

it("reads each move label when the menu is built", () => {
	const { canvas, stop } = mountEditor(taskNote());
	lang.prefix = "T:";
	const labels = canvasMenu(canvas, { kind: "section", section: "main" }).map((option) => option.label);
	stop();
	expect(labels.slice(0, 4)).toEqual(["T:Move up", "T:Move down", "T:Move to the tab before", "T:Move to the tab after"]);
});
