export function errorMessage(exception: unknown): string {
  const error = exception as { messages?: string[]; message?: string };
  return error?.messages?.[0] || error?.message || String(exception);
}
