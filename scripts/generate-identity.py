"""Build the Loop Lab dividers and responsive signature panels.
Requires Python 3 + fonttools; font and license are local.
"""
from pathlib import Path
import html
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen

ROOT = Path(__file__).resolve().parents[1]
FONT = instantiateVariableFont(TTFont(ROOT / 'assets/fonts/SpaceGrotesk-wght.ttf'), {'wght': 600}, inplace=False)
GLYPHS, CMAP, UNITS = FONT.getGlyphSet(), FONT.getBestCmap(), FONT['head'].unitsPerEm
PALETTES = {
    'dark': dict(bg='#130a24', panel='#281343', border='#493064', ink='#c2acd8', accent='#c9a3ff'),
    'light': dict(bg='#f9f4ff', panel='#eee0ff', border='#d7c3ef', ink='#70598d', accent='#713cc0'),
}


def lettering(label, x, baseline, size, fill, tracking=0):
    scale = size / UNITS
    paths = []
    for char in label:
        glyph = GLYPHS[CMAP.get(ord(char), '.notdef')]
        pen = SVGPathPen(GLYPHS)
        glyph.draw(pen)
        if pen.getCommands():
            paths.append(f'<path d="{pen.getCommands()}" transform="translate({x:.3f} {baseline:.3f}) scale({scale:.7f} {-scale:.7f})"/>')
        x += glyph.width * scale + tracking
    return f'<g fill="{fill}">' + ''.join(paths) + '</g>'


def start(width, height, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{html.escape(title)}</title>']


def ornaments(theme):
    p = PALETTES[theme]
    svg = start(960, 36, 'Loop Lab divider')
    svg += [
        f'<defs><linearGradient id="line"><stop stop-color="{p["accent"]}" stop-opacity="0"/><stop offset=".5" stop-color="{p["accent"]}" stop-opacity=".65"/><stop offset="1" stop-color="{p["accent"]}" stop-opacity="0"/></linearGradient></defs>',
        '<path d="M32 18h400m96 0h400" fill="none" stroke="url(#line)"/>',
        f'<path d="m473 18 7-7 7 7-7 7-7-7Z" fill="{p["accent"]}" fill-opacity=".12" stroke="{p["accent"]}" stroke-opacity=".7"/>',
        f'<circle cx="452" cy="18" r="1.5" fill="{p["accent"]}"/><circle cx="508" cy="18" r="1.5" fill="{p["accent"]}"/>',
        '</svg>',
    ]
    (ROOT / f'assets/divider-{theme}.svg').write_text('\n'.join(svg) + '\n', encoding='utf-8', newline='\n')
    for mobile in (False, True):
        width, height = (480, 88) if mobile else (960, 88)
        svg = start(width, height, 'Make. Refine. Repeat.')
        svg += [
            f'<defs><linearGradient id="surface"><stop stop-color="{p["panel"]}"/><stop offset=".5" stop-color="{p["bg"]}"/><stop offset="1" stop-color="{p["panel"]}"/></linearGradient></defs>',
            f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="16" fill="url(#surface)" stroke="{p["border"]}"/>',
            f'<path d="m{width/2-165:g} 44 4-4 4 4-4 4-4-4Z" fill="none" stroke="{p["accent"]}"/>',
            lettering('MAKE. REFINE. REPEAT.', width/2-138, 51, 22, p['ink'], 1.05),
            f'<path d="M24 32v-8h8m{width-56} 40h8v-8" stroke="{p["accent"]}" stroke-opacity=".4" fill="none"/>',
            '</svg>',
        ]
        suffix = 'mobile-' if mobile else ''
        (ROOT / f'assets/footer-{suffix}{theme}.svg').write_text('\n'.join(svg) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    for theme in PALETTES:
        ornaments(theme)
    print('Generated six Loop Lab ornaments with outlined Space Grotesk typography.')
