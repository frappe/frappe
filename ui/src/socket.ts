import { getCurrentInstance, inject } from "vue";

export interface RealtimeSocket {
  emit(event: string, ...args: unknown[]): void;
  on(event: string, handler: (...args: unknown[]) => void): void;
  off(event: string, handler: (...args: unknown[]) => void): void;
}

// Try to get the socket from various sources: injected properties or global properties like $socket or socket.
// Assumes global socket is present via
// provide('socket', …) or provide('$socket', …) in the app root, or via app.config.globalProperties.$socket/socket.
export function getSocketInstance(): RealtimeSocket | undefined {
  const instance = getCurrentInstance();
  if (!instance) {
    throw new Error("getSocketInstance() must be called during setup().");
  }

  const globals = instance.appContext.config.globalProperties;
  const socket =
    inject<RealtimeSocket | undefined>("socket", undefined) ??
    inject<RealtimeSocket | undefined>("$socket", undefined) ??
    (globals.socket as RealtimeSocket | undefined) ??
    (globals.$socket as RealtimeSocket | undefined);

  if (!socket && import.meta.env?.DEV) {
    console.warn(
      "getSocketInstance: no socket found. Expose one via " +
        "provide('socket'|'$socket', …) or a $socket global.",
    );
  }

  return socket;
}

// The server's `doc_unsubscribe` is a bare `socket.leave` (realtime/handlers.js), so one
// consumer leaving a room silently deafens every other consumer on the same document.
interface DocRoom {
  doctype: string;
  docname: string;
  holders: number;
}

const rooms = new Map<string, DocRoom>();

/**
 * Joins a document's realtime room, and leaves only when the last holder releases it.
 */
export function subscribeToDoc(
  socket: RealtimeSocket | undefined,
  doctype: string,
  docname: string,
): () => void {
  if (!socket) return () => {};

  // Doctypes and docnames both allow spaces, so a delimited key is ambiguous.
  const key = JSON.stringify([doctype, docname]);
  const room = rooms.get(key) ?? { doctype, docname, holders: 0 };
  if (room.holders === 0) {
    watchReconnect(socket);
    socket.emit("doc_subscribe", doctype, docname);
  }
  room.holders += 1;
  rooms.set(key, room);

  let released = false;
  return () => {
    if (released) return;
    released = true;
    room.holders -= 1;
    if (room.holders > 0) return;
    rooms.delete(key);
    socket.emit("doc_unsubscribe", doctype, docname);
  };
}

// The rooms are this module's, so rejoining them is too: one listener for the table,
// rather than one per consumer each rejoining every room in it. `connect` also fires on
// the first connect, where re-joining a room we are already in costs nothing.
let watchingReconnect = false;
function watchReconnect(socket: RealtimeSocket) {
  if (watchingReconnect) return;
  watchingReconnect = true;
  socket.on("connect", () => resubscribeHeldDocs(socket));
}

/** Rejoins every held room, for a reconnect that dropped the server's membership. */
export function resubscribeHeldDocs(socket: RealtimeSocket | undefined) {
  if (!socket) return;
  for (const room of rooms.values())
    socket.emit("doc_subscribe", room.doctype, room.docname);
}
