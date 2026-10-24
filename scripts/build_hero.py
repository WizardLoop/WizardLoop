#!/usr/bin/env python3
"""Build self-contained Loop Lab banners. Install fonttools to regenerate."""
from pathlib import Path
from base64 import b64encode
from html import escape
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets/fonts/SpaceGrotesk-wght.ttf"
ART = ROOT / "assets/loop-lab-art.png"
fonts = {}
def lettering(text, x, y, size, color, weight=500, spacing=0):
    if weight not in fonts:
        fonts[weight] = instantiateVariableFont(TTFont(FONT), {"wght": weight}, inplace=False)
    font = fonts[weight]
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    pieces = []
    for char in text:
        name = cmap.get(ord(char), ".notdef")
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        path = pen.getCommands()
        if path:
            pieces.append(f'<path d="{path}" transform="translate({x:.3f} {y:.3f}) scale({scale:.7f} {-scale:.7f})"/>')
        x += glyphs[name].width * scale + spacing
    return f'<g fill="{color}" aria-label="{escape(text)}">' + "".join(pieces) + "</g>"

art = b64encode(ART.read_bytes()).decode()
for theme in ("dark", "light"):
    dark = theme == "dark"
    bg, panel, border = ("#0d1117", "#12111e", "#302b43") if dark else ("#ffffff", "#f6f3fc", "#e4ddee")
    fg, accent, muted, mint = ("#eeeffa", "#b899ff", "#bbb4cb", "#9cd9c6") if dark else ("#242133", "#7145ad", "#625871", "#327b68")
    for mobile in (False, True):
        w, h = (480, 584) if mobile else (1200, 464)
        a = []
        a.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="hero-title hero-desc">')
        a.append('<title id="hero-title">WizardLoop — Loop Lab</title><desc id="hero-desc">Software, bots, and open source. Turning ideas into useful tools, with code, design, and motion. An original amethyst crystal connects a terminal, a bot, and an animation keyframe.</desc>')
        a.append(f'<defs><radialGradient id="glow"><stop stop-color="{accent}" stop-opacity="{".13" if dark else ".10"}"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient><linearGradient id="rule"><stop stop-color="{accent}" stop-opacity=".8"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{accent}" stroke-opacity=".08" stroke-width=".6"/></pattern></defs>')
        a.append('<style>.signal{animation:pulse 2.6s ease-in-out 1}@keyframes pulse{0%,100%{opacity:.5}50%{opacity:1}}@media(prefers-reduced-motion:reduce){.signal{animation:none}}</style>')
        a.append(f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="18" fill="{bg}" stroke="{border}"/>')
        if mobile:
            a.append(f'<ellipse cx="258" cy="350" rx="280" ry="235" fill="url(#glow)"/>')
            a.append(f'<rect x="30" y="244" width="420" height="240" fill="url(#grid)"/>')
            a.append(lettering("SOFTWARE / BOTS / OPEN SOURCE",28,40,11,accent,600,1.5))
            a.append(lettering("WizardLoop",26,117,61,fg,700,-1.6))
            a.append(lettering("Turning ideas into useful tools.",28,161,20,fg,500,-.3))
            a.append(lettering("A little magic in every loop.",28,192,19,muted,400,-.15))
            a.append(f'<g class="art"><image x="15" y="203" width="450" height="338" href="data:image/png;base64,{art}"/></g>')
            a.append(f'<path d="M28 535H452" stroke="url(#rule)"/>')
            a.append(lettering("idea  /  code  /  motion  /  repeat",28,560,14,mint,500,.2))
        else:
            a.append(f'<ellipse cx="920" cy="210" rx="360" ry="310" fill="url(#glow)"/>')
            a.append(f'<rect x="700" y="24" width="460" height="392" fill="url(#grid)"/>')
            a.append(lettering("SOFTWARE / BOTS / OPEN SOURCE",52,60,14,accent,600,2.1))
            a.append(lettering("WizardLoop",48,184,96,fg,700,-3))
            a.append(lettering("Turning ideas into useful tools.",52,243,29,fg,500,-.5))
            a.append(lettering("A little magic in every loop.",52,284,26,muted,400,-.3))
            a.append(f'<g class="art"><image x="638" y="18" width="546" height="410" href="data:image/png;base64,{art}"/></g>')
            a.append(f'<path d="M52 352H575" stroke="url(#rule)"/>')
            a.append(lettering("idea  /  code  /  motion  /  repeat",52,390,18,mint,500,.7))
            a.append(lettering("DEVELOPMENT + DESIGN + ANIMATION",52,430,11,muted,500,1.5))
        a.append(f'<circle class="signal" cx="{w-30}" cy="30" r="3" fill="{mint}" opacity=".5"/>')
        a.append("</svg>")
        filename = f'hero-{"mobile-" if mobile else ""}{theme}.svg'
        (ROOT / "assets" / filename).write_text("".join(a), encoding="utf-8")
        print(filename)

