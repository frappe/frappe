// The Files tab's rows and its upload: time orders the record's attachments and a script's rows.
import { compareActivities } from "@framework/ui/ActivityTimeline";
import { attachFile, type AttachmentsPart, type UploadFields } from "@framework/ui/api";
import type { UploadArgs, UploadTransport } from "@framework/ui/FileUpload";
import type { FeedItem, FileRow } from "@/recordPage";

export type FilesListRow = FileRow | FeedItem;

/** Uploads onto the record, handing each answer's refreshed `attachments` part to `keep`. */
export function attachTransport(
	record: { doctype: string; docname: string },
	keep: (part: AttachmentsPart) => void
): UploadTransport {
	return async (file, args, { signal, onProgress, chunkSize }) => {
		const options = { signal, onProgress, chunkSize };
		const fields = uploadFields(args);
		const { data } = await attachFile(record.doctype, record.docname, file, fields, options);
		keep(data);
		const row = data.attachments.find((one) => one.name === data.file);
		if (!row) throw new Error("The upload finished, but the server named no file.");
		return { file_url: row.file_url, name: row.name };
	};
}

/** The server's rows and a script's, oldest first; a script row that reuses a File name is dropped. */
export function filesInTimeOrder(server: FileRow[], own: FeedItem[]): FilesListRow[] {
	const taken = new Set(server.map((row) => row.name));
	const rows = [...server, ...own.filter((item) => !taken.has(item.name))];
	return rows.sort(byTime);
}

/** As `page.files.items` orders them: the time's text, then the name. */
export function byTime(a: FileRow | FeedItem, b: FileRow | FeedItem) {
	return compareActivities(timed(a), timed(b));
}

export function isScriptRow(row: FilesListRow): row is FeedItem {
	return "component" in row && Boolean(row.component);
}

export function isImage(row: FileRow) {
	return /\.(png|jpe?g|gif|webp|svg|bmp|avif)$/i.test(row.file_name || row.file_url);
}

function uploadFields(args: UploadArgs): UploadFields {
	return {
		is_private: args.isPrivate ? 1 : 0,
		folder: args.folder || "Home/Attachments",
		optimize: args.optimize ? 1 : undefined,
		max_width: args.optimize ? args.maxWidth : undefined,
		max_height: args.optimize ? args.maxHeight : undefined,
	};
}

function timed(row: FilesListRow) {
	return { timestamp: "timestamp" in row ? row.timestamp : row.creation, key: row.name };
}
