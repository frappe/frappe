// Orders replies by the time their request was sent, per document.
// A ticket is taken at send time; the counter never restarts, so a sealed document stays sealed.

export class WriteGate {
  private counter = 0;
  private applied = new Map<string, number>();

  next(): number {
    return ++this.counter;
  }

  /** A read records nothing: a later read may land before an earlier save commits. */
  admitRead(key: string, ticket: number): boolean {
    return ticket >= (this.applied.get(key) ?? 0);
  }

  admitWrite(key: string, ticket: number): boolean {
    if (!this.admitRead(key, ticket)) return false;
    this.applied.set(key, ticket);
    return true;
  }

  /** A fresh number: a request still in flight when the delete settles was answered before it. */
  seal(key: string): void {
    this.applied.set(key, ++this.counter);
  }

  clear(): void {
    this.applied.clear();
  }
}
