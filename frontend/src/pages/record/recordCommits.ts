// One commit channel for a record page's form and panel, forwarded so it follows the controller across loads.
import { provide } from "vue";
import { CommitKey } from "@framework/ui/components/Fields/types";
import type { RecordPageController } from "@/recordPage";

export function provideRecordCommits(controller: () => RecordPageController | null) {
	provide(CommitKey, {
		pending: (fieldname, value, row) => controller()?.commits.pending(fieldname, value, row),
		commit: (fieldname, value, row) => controller()?.commits.commit(fieldname, value, row),
		rowChanged: (row, change) => controller()?.commits.rowChanged(row, change),
	});
}
