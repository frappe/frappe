// The engine's commit channel and field marks for a record page's form and panel, forwarded so they follow the controller across loads.
import { computed, provide } from "vue";
import { CommitKey, FieldErrorsKey } from "@framework/ui/fields/types";
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
