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
    bg, panel, border = ("#130a24", "#281343", "#5b377a") if dark else ("#f9f4ff", "#eee0ff", "#cfb5e9")
    fg, accent, muted, mint = ("#f6efff", "#c9a3ff", "#c2acd8", "#c4acff") if dark else ("#34194f", "#713cc0", "#70598d", "#8952ce")
    for mobile in (False, True):
        w, h = (480, 584) if mobile else (1200, 464)
        a = []
        a.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="hero-title hero-desc">')
        a.append('<title id="hero-title">WizardLoop — Loop Lab</title><desc id="hero-desc">Software, bots, and open source. Turning ideas into useful tools, with code, design, and motion. An original amethyst crystal connects a terminal, a bot, and an animation keyframe.</desc>')
        a.append(f'<defs><linearGradient id="surface" x2="1" y2="1"><stop stop-color="{panel}"/><stop offset=".57" stop-color="{bg}"/><stop offset="1" stop-color="{panel}"/></linearGradient><linearGradient id="wordmark" x1="0" y1="0" x2="0.8" y2="1"><stop stop-color="{"#ffffff" if dark else "#301244"}"/><stop offset=".55" stop-color="{"#f3e7ff" if dark else "#573083"}"/><stop offset="1" stop-color="{"#b68aef" if dark else "#8753c3"}"/></linearGradient><radialGradient id="glow"><stop stop-color="{"#a05cff" if dark else "#b57aef"}" stop-opacity="{".34" if dark else ".23"}"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient><linearGradient id="rule"><stop stop-color="{accent}" stop-opacity=".68"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient><linearGradient id="rim"><stop stop-color="{accent}" stop-opacity=".12"/><stop offset=".52" stop-color="{accent}" stop-opacity=".78"/><stop offset="1" stop-color="{accent}" stop-opacity=".12"/></linearGradient><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{accent}" stroke-opacity=".075" stroke-width=".6"/></pattern><clipPath id="frame"><rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="22"/></clipPath></defs>')
        a.append('<style>.signal{animation:pulse 2.6s ease-in-out 1}@keyframes pulse{0%,100%{opacity:.45}50%{opacity:.95}}@media(prefers-reduced-motion:reduce){.signal{animation:none}}</style>')
        a.append(f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="22" fill="url(#surface)" stroke="{border}"/>')
        a.append('<g clip-path="url(#frame)">')
        a.append(f'<path d="M24 1H{w-24}" stroke="url(#rim)"/>')
        if mobile:
            a.append(f'<ellipse cx="258" cy="350" rx="280" ry="235" fill="url(#glow)"/>')
            a.append(f'<rect x="30" y="244" width="420" height="240" fill="url(#grid)"/>')
            a.append(lettering("SOFTWARE / BOTS / OPEN SOURCE",28,40,11,accent,600,1.5))
            a.append(lettering("WizardLoop",26,117,61,"url(#wordmark)",700,-1.6))
            a.append(lettering("Turning ideas into useful tools.",28,161,20,fg,500,-.3))
            a.append(lettering("A little magic in every loop.",28,192,19,muted,400,-.15))
            a.append(f'<g class="art"><image x="15" y="203" width="450" height="338" href="data:image/png;base64,{art}"/></g>')
            a.append(f'<path d="M28 535H452" stroke="url(#rule)"/>')
            a.append(lettering("idea  /  code  /  motion  /  repeat",28,560,14,mint,500,.2))
        else:
            a.append(f'<ellipse cx="920" cy="210" rx="360" ry="310" fill="url(#glow)"/>')
            a.append(f'<rect x="700" y="24" width="460" height="392" fill="url(#grid)"/>')
            a.append(lettering("SOFTWARE / BOTS / OPEN SOURCE",52,60,14,accent,600,2.1))
            a.append(lettering("WizardLoop",48,184,96,"url(#wordmark)",700,-3))
            a.append(lettering("Turning ideas into useful tools.",52,243,29,fg,500,-.5))
            a.append(lettering("A little magic in every loop.",52,284,26,muted,400,-.3))
            a.append(f'<g class="art"><image x="638" y="18" width="546" height="410" href="data:image/png;base64,{art}"/></g>')
            a.append(f'<path d="M52 352H575" stroke="url(#rule)"/>')
            a.append(lettering("idea  /  code  /  motion  /  repeat",52,390,18,mint,500,.7))
            a.append(lettering("DEVELOPMENT + DESIGN + ANIMATION",52,430,11,muted,500,1.5))
        a.append(f'<circle class="signal" cx="{w-30}" cy="30" r="3" fill="{mint}" opacity=".5"/>')
        a.append("</g></svg>")
        filename = f'hero-{"mobile-" if mobile else ""}{theme}.svg'
        (ROOT / "assets" / filename).write_text("".join(a), encoding="utf-8")
        print(filename)

