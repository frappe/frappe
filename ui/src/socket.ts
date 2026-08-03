import { getCurrentInstance, inject } from "vue";

interface RealtimeSocket {
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
        "provide('socket'|'$socket', …) or a $socket global."
    );
  }

  return socket;
}
