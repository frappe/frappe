// Whether the person may create a doctype's records, from the meta and session the page already
// holds. It can miss a disabled module; the insert checks again.
import { computed, inject, type ComputedRef } from "vue";
import { useDoctypeMeta, type DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { useSession } from "@framework/ui/composables/useSession";
import type { Boot } from "@/boot";

/** False until the meta and the session load. */
export function useCreateRight(doctype: string): ComputedRef<boolean> {
	const { meta } = useDoctypeMeta(doctype);
	const { session } = useSession();
	const boot = inject<Boot>("boot")!;
	return computed(() => {
		if (!meta.value || !session.value) return false;
		return canCreate(meta.value, {
			user: session.value.user.name,
			roles: session.value.roles,
			readOnlyMode: boot.read_only_mode,
		});
	});
}

/** Desk v1's rule: a level 0 create row for one of the roles, on a doctype taking new records. */
export function canCreate(
	meta: DoctypeMeta,
	person: { user: string; roles: string[]; readOnlyMode: boolean }
): boolean {
	if (person.readOnlyMode || meta.issingle || meta.istable || meta.in_create) return false;
	if (person.user === "Administrator") return true;
	return (meta.permissions ?? []).some(
		(row) =>
			(row.permlevel ?? 0) === 0 && Boolean(row.create) && person.roles.includes(row.role)
	);
}
