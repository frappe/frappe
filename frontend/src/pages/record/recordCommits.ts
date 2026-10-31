// The engine's commit channel, field marks and Button clicks for a record page's form and panel, forwarded so they follow the controller across loads.
import { computed, provide } from "vue";
import { CommitKey, FieldErrorsKey } from "@framework/ui/fields/types";
import type { Decorator } from "@framework/ui/FormLayout";
import type { RecordPageController } from "@/recordPage";

export function provideRecordCommits(controller: () => RecordPageController | null) {
	provide(CommitKey, {
		pending: (fieldname, value, row) => controller()?.commits.pending(fieldname, value, row),
		commit: (fieldname, value, row) => controller()?.commits.commit(fieldname, value, row),
		rowChanged: (row, change) => controller()?.commits.rowChanged(row, change),
	});
	provide(
		FieldErrorsKey,
		computed(() => controller()?.fieldErrors.drawn.value ?? {})
	);
}

/** A Button field's click fires the handler keyed by its fieldname, as desk v1's `frm.trigger` does. */
export function buttonClicks(controller: () => RecordPageController | null): Decorator {
	return ({ fieldtype, fieldname }) => {
		if (fieldtype !== "Button") return;
		return {
			on: {
				// Child fields are decorated too, with no row to address: a grid cell hands its row last.
				click: (_event: MouseEvent, row?: object) => {
					const page = controller();
					if (row || !page?.fields.has(fieldname)) return;
					if (page.fields.get(fieldname)?.fieldtype === "Button") page.commits.trigger(fieldname);
				},
			},
		};
	};
}
