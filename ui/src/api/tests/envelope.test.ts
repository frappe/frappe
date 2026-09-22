import { describe, expect, it } from "vitest";
import { ApiError, isApiError, readEnvelope, TIMESTAMP_MISMATCH } from "../envelope";

describe("readEnvelope", () => {
  it("returns the body, data and the keys beside it", () => {
    const body = { data: { name: "T-1" }, permissions: { read: 1 }, has_next_page: true };
    expect(readEnvelope(body, 200)).toBe(body);
  });

  it("throws the first entry of errors as an ApiError", () => {
    const body = {
      errors: [
        { type: TIMESTAMP_MISMATCH, message: "Error: Document has been modified", title: "Conflict" },
        { type: "ValidationError" },
      ],
    };
    let thrown: unknown;
    try {
      readEnvelope(body, 409);
    } catch (error) {
      thrown = error;
    }
    expect(isApiError(thrown)).toBe(true);
    const error = thrown as ApiError;
    expect(error.type).toBe(TIMESTAMP_MISMATCH);
    expect(error.isTimestampMismatch).toBe(true);
    expect(error.message).toBe("Error: Document has been modified");
    expect(error.title).toBe("Conflict");
    expect(error.status).toBe(409);
  });

  it("names the error by its type when the server sent no message", () => {
    expect(() => readEnvelope({ errors: [{ type: "PermissionError" }] }, 403)).toThrow(
      "PermissionError"
    );
  });

  it("treats an empty errors list as success", () => {
    expect(readEnvelope({ data: 1, errors: [] }, 200).data).toBe(1);
  });

  it("throws an HTTPError for a failed status with no errors list", () => {
    expect(() => readEnvelope(null, 502)).toThrow(
      expect.objectContaining({ type: "HTTPError", status: 502 })
    );
  });

  it("throws when a 200 body is not a JSON object", () => {
    expect(() => readEnvelope([1], 200)).toThrow(
      expect.objectContaining({ type: "InvalidResponse" })
    );
    expect(() => readEnvelope(null, 200)).toThrow(
      expect.objectContaining({ type: "InvalidResponse" })
    );
  });

  it("throws a MissingData error for a 200 body with no data key", () => {
    expect(() => readEnvelope({ permissions: { read: 1 } }, 200)).toThrow(
      expect.objectContaining({ type: "MissingData", status: 200 })
    );
  });

  it("fills a null data for a nullable route and keeps the keys beside it", () => {
    const envelope = readEnvelope({ docs: [] }, 200, { nullable: true });
    expect(envelope).toEqual({ docs: [], data: null });
  });

  it("names the request in the errors it makes itself", () => {
    const source = "GET /document/ToDo/T-1";
    expect(() => readEnvelope({}, 200, { source })).toThrow(`${source} answered 200 with no data`);
    expect(() => readEnvelope(null, 502, { source })).toThrow(`${source} failed with status 502`);
    expect(() => readEnvelope("x", 200, { source })).toThrow(
      `${source} did not answer with a JSON object`
    );
  });
});
