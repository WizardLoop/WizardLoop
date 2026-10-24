"""Rebuild the original Loop Lab vector toolbox and ornaments.
Requires Python 3 + fonttools; fonts and license are local.
"""
from pathlib import Path
import html, sys
ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.tooling').exists(): sys.path.insert(0, str(ROOT / '.tooling'))
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
FONT = instantiateVariableFont(TTFont(ROOT / 'assets/fonts/SpaceGrotesk-wght.ttf'), {'wght':600}, inplace=False)
GLYPHS, CMAP, UNITS = FONT.getGlyphSet(), FONT.getBestCmap(), FONT['head'].unitsPerEm
PALETTES = {
 'dark': dict(bg='#0d1117', tile='#141720', border='#2b2a3b', ink='#e8e5f2', muted='#a29ab6', purple='#b899ff', mint='#9cd9c6'),
 'light': dict(bg='#ffffff', tile='#f8f6fc', border='#e4ddee', ink='#281d3c', muted='#71657f', purple='#7350b4', mint='#367a67')}
ITEMS = [('PHP','code'),('Python','interlock'),('C','chip'),('JavaScript','braces'),('HTML & CSS','layers'),('Shell','terminal'),('Telegram','plane'),('Lottie','motion'),('Docker','blocks'),('SQLite','database'),('Git','branch'),('GitHub','source')]
# Original geometric category symbols, not third-party brand logos.
SYMBOLS = {
 'code':'<path d="m10 8-6 8 6 8m12-16 6 8-6 8m-4-19-4 22"/>',
 'interlock':'<path d="M7 17V9a4 4 0 0 1 4-4h10v10H11m14 0v8a4 4 0 0 1-4 4H11V17h10"/><circle cx="16" cy="9" r="1"/><circle cx="16" cy="23" r="1"/>',
 'chip':'<rect x="7" y="7" width="18" height="18" rx="3"/><path d="M12 3v4m8-4v4m-8 18v4m8-4v4M3 12h4m-4 8h4m18-8h4m-4 8h4M20 12h-5a4 4 0 0 0 0 8h5"/>',
 'braces':'<path d="M11 5H8v8l-3 3 3 3v8h3m10-22h3v8l3 3-3 3v8h-3m-7-7 4-8"/>',
 'layers':'<path d="m16 3 12 7-12 7-12-7 12-7Zm-12 14 12 7 12-7M4 23l12 7 12-7"/>',
 'terminal':'<rect x="3" y="5" width="26" height="22" rx="3"/><path d="m8 12 5 4-5 4m10 0h6"/>',
 'plane':'<path d="m3 14 26-10-8 25-6-11-12-4Zm12 4L29 4"/>',
 'motion':'<path d="M5 25C5 7 27 25 27 7M5 7v18M27 7v18"/><rect x="2" y="22" width="6" height="6" rx="1"/><rect x="24" y="4" width="6" height="6" rx="1"/>',
 'blocks':'<rect x="3" y="13" width="7" height="7" rx="1"/><rect x="12" y="13" width="7" height="7" rx="1"/><rect x="21" y="13" width="7" height="7" rx="1"/><rect x="12" y="4" width="7" height="7" rx="1"/><path d="M3 24h25"/>',
 'database':'<ellipse cx="16" cy="7" rx="11" ry="4"/><path d="M5 7v18c0 5.3 22 5.3 22 0V7M5 16c0 5.3 22 5.3 22 0"/>',
 'branch':'<path d="M8 8v16m0-8h10a6 6 0 0 0 6-6V8"/><circle cx="8" cy="5" r="3"/><circle cx="8" cy="27" r="3"/><circle cx="24" cy="5" r="3"/>',
 'source':'<path d="m10 10-6 6 6 6m12-12 6 6-6 6M13 5h6M13 27h6m-1-17-4 12"/>'}

