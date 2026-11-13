// The app's layouts behind a Customize site layout, drawn read-only as Design reads them.
import { DesignCanvas } from "./designCanvas";
import type { EditorState } from "./editorSource";
import { PendingEdits } from "./pendingEdits";

/** A read-only canvas of the app's layouts, open at the one with the site layout's condition, else the default. */
export function appLayoutCanvas(canvas: DesignCanvas): DesignCanvas {
	const { state } = canvas;
	const app: EditorState = { ...state, mode: "Design", modes: [], custom: 0 };
	const head = { doctype: state.doctype, mode: app.mode, base_version: state.base_version };
	const view = new DesignCanvas(app, new PendingEdits(head, () => undefined));
	const { type } = canvas.openLayout.value;
	const condition = canvas.layout.value?.condition;
	const same = condition && view.working.value.layouts[type]?.layouts.find((one) => one.condition === condition);
	view.open(same ? { type, id: same.id } : { type });
	return view;
}
