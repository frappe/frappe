import { ref } from "vue";

// Internal to `<HelpModal>`: which of its two panes is showing. Not exported
// from the package — `frappe-ui/frappe` exported it, but no app imported it.
export const showHelpCenter = ref(false);
