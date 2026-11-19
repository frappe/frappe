// Whether a bulk run exists in this tab: the shell mounts the tray (a lazy chunk) only after the first one.
import { ref } from "vue";

export const bulkTrayShown = ref(false);
