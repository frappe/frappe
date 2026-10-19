import fs from "fs";
import path from "path";

export async function drop_file(target, file_path, mime_type) {
	const data_transfer = await target.page().evaluateHandle(
		([content, name, type]) => {
			const data_transfer = new DataTransfer();
			const bytes = Uint8Array.from(atob(content), (char) => char.charCodeAt(0));
			data_transfer.items.add(new File([bytes], name, { type }));
			return data_transfer;
		},
		[fs.readFileSync(file_path).toString("base64"), path.basename(file_path), mime_type]
	);
	await target.dispatchEvent("drop", { dataTransfer: data_transfer });
}
