import { provide } from "vue";
import { UploadTransportKey } from "@framework/ui/FileUpload";
import { CreateRecordKey } from "@framework/ui/fields/types";
import { CommitKey, NO_COMMIT } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";

/** Preview never writes: its fields commit nothing, uploads fail, and Link fields offer no Create. */
export function refuseWrites() {
	provide(CommitKey, NO_COMMIT);
	provide(UploadTransportKey, async () => {
		throw new Error(__("Preview does not upload files."));
	});
	provide(CreateRecordKey, null);
}
