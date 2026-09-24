import { computed, nextTick, ref } from "vue";
import { zone_fields } from "../components/letterhead/zone_fields";

const LETTERHEAD_EDITED_FIELDS = [
	...Object.values(zone_fields("header")),
	...Object.values(zone_fields("footer")),
	"custom_css",
];

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
	const last_error = ref("");
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
	// paused after a failure so the error dialog doesn't loop; the next edit,
	// a manual save or a flush re-arms it
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
	let letterhead_push = Promise.resolve();
	function push_letterhead() {
		// one at a time — the manual save and the autosave can both ask, and the
		// second would carry the timestamp the first is about to move
		const run = () => {
			const ours = Object.fromEntries(
				LETTERHEAD_EDITED_FIELDS.map((key) => [key, letterhead.value[key]])
			);
			return frappe
				.call({
					method: "frappe.client.save",
					args: { doc: letterhead.value },
					silent: true,
				})
				.catch((xhr) => {
					if (xhr?.responseJSON?.exc_type !== "TimestampMismatchError") throw xhr;
					return frappe.db
						.get_doc("Letter Head", letterhead.value.name)
						.then((fresh) => {
							letterhead.value = Object.assign(fresh, ours, { _dirty: true });
							return frappe.call("frappe.client.save", { doc: letterhead.value });
						});
				});
		};
		letterhead_push = letterhead_push.then(run, run);
		return letterhead_push;
	}
	function save_letterhead() {
		if (!letterhead.value?._dirty) return Promise.resolve();
		return push_letterhead().then((r) => (letterhead.value = r.message));
	}
	function server_message(xhr) {
		let r = xhr?.responseJSON;
		if (!r && xhr?.responseText) {
			try {
				r = JSON.parse(xhr.responseText);
			} catch {
				r = null;
			}
		}
		try {
			const messages = JSON.parse(r?._server_messages || "[]").map(
				(m) => JSON.parse(m).message
			);
			if (messages.length) return messages.join("<br>");
		} catch {
			// not a frappe error payload
		}
		return r?.exc_type || xhr?.statusText || "";
	}
	function report_failure(xhr) {
		last_error.value = server_message(xhr);
		if (save_failed.value) return;
		const message = __("The latest changes to this print format are not saved.");
		// a 500 already opened the framework's Server Error dialog
		if (xhr?.status === 500) {
			frappe.show_alert({ message, indicator: "red" });
			return;
		}
		frappe.msgprint({
			title: __("Autosave failed"),
			indicator: "red",
			message: message + (last_error.value ? `<br><br>${last_error.value}` : ""),
		});
	}
	function resume_autosave() {
		if (!autosave_stopped) return;
		autosave_stopped = false;
		autosave();
	}
	// one last attempt before leaving; rejects with the server message when the
	// changes are still unsaved so the caller can warn instead of dropping them
	function flush() {
		autosave.cancel();
		return after_autosave()
			.then(() => {
				if (viewing_version.value || applying) return;
				if (dirty.value) {
					autosave_stopped = false;
					autosave_changes();
				}
				return after_autosave();
			})
			.then(() => {
				if (save_failed.value || (dirty.value && !viewing_version.value)) {
					return Promise.reject(last_error.value);
				}
			});
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
		autosave_promise = frappe
			.call({
				method: "frappe.printing.doctype.print_format.print_format.save_draft",
				args: {
					name,
					data: get_preview_format_doc(),
					modified: print_format.value.modified,
				},
				silent: true,
			})
			.then((r) => {
				// sync only the stamp — the user may have kept editing mid-request
				const was_dirty = dirty.value;
				print_format.value.modified = r.message;
				if (epoch !== draft_epoch) return;
				has_draft.value = true;
				if (!was_dirty) nextTick(() => (dirty.value = false));
				if (letterhead.value && letterhead.value._dirty) {
					return push_letterhead().then((res) => {
						letterhead.value.modified = res.message.modified;
						letterhead.value._dirty = false;
					});
				}
			})
			.then(() => {
				save_failed.value = false;
				last_error.value = "";
			})
			.catch((xhr) => {
				// an apply landed first and moved the timestamp on — not a failure
				if (epoch !== draft_epoch) return;
				autosave_stopped = true;
				dirty.value = true;
				report_failure(xhr);
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
		resume_autosave,
		flush,
	};
}
