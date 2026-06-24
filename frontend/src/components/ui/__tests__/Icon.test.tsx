import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Star } from 'lucide-react';
import { Icon } from '../Icon';

/**
 * Helpers — get the rendered SVG element from a rendered Icon.
 * lucide-react renders an <svg> as its root element.
 */
function getSvg(container: HTMLElement): SVGSVGElement {
  const svg = container.querySelector('svg');
  if (!svg) throw new Error('No <svg> found in rendered Icon');
  return svg as SVGSVGElement;
}


describe('Icon component', () => {
  describe('size variants', () => {
    it('renders sm size with width=14, height=14, strokeWidth=1.5', () => {
      const { container } = render(<Icon icon={Star} size="sm" />);
      const svg = getSvg(container);
      expect(svg.getAttribute('width')).toBe('14');
      expect(svg.getAttribute('height')).toBe('14');
      expect(svg.getAttribute('stroke-width')).toBe('1.5');
    });

    it('renders md size with width=16, height=16, strokeWidth=1.5', () => {
      const { container } = render(<Icon icon={Star} size="md" />);
      const svg = getSvg(container);
      expect(svg.getAttribute('width')).toBe('16');
      expect(svg.getAttribute('height')).toBe('16');
      expect(svg.getAttribute('stroke-width')).toBe('1.5');
    });

    it('renders lg size with width=20, height=20, strokeWidth=1.75', () => {
      const { container } = render(<Icon icon={Star} size="lg" />);
      const svg = getSvg(container);
      expect(svg.getAttribute('width')).toBe('20');
      expect(svg.getAttribute('height')).toBe('20');
      expect(svg.getAttribute('stroke-width')).toBe('1.75');
    });
  });

  describe('default size', () => {
    it('defaults to md (16px, strokeWidth=1.5) when size prop is omitted', () => {
      const { container } = render(<Icon icon={Star} />);
      const svg = getSvg(container);
      expect(svg.getAttribute('width')).toBe('16');
      expect(svg.getAttribute('height')).toBe('16');
      expect(svg.getAttribute('stroke-width')).toBe('1.5');
    });
  });

  describe('accessibility', () => {
    it('always sets aria-hidden="true"', () => {
      const { container } = render(<Icon icon={Star} />);
      const svg = getSvg(container);
      expect(svg.getAttribute('aria-hidden')).toBe('true');
    });

    it('forces stroke="currentColor"', () => {
      const { container } = render(<Icon icon={Star} />);
      const svg = getSvg(container);
      expect(svg.getAttribute('stroke')).toBe('currentColor');
    });
  });

  describe('className passthrough', () => {
    it('passes className to the underlying SVG element', () => {
      const { container } = render(<Icon icon={Star} className="text-primary w-full" />);
      const svg = getSvg(container);
      expect(svg.classList.contains('text-primary')).toBe(true);
      expect(svg.classList.contains('w-full')).toBe(true);
    });

    it('renders with lucide default class when className is omitted', () => {
      // lucide-react always merges "lucide lucide-{name}" into the class attribute;
      // when no className is passed to Icon, the SVG still carries the lucide classes.
      // This is expected behaviour from the library — Icon does not strip them.
      const { container } = render(<Icon icon={Star} />);
      const svg = getSvg(container);
      expect(svg.classList.contains('lucide')).toBe(true);
    });
  });

  describe('no duplicate attributes', () => {
    /**
     * Verifies that the SVG element has exactly one each of:
     *   - width (not to be confused with stroke-width)
     *   - height
     *   - stroke-width
     *
     * Strategy: use the DOM API on the SVG element's attributes collection
     * rather than string-matching the innerHTML, to avoid regex false-positives
     * (e.g. "stroke-width=" matching a "\bwidth=" pattern).
     */
    function checkNoDuplicateAttrs(container: HTMLElement) {
      const svg = getSvg(container);
      const attrs = Array.from(svg.attributes).map((a) => a.name);
      const widthCount = attrs.filter((a) => a === 'width').length;
      const heightCount = attrs.filter((a) => a === 'height').length;
      const strokeWidthCount = attrs.filter((a) => a === 'stroke-width').length;
      expect(widthCount).toBe(1);
      expect(heightCount).toBe(1);
      expect(strokeWidthCount).toBe(1);
    }

    it('sm: has exactly one width, one height, one stroke-width attribute on the SVG element', () => {
      const { container } = render(<Icon icon={Star} size="sm" />);
      checkNoDuplicateAttrs(container);
    });

    it('md: has exactly one width, one height, one stroke-width attribute on the SVG element', () => {
      const { container } = render(<Icon icon={Star} size="md" />);
      checkNoDuplicateAttrs(container);
    });

    it('lg: has exactly one width, one height, one stroke-width attribute on the SVG element', () => {
      const { container } = render(<Icon icon={Star} size="lg" />);
      checkNoDuplicateAttrs(container);
    });
  });
});
