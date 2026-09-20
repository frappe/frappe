import { computed, nextTick, ref } from "vue";

export function call_format(name, method, args = {}) {
	return frappe.call("frappe.printing.doctype.print_format.print_format." + method, {
		name,
		...args,
	});
}

export function useDraftSave({
	name,
	print_format,
	letterhead,
	layout,
	dirty,
	viewing_version,
	get_preview_format_doc,
	fetch,
	after_replace,
}) {
	// count, not a flag — autosave and a manual save can overlap
	const saving_count = ref(0);
	const save_failed = ref(false);
	const has_draft = ref(false);
	const save_status = computed(() =>
		save_failed.value
			? "failed"
			: saving_count.value > 0
			? "saving"
			: has_draft.value
			? "draft"
			: "saved"
	);
	// bumped by every apply/discard so a reply from an autosave that was already in
	// flight can't put the draft back after it was cleared
	let draft_epoch = 0;
	// stops after a failure so the error dialog doesn't loop; a manual save re-arms it
	let autosave_stopped = false;
	// one autosave at a time — a second would carry the same `modified` as the one
	// still in flight and be rejected as stale. An apply/discard moves the timestamp
	// too, so a queued autosave waits for it rather than firing against the old one.
	let autosave_inflight = false;
	let autosave_promise = null;
	let applying = false;

	const call = (method, args) => call_format(name, method, args);

	// an autosave already in flight will move `modified` on; wait it out so an
	// explicit write reads the fresh stamp instead of being rejected as stale
	function after_autosave() {
		return Promise.resolve(autosave_promise).catch(() => {});
	}
	// a write that replaces the loaded format: freeze so an edit made during the
	// round trip isn't silently erased when fetch() swaps the layout, then re-arm
	// autosave the way a deliberate reset should
	function replace_from_server(freeze_label, request, message) {
		frappe.dom.freeze(freeze_label);
		draft_epoch++;
		applying = true;
		return after_autosave()
			.then(request)
			.then(() => fetch())
			.then(() => after_replace())
			.then(() => {
				autosave_stopped = false;
				save_failed.value = false;
				frappe.show_alert({ message, indicator: "green" });
			})
			.finally(() => {
				applying = false;
				frappe.dom.unfreeze();
			});
	}
	function save_changes() {
		saving_count.value++;
		return replace_from_server(
			__("Applying…"),
			() =>
				save_letterhead().then(() =>
					call("apply_draft", {
						data: get_preview_format_doc(),
						modified: print_format.value.modified,
					})
				),
			__("Applied")
		)
			.catch(() => (save_failed.value = true))
			.finally(() => saving_count.value--);
	}
	// the letterhead goes first so apply-time validation reads its live state
	function save_letterhead() {
		if (!letterhead.value?._dirty) return Promise.resolve();
		return frappe
			.call("frappe.client.save", { doc: letterhead.value })
			.then((r) => (letterhead.value = r.message));
	}
	function autosave_changes() {
		if (!dirty.value || autosave_stopped || viewing_version.value) return;
		if (applying || autosave_inflight || document.body.classList.contains("pfb-dragging")) {
			autosave();
			return;
		}
		autosave_inflight = true;
		dirty.value = false;
		saving_count.value++;
		const epoch = draft_epoch;
		autosave_promise = call("save_draft", {
			data: get_preview_format_doc(),
			modified: print_format.value.modified,
		})
			.then((r) => {
				// sync only the stamp — the user may have kept editing mid-request
				const was_dirty = dirty.value;
				print_format.value.modified = r.message;
				if (epoch !== draft_epoch) return;
				has_draft.value = true;
				if (!was_dirty) nextTick(() => (dirty.value = false));
				if (letterhead.value && letterhead.value._dirty) {
					return frappe
						.call("frappe.client.save", { doc: letterhead.value })
						.then((res) => {
							letterhead.value.modified = res.message.modified;
							letterhead.value._dirty = false;
						});
				}
			})
			.then(() => (save_failed.value = false))
			.catch(() => {
				// an apply landed first and moved the timestamp on — not a failure
				if (epoch !== draft_epoch) return;
				autosave_stopped = true;
				dirty.value = true;
				save_failed.value = true;
			})
			.always(() => {
				autosave_inflight = false;
				saving_count.value--;
			});
	}
	const autosave = frappe.utils.debounce(autosave_changes, 3000);

	return {
		saving_count,
		save_failed,
		has_draft,
		save_status,
		call_format: call,
		after_autosave,
		replace_from_server,
		save_changes,
		save_letterhead,
		autosave,
	};
}
