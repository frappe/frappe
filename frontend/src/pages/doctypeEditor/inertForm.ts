// The canvas draws each field with the record page's real control, on a form that holds nothing:
// an empty doc no edit reaches, and no commit channel. Its fields sit in an `inert` box, so a
// Link never opens and never searches.
import { provide, ref } from "vue";
import { useFieldTypes } from "@framework/ui/FormLayout";
import { CommitKey, DocKey, NO_COMMIT, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";

export function provideInertForm() {
	provide(DocKey, ref({}));
	provide(UpdateKey, () => undefined);
	provide(CommitKey, NO_COMMIT);
	provide(ResolveFieldKey, useFieldTypes().resolve);
}
