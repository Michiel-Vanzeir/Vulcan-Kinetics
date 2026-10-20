// whoknows mark: a text cursor, two white "typing" dots, and a yellow person (the colleague who knows).
// Built with DOM APIs instead of innerHTML so it also works on Trusted Types pages like Gmail.

const SVG_NS = 'http://www.w3.org/2000/svg';

const SHAPES: [string, Record<string, string>][] = [
  ['rect', { width: '64', height: '64', rx: '14', fill: '#1B2A4E' }],
  ['rect', { x: '11', y: '16', width: '4.5', height: '32', rx: '2.25', fill: '#FFFFFF' }],
  ['circle', { cx: '25', cy: '40', r: '4', fill: '#FFFFFF' }],
  ['circle', { cx: '37', cy: '40', r: '4', fill: '#FFFFFF' }],
  ['circle', { cx: '51', cy: '30', r: '5', fill: '#FFD23F' }],
  ['path', { d: 'M42 46.5a9 9 0 0 1 18 0z', fill: '#FFD23F' }],
];

export function createLogo(): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 64 64');
  svg.setAttribute('aria-hidden', 'true');
  for (const [tag, attrs] of SHAPES) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    svg.append(el);
  }
  return svg;
}
