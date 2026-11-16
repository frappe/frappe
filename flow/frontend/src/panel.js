// In the launcher's panel, the app around it keeps the keyboard's shortcuts. The island's
// entry sets these before the chat mounts: the page around the panel is Desk ("desk") or a
// frappe-ui app ("app"); the /flow page has none
export let inPanel = false;
export let panelHost = null;

export function setPanel(host) {
	inPanel = Boolean(host);
	panelHost = host || null;
}
