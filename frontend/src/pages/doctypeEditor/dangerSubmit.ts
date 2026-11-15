// A Danger zone dialog's Confirm: it sends the act's call, and a failure stays in the dialog.
import { computed, ref } from "vue";
import { errorMessage } from "@/recordPage/errorMessage";

export function useDangerSubmit<V, R>(submit: (value: V) => Promise<R>, close: (result: R) => void) {
	const working = ref(false);
	const error = ref("");
	// The spinner would widen the Confirm button and shift Cancel: it keeps the width it had when pressed.
	const confirmButton = ref<{ $el: HTMLElement } | null>(null);
	const pinnedWidth = ref(0);
	const confirmStyle = computed(() => (working.value && pinnedWidth.value ? { minWidth: `${pinnedWidth.value}px` } : undefined));

	async function send(value: V) {
		if (working.value) return;
		pinnedWidth.value = confirmButton.value?.$el.getBoundingClientRect().width ?? 0;
		working.value = true;
		error.value = "";
		try {
			close(await submit(value));
		} catch (exception) {
			error.value = errorMessage(exception);
		} finally {
			working.value = false;
		}
	}

	return { working, error, send, confirmButton, confirmStyle };
}
