interface Props {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  children?: React.ReactNode;
}

export function EmptyState({ icon, title, description, children }: Props) {
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
      {children}
    </div>
  );
}
