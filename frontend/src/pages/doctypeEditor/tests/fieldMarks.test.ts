// The marks after a field's label: the title field, rules and what Customize did to it.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import FieldMarks from "../FieldMarks.vue";
import { mountEditor, taskNote } from "./editorFixture";

let app: App | undefined;
let stop: (() => void) | undefined;
afterEach(() => {
	app?.unmount();
	stop?.();
	app = stop = undefined;
	document.body.innerHTML = "";
});

function marks(fieldname: string, edit?: (editor: ReturnType<typeof mountEditor>) => void) {
	const editor = mountEditor(taskNote());
	stop = editor.stop;
	edit?.(editor);
	const root = document.body.appendChild(document.createElement("div"));
	app = createApp({ render: () => h(FieldMarks, { canvas: editor.canvas, fieldname }) });
	app.mount(root);
	return root;
}

describe("FieldMarks", () => {
	it("draws nothing for a plain field", async () => {
		const root = marks("status");
		await nextTick();
		expect(root.querySelector("[data-canvas-marks]")).toBeNull();
	});

	it("tags the title field, after a word joiner that keeps it with the label's last word", async () => {
		const root = marks("subject", ({ canvas }) => {
			canvas.working.value.settings.properties.title_field = "subject";
		});
		await nextTick();
		const mark = root.querySelector("[data-canvas-marks]")!;
		expect(mark.textContent).toBe("⁠· Title field");
		expect(mark.querySelector('[data-canvas-mark="title"]')).not.toBeNull();
	});
});
