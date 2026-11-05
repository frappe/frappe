import { dialog } from "frappe-ui";
import { nextTick } from "vue";
import { translate as __ } from "../../utils/translate";
import type { EmailAccount } from "./types";

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

/**
 * Runs `save` for `changes` to `account`, first asking when they turn off a direction it is the
 * default for, since the site then has no default account to receive or send with.
 */
export function confirmDefaultsOff(
  account: Pick<
    EmailAccount,
    "email_account_name" | "default_incoming" | "default_outgoing"
  >,
  changes: Record<string, unknown>,
  save: () => void,
) {
  const off = (["incoming", "outgoing"] as const).filter(
    (kind) => account[`default_${kind}`] && changes[`enable_${kind}`] === 0,
  );
  if (!off.length) return save();
  const name = account.email_account_name;
  dialog.confirm({
    title: __("Turn off the default account?"),
    message:
      off.length === 2
        ? __(
            "{0} is the default incoming and outgoing account. Turn these off and you won't be able to receive or send email.",
            [name],
          )
        : off[0] === "incoming"
          ? __(
              "{0} is the default incoming account. Turn this off and you won't be able to receive email.",
              [name],
            )
          : __(
              "{0} is the default outgoing account. Turn this off and you won't be able to send email.",
              [name],
            ),
    confirmLabel: __("Turn off"),
    cancelLabel: __("Cancel"),
    onConfirm({ close }) {
      close();
      save();
    },
  });
}
