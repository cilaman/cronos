interface Props {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  /**
   * Primary call-to-action for the empty state. Renders a styled button
   * below the description. Pass `children` instead when you need more than
   * one action or a custom element.
   */
  action?: { label: string; onClick: () => void };
  children?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action, children }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      {icon && (
        <span className="text-4xl opacity-30" aria-hidden>
          {icon}
        </span>
      )}
      <p className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
        {title}
      </p>
      {description && (
        <p className="max-w-xs text-xs text-ink-faint">{description}</p>
      )}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-1 inline-flex h-9 items-center rounded border border-accent bg-accent px-4 text-[12px] font-medium text-canvas transition hover:bg-accent-bright"
        >
          {action.label}
        </button>
      )}
      {children}
    </div>
  );
}
