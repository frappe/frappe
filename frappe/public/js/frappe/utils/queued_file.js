/**
 * The file name to show for a queued upload, read back from its file URL.
 * Shared by the review dialog and the review form, which ship as separate bundles.
 */
export function queued_file_name(file_url) {
	const segment = String(file_url || "").split("?", 1)[0].split("/").pop();
	try {
		return decodeURIComponent(segment);
	} catch (e) {
		return segment;
	}
}
