/** One entry of the `errors` list a v2 response carries when a request failed. */
export interface ErrorEntry {
  type: string;
  message?: string;
  title?: string;
  exception?: string;
  indicator?: string;
}

/** A v2 response body: `data`, plus what the route adds beside it (`has_next_page`, `include` parts). */
export type Envelope<T> = { data: T } & Record<string, unknown>;

export const TIMESTAMP_MISMATCH = "TimestampMismatchError";

/** The first entry of a failed response's `errors` list, as a throwable. */
export class ApiError extends Error {
  readonly type: string;
  readonly title?: string;
  readonly exception?: string;
  readonly indicator?: string;
  readonly status: number;

  constructor(entry: ErrorEntry, status: number) {
    super(entry.message || entry.type);
    this.name = "ApiError";
    this.type = entry.type;
    this.title = entry.title;
    this.exception = entry.exception;
    this.indicator = entry.indicator;
    this.status = status;
  }

  get isTimestampMismatch(): boolean {
    return this.type === TIMESTAMP_MISMATCH;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export interface ReadOptions {
  /** `METHOD /path`, named in the message of an error the wrapper makes itself. */
  source?: string;
  /** The route hands back what a function returned, so a body with no `data` is a `null`. */
  nullable?: boolean;
}

/** Turn a parsed response body into an envelope, or throw its first error. */
export function readEnvelope<T>(
  body: unknown,
  status: number,
  { source, nullable = false }: ReadOptions = {}
): Envelope<T> {
  const errors = (body as { errors?: unknown } | null)?.errors;
  if (Array.isArray(errors) && errors.length) {
    throw new ApiError(errors[0] as ErrorEntry, status);
  }
  const where = source ?? "The request";
  if (status >= 400) {
    throw new ApiError(
      { type: "HTTPError", message: `${where} failed with status ${status}` },
      status
    );
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new ApiError(
      { type: "InvalidResponse", message: `${where} did not answer with a JSON object` },
      status
    );
  }
  if (!("data" in body)) {
    if (!nullable) {
      throw new ApiError(
        { type: "MissingData", message: `${where} answered ${status} with no data` },
        status
      );
    }
    return { ...body, data: null } as Envelope<T>;
  }
  return body as Envelope<T>;
}
