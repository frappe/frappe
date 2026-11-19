import type { ActSchema } from "../schema/checkValue";

/** What an agent reads about an act: kept out of the page bundle, in one sidecar module per surface. */
export interface ActText {
	description: string;
	input?: ActSchema;
	output?: ActSchema;
}