def text_paths(label,x,baseline,size,fill,tracking=-0.25):
 s=size/UNITS; fragments=[]; cursor=x
 for char in label:
  glyph=GLYPHS[CMAP.get(ord(char),'.notdef')]; pen=SVGPathPen(GLYPHS); glyph.draw(pen); path=pen.getCommands()
  if path: fragments.append(f'<path d="{path}" transform="translate({cursor:.3f} {baseline:.3f}) scale({s:.7f} {-s:.7f})"/>')
  cursor+=glyph.width*s+tracking
 return f'<g fill="{fill}">{"".join(fragments)}</g>'

def start(w,h,title,desc,p):
 return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">',f'<title id="title">{html.escape(title)}</title>',f'<desc id="desc">{html.escape(desc)}</desc>',f'<rect width="{w}" height="{h}" fill="{p["bg"]}"/>']

def toolbox(theme,mobile=False):
 p=PALETTES[theme]; w,h,cols=(480,312,3) if mobile else (960,264,4)
 margin,gap=(2,10) if mobile else (3,16); rows=4 if mobile else 3
 cw=(w-margin*2-gap*(cols-1))/cols; ch=(h-margin*2-gap*(rows-1))/rows
 svg=start(w,h,'The Loop Lab toolbox',', '.join(i[0] for i in ITEMS),p)
 for index,(label,icon) in enumerate(ITEMS):
  row,col=divmod(index,cols); x=margin+col*(cw+gap); y=margin+row*(ch+gap)
  color=p['mint'] if index in (3,6,9) else p['purple']
  svg.append(f'<rect x="{x:g}" y="{y:g}" width="{cw:g}" height="{ch:g}" rx="7" fill="{p["tile"]}" stroke="{p["border"]}"/>')
  if mobile: sz,ix,iy,lx,base,fs=22,x+14,y+10,x+14,y+ch-12,20
  else: sz,ix,iy,lx,base,fs=29,x+22,y+(ch-29)/2,x+67,y+ch/2+8.5,25
  svg.append(f'<g transform="translate({ix:g} {iy:g}) scale({sz/32:g})" fill="none" stroke="{color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{SYMBOLS[icon]}</g>')
  svg.append(text_paths(label,lx,base,fs,p['ink'],-0.45 if mobile else -0.35))
  svg.append(f'<path d="M{x+cw-14:g} {y+10:g}h4v4" stroke="{p["border"]}" stroke-width="1.2" fill="none"/>')
 svg.append('</svg>'); suffix=f'-mobile-{theme}' if mobile else f'-{theme}'
 (ROOT/f'assets/toolbox{suffix}.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')

def ornaments(theme):
 p=PALETTES[theme]; svg=start(960,36,'Loop Lab divider','Decorative technical linework.',p)
 svg += [f'<path d="M2 18h430m96 0h430" fill="none" stroke="{p["border"]}"/>',f'<path d="m472 18 8-8 8 8-8 8-8-8Z" fill="none" stroke="{p["purple"]}"/>',f'<rect x="450" y="16" width="4" height="4" fill="{p["mint"]}"/><rect x="506" y="16" width="4" height="4" fill="{p["mint"]}"/>','</svg>']
 (ROOT/f'assets/divider-{theme}.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')
 svg=start(960,80,'Make. Refine. Repeat.','Loop Lab — WizardLoop.',p)
 svg += [f'<path d="M3 3v14h14m940 46v14h-14" fill="none" stroke="{p["border"]}" stroke-width="2"/>',text_paths('MAKE. REFINE. REPEAT.',329,43,24,p['muted'],0.8),f'<rect x="298" y="30" width="9" height="9" fill="none" stroke="{p["purple"]}"/>',f'<path d="M318 34.5h10" stroke="{p["purple"]}"/>','</svg>']
 (ROOT/f'assets/footer-{theme}.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')
if __name__=='__main__':
 for theme in PALETTES: toolbox(theme); toolbox(theme,mobile=True); ornaments(theme)
 print('Generated eight original Loop Lab SVGs with outlined Space Grotesk typography.')

