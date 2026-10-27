/**
 * The video id in a YouTube link: watch?v=, youtu.be/, shorts/, live/, embed/ and v/, on
 * youtube.com or youtube-nocookie.com. A bare id is accepted as is, since that is what the field
 * used to hold.
 */
export function get_youtube_id(value) {
	value = (value || "").trim();
	if (/^[\w-]{11}$/.test(value)) return value;

	let url;
	try {
		url = new URL(value);
	} catch {
		return null;
	}

	const host = url.hostname.replace(/^(www|m|music)\./, "");
	let id = null;
	if (host === "youtu.be") {
		id = url.pathname.split("/")[1];
	} else if (host === "youtube.com" || host === "youtube-nocookie.com") {
		id =
			url.pathname === "/watch"
				? url.searchParams.get("v")
				: url.pathname.match(/^\/(?:embed|shorts|live|v)\/([\w-]+)/)?.[1];
	}
	return id && /^[\w-]{6,}$/.test(id) ? id : null;
}
