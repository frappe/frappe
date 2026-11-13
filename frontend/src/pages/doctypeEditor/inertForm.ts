// The record page's real controls on a form that holds nothing: an empty doc, no commit channel,
// and an `inert` box so a Link never opens or searches.
import { provide, ref } from "vue";
import { useFieldTypes } from "@framework/ui/FormLayout";
import { CommitKey, DocKey, NO_COMMIT, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";

export function provideInertForm() {
	provide(DocKey, ref({}));
	provide(UpdateKey, () => undefined);
	provide(CommitKey, NO_COMMIT);
	provide(ResolveFieldKey, useFieldTypes().resolve);
}
