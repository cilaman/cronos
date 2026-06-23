import { LucideIcon } from 'lucide-react';

export type IconSize = 'sm' | 'md' | 'lg';

const SIZE_PX: Record<IconSize, number> = {
  sm: 14,
  md: 16,
  lg: 20,
};

const STROKE_WIDTH: Record<IconSize, number> = {
  sm: 1.5,
  md: 1.5,
  lg: 1.75,
};

export interface IconProps {
  icon: LucideIcon;
  size?: IconSize;
  className?: string;
}

/**
 * Icon — thin wrapper around a LucideIcon component.
 *
 * Props are resolved explicitly into a single known-safe object so that the
 * underlying SVG never receives duplicate width/height/stroke-width attributes.
 * lucide-react's `size` prop sets both width and height; passing `width`/`height`
 * separately alongside `size` would produce duplicate DOM attributes. We therefore
 * always pass `size` and let lucide emit a single width= and height= on the SVG.
 *
 * All icons are rendered with aria-hidden="true" and stroke="currentColor".
 */
export function Icon({ icon: LucideComponent, size = 'md', className }: IconProps) {
  const px = SIZE_PX[size];
  const strokeWidth = STROKE_WIDTH[size];

  // Build an explicit resolved-props object — no naive `{...props}` spread.
  // `size` drives both width and height via lucide's own mapping, preventing
  // duplicate width= / height= attributes on the SVG element.
  const resolvedProps = {
    size: px,
    strokeWidth,
    color: 'currentColor',
    'aria-hidden': 'true' as const,
    ...(className !== undefined ? { className } : {}),
  };

  return <LucideComponent {...resolvedProps} />;
}

export default Icon;
