/**
 * The file name to show for a queued upload, read back from its file URL.
 * Shared by the review dialog and the review form, which ship as separate bundles.
 */
export function queued_file_name(file_url) {
	return decodeURIComponent(file_url.split("?", 1)[0].split("/").pop());
}
