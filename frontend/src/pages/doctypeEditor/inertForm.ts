// The record page's real controls on a form that holds nothing: an empty doc, no commit channel,
// and an `inert` box so a Link never opens or searches.
import { inject, provide, ref, type InjectionKey } from "vue";
import { useFieldTypes } from "@framework/ui/FormLayout";
import { CommitKey, DocKey, NO_COMMIT, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";

export function provideInertForm() {
	provide(DocKey, ref({}));
	provide(UpdateKey, () => undefined);
	provide(CommitKey, NO_COMMIT);
	provide(ResolveFieldKey, useFieldTypes().resolve);
}

const PANEL_ROWS: InjectionKey<boolean> = Symbol("panel rows");

/** The side panel's canvas draws each field as the record panel's label-left row. */
export function providePanelRows() {
	provide(PANEL_ROWS, true);
}

export function usePanelRows(): boolean {
	return inject(PANEL_ROWS, false);
}
