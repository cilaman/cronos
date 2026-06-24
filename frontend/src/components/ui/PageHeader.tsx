import { Link } from "react-router-dom";
import { cn } from "../../utils/cn";

/**
 * PageHeader — unified page title / breadcrumb / actions bar.
 *
 * Props:
 *   breadcrumbs — optional [{label, href?}] rendered as <nav><ol>
 *   title       — required; rendered as <h1 className="text-title">
 *   subtitle    — optional ReactNode below the h1 (description, meta)
 *   actions     — optional ReactNode[]. Up to 3 rendered inline in flex
 *                 row; for 4+ the first 2 appear inline then the rest
 *                 are revealed via a native <details>/<summary> "More"
 *                 disclosure (keyboard-accessible, ESC-closable via blur).
 *                 Design decision documented in R4 mitigation (design
 *                 report risks[4]). No in-scope page currently has 4+
 *                 actions; this path is implemented for spec compliance.
 *   sticky      — optional boolean; when true applies `sticky top-0 z-30`
 *                 plus backdrop-blur. z-30 > StickyToolbar's z-20. Do NOT
 *                 set sticky=true on any page that retains StickyToolbar
 *                 (z-index collision — medium risk, design report risks[3]).
 *   className   — merged via cn()
 */
interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface Props {
  breadcrumbs?: BreadcrumbItem[];
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode[];
  sticky?: boolean;
  className?: string;
}

export function PageHeader({
  breadcrumbs,
  title,
  subtitle,
  actions,
  sticky = false,
  className,
}: Props) {
  const inlineActions = actions && actions.length > 3 ? actions.slice(0, 2) : actions;
  const overflowActions = actions && actions.length > 3 ? actions.slice(2) : [];

  return (
    <header
      className={cn(
        "flex flex-col gap-1 border-b border-hairline bg-canvas pb-4 sm:flex-row sm:items-start sm:justify-between",
        sticky && "sticky top-0 z-30 backdrop-blur",
        className,
      )}
    >
      {/* Left column: breadcrumbs, title, subtitle */}
      <div className="flex flex-col gap-1">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav aria-label="Breadcrumb">
            <ol className="flex items-center gap-1 text-[11px] text-ink-faint">
              {breadcrumbs.map((crumb, i) => (
                <li key={i} className="flex items-center gap-1">
                  {i > 0 && <span aria-hidden>/</span>}
                  {crumb.href ? (
                    <Link
                      to={crumb.href}
                      className="hover:text-ink transition-colors"
                    >
                      {crumb.label}
                    </Link>
                  ) : (
                    <span>{crumb.label}</span>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        )}

        <h1 className="text-title">{title}</h1>

        {subtitle && (
          <div className="text-sm text-ink-muted">{subtitle}</div>
        )}
      </div>

      {/* Right column: actions */}
      {actions && actions.length > 0 && (
        <div className="mt-2 flex shrink-0 items-center gap-2 sm:mt-0">
          {inlineActions?.map((action, i) => (
            <span key={i}>{action}</span>
          ))}
          {overflowActions.length > 0 && (
            <details className="relative">
              <summary className="cursor-pointer list-none rounded px-2 py-1 text-sm text-ink-muted hover:bg-surface-2">
                More
              </summary>
              <div className="absolute right-0 top-full z-40 mt-1 flex flex-col gap-1 rounded border border-hairline bg-surface-1 p-1 shadow-md">
                {overflowActions.map((action, i) => (
                  <span key={i} className="px-1">
                    {action}
                  </span>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </header>
  );
}
