import { useContext } from "react";
import { ToastContext } from "./ToastProvider";
import type { ToastContextValue } from "./ToastProvider";

/**
 * Hook to consume the ToastContext.
 *
 * Returns `{ show, dismiss }` from the nearest ToastProvider.
 *
 * IMPORTANT: When called outside a ToastProvider this hook returns no-op
 * functions rather than throwing — this is intentional so that components
 * using toasts can be rendered in tests without wrapping them in a provider.
 */
export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}
