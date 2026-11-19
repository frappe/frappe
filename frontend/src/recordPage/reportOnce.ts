// One set for every reporter: a Submit that joined a header Save's failure is the same failure.
const reported = new WeakMap<object, unknown>();

/** Callers that joined one running act all reject with the same error; it is reported once, and a later caller gets the first report's result. */
export function reportOnce<Result>(report: (error: unknown) => Result): (error: unknown) => Result {
  return (error) => {
    if (typeof error !== "object" || !error) return report(error);
    if (reported.has(error)) return reported.get(error) as Result;
    const result = report(error);
    reported.set(error, result);
    return result;
  };
}
