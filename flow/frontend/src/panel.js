// In the launcher's panel, the app around it keeps the keyboard's shortcuts
export const inPanel = window.top !== window;
// the page around the panel: Desk, or a frappe-ui app. frameElement, unlike parent.location, is
// null rather than an error when another site frames the page
const around = window.frameElement?.ownerDocument.location.pathname;
export const panelHost = !inPanel ? null : around?.startsWith("/desk") ? "desk" : "app";
