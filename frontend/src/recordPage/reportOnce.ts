/** Callers that joined one running act all reject with the same error; `report` sees that error once. */
export function reportOnce<Result>(report: (error: unknown) => Result): (error: unknown) => Result | undefined {
  const reported = new WeakSet<object>();
  return (error) => {
    if (typeof error === "object" && error) {
      if (reported.has(error)) return undefined;
      reported.add(error);
    }
    return report(error);
  };
}
