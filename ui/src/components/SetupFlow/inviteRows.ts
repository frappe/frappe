import { computed, ref, type Ref } from "vue";

export type InviteRow = {
	id: number;
	email: string;
	role: string;
	/** Done: invited now, or already had access (`existing`). Locked either way. */
	sent: boolean;
	existing: boolean;
};

export type RowText = { invalid: string; duplicate: string; empty: string };

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const normal = (email: string) => email.trim().toLowerCase();

/**
 * The rows of an invite step and what is wrong with each. A bad address shows once the owner
 * leaves its field or tries to send or add a row, so it does not flag an address still being
 * typed; a repeated one shows at once.
 */
export function useInviteRows(options: {
	firstRole: string;
	role: () => string;
	maxRows: () => number;
	validate: () => ((email: string) => boolean) | undefined;
	text: () => RowText;
}) {
	let lastId = 0;
	const newRow = (role = options.role()): InviteRow => ({
		id: ++lastId,
		email: "",
		role,
		sent: false,
		existing: false,
	});
	const rows = ref<InviteRow[]>([newRow(options.firstRole), newRow()]) as Ref<InviteRow[]>;
	const attempted = ref(false);
	const blocked = ref<number | null>(null);
	const touched = ref(new Set<number>());

	const isValid = (email: string) => (options.validate() ?? ((e) => EMAIL.test(e)))(email);

	const problems = computed(() => {
		const text = options.text();
		const seen = new Set(rows.value.filter((row) => row.sent).map((row) => normal(row.email)));
		const found: Record<number, string> = {};
		for (const row of rows.value) {
			const email = normal(row.email);
			if (row.sent) continue;
			if (!email) {
				if (row.id === blocked.value) found[row.id] = text.empty;
				continue;
			}
			if (seen.has(email)) found[row.id] = text.duplicate;
			else if ((attempted.value || touched.value.has(row.id)) && !isValid(email))
				found[row.id] = text.invalid;
			seen.add(email);
		}
		return found;
	});
	const pending = computed(() => rows.value.filter((row) => !row.sent && row.email.trim()));
	const atLimit = computed(() => rows.value.length >= options.maxRows());

	/** True when every typed row can be sent; otherwise shows what is wrong. */
	function check() {
		attempted.value = true;
		return !pending.value.some((row) => problems.value[row.id] || !isValid(normal(row.email)));
	}

	/** Adds a row, or returns the first unfinished row so the step can point at it. */
	function add(): InviteRow | undefined {
		const unfinished = rows.value.find(
			(row) => !row.sent && (!isValid(normal(row.email)) || problems.value[row.id])
		);
		if (unfinished) {
			attempted.value = true;
			blocked.value = unfinished.id;
			return unfinished;
		}
		blocked.value = null;
		if (!atLimit.value) rows.value.push(newRow());
	}

	function touch(id: number) {
		touched.value = new Set([...touched.value, id]);
	}

	function remove(index: number) {
		rows.value.splice(index, 1);
		if (!rows.value.length) rows.value.push(newRow());
	}

	return { rows, problems, pending, atLimit, isValid, check, add, touch, remove };
}
