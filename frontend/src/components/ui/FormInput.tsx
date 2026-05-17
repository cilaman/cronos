import { cn } from "../../utils/cn";

const BASE =
  "mt-1 block w-full rounded border border-hairline-strong bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-60";

export function FormInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(BASE, props.className)} />;
}

export function FormTextarea(
  props: React.TextareaHTMLAttributes<HTMLTextAreaElement>,
) {
  return <textarea {...props} className={cn(BASE, props.className)} />;
}

export function FormSelect(
  props: React.SelectHTMLAttributes<HTMLSelectElement>,
) {
  return <select {...props} className={cn(BASE, props.className)} />;
}
