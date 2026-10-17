import { dialog } from "frappe-ui";
import { nextTick } from "vue";
import { translate as __ } from "../../utils/translate";

/**
 * Asks before unsaved changes are dropped. The confirm traps focus until it renders closed, and
 * refocuses what had focus on open when it unmounts, so focus is cleared and moved after closing.
 */
export function confirmDiscard(
  message: string,
  onConfirm: () => void,
  onCancel: () => void,
) {
  (document.activeElement as HTMLElement | null)?.blur();
  dialog.confirm({
    title: __("Unsaved changes"),
    message,
    confirmLabel: __("Confirm"),
    cancelLabel: __("Cancel"),
    async onConfirm({ close }) {
      close();
      (document.activeElement as HTMLElement | null)?.blur();
      await nextTick();
      onConfirm();
    },
    async onCancel() {
      await nextTick();
      onCancel();
    },
  });
}
