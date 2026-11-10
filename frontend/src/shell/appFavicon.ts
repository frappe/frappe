// The tab icon an app's `brand` hook sets for its own prefix; the page ships the framework's.

export function applyAppFavicon(favicon: string | null | undefined) {
	if (!favicon) return;

	const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
	if (link) link.href = favicon;
}
