// Whether the person may create a doctype's records, from the meta and session the page already
// holds. It can miss a disabled module; the insert checks again.
import { computed, inject, type ComputedRef, type MaybeRefOrGetter } from "vue";
import { useDocPermissions } from "@framework/ui/composables/useDocPermissions";
import { useDoctypeMeta, type DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { useSession } from "@framework/ui/composables/useSession";
import type { Boot } from "@/boot";

/** False until the meta and the session load. */
export function useCreateRight(doctype: MaybeRefOrGetter<string>): ComputedRef<boolean> {
	const { meta } = useDoctypeMeta(doctype);
	const { allowedPermlevels } = useDocPermissions(doctype);
	const { session } = useSession();
	const boot = inject<Boot>("boot")!;
	return computed(() => {
		if (!meta.value || !session.value) return false;
		return canCreate(meta.value, {
			user: session.value.user.name,
			createsAtLevel0: allowedPermlevels("create").includes(0),
			readOnlyMode: boot.read_only_mode,
		});
	});
}

/** Desk v1's rule: a level 0 create right, on a doctype that takes new records from a list. */
export function canCreate(
	meta: DoctypeMeta,
	person: { user: string; createsAtLevel0: boolean; readOnlyMode: boolean }
): boolean {
	if (person.readOnlyMode || meta.issingle || meta.istable || meta.in_create) return false;
	return person.user === "Administrator" || person.createsAtLevel0;
}
