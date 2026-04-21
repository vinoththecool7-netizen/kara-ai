export type ToastVariant = "success" | "error" | "info";

export interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  /** Milliseconds before auto-dismiss. 0 disables auto-dismiss. */
  duration: number;
}

type Listener = (toasts: readonly Toast[]) => void;

const DEFAULT_DURATION = 4000;
const ERROR_DURATION = 6000;

let toasts: Toast[] = [];
const listeners = new Set<Listener>();
let idCounter = 0;

function notify(): void {
  const snapshot = toasts;
  for (const l of listeners) l(snapshot);
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  listener(toasts);
  return () => {
    listeners.delete(listener);
  };
}

export function getToasts(): readonly Toast[] {
  return toasts;
}

export function push(input: Omit<Toast, "id">): string {
  const id = String(++idCounter);
  toasts = [...toasts, { ...input, id }];
  notify();
  return id;
}

export function dismiss(id: string): void {
  const next = toasts.filter((t) => t.id !== id);
  if (next.length === toasts.length) return;
  toasts = next;
  notify();
}

export function clear(): void {
  toasts = [];
  idCounter = 0;
  notify();
}

function pushWithTimer(input: Omit<Toast, "id">): string {
  const id = push(input);
  if (input.duration > 0 && typeof window !== "undefined") {
    window.setTimeout(() => dismiss(id), input.duration);
  }
  return id;
}

export const toast = {
  success(title: string, description?: string): string {
    return pushWithTimer({ variant: "success", title, description, duration: DEFAULT_DURATION });
  },
  error(title: string, description?: string): string {
    return pushWithTimer({ variant: "error", title, description, duration: ERROR_DURATION });
  },
  info(title: string, description?: string): string {
    return pushWithTimer({ variant: "info", title, description, duration: DEFAULT_DURATION });
  },
};
