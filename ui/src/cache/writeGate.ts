// Orders replies by the time their request was sent, per document.
// A ticket is taken at send time; the counter never restarts, so a sealed document stays sealed.

export class WriteGate {
  private counter = 0;
  private floor = 0;
  private applied = new Map<string, number>();
  private sealed = new Set<string>();

  next(): number {
    return ++this.counter;
  }

  /** False for a request sent before the last clear. */
  current(ticket: number): boolean {
    return ticket > this.floor;
  }

  /** A read records nothing: a later read may land before an earlier save commits. */
  admitRead(key: string, ticket: number): boolean {
    return this.current(ticket) && ticket >= (this.applied.get(key) ?? 0);
  }

  admitWrite(key: string, ticket: number): boolean {
    if (!this.admitRead(key, ticket)) return false;
    this.applied.set(key, ticket);
    this.sealed.delete(key);
    return true;
  }

  /** A fresh number: a request still in flight when the delete settles was answered before it. */
  seal(key: string): void {
    this.applied.set(key, ++this.counter);
    this.sealed.add(key);
  }

  isSealed(key: string): boolean {
    return this.sealed.has(key);
  }

  clear(): void {
    this.floor = this.counter;
    this.applied.clear();
    this.sealed.clear();
  }
}
