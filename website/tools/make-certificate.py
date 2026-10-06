#!/usr/bin/env python3
"""Generate the Yellowback gold-certificate SVG (website/assets/img/yellowback-certificate.svg).

An original design in the style of the 1882-1928 US gold certificates ("yellowbacks"):
cream paper, engraved dark frame, gold seal and serials, an oval vignette, outlined
denomination. The vignette holds the Ycash glyph (redrawn from YecWallet's res/logo.svg)
instead of a portrait, and every legend names Ycash, so it cannot be mistaken for money.

Usage: python3 website/tools/make-certificate.py  (rewrites the SVG; index.html inlines a copy
between the CERTIFICATE markers, so run with --inline to refresh that too).
"""
import math, pathlib, sys

W, H = 1300, 552
INK = "#2f2b22"
INK2 = "#4a4434"
GOLD = "#d4a019"
GOLD_D = "#a8770c"
PAPER = "#f2ead2"
SERIF = "'Playfair Display', 'Old Standard TT', Georgia, 'Times New Roman', serif"
out = []
a = out.append


def rosette(cx, cy, r, n, rx_k, ry_k, stroke, sw, op=1.0):
    """Guilloche rosette: n ellipses rotated about a centre."""
    g = [f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" opacity="{op}">']
    for i in range(n):
        g.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{r*rx_k:.1f}" ry="{r*ry_k:.1f}" '
                 f'transform="rotate({180*i/n:.2f} {cx} {cy})"/>')
    g.append("</g>")
    return "".join(g)


def star(cx, cy, r1, r2, n):
    pts = []
    for i in range(2 * n):
        r = r1 if i % 2 == 0 else r2
        t = math.pi * i / n - math.pi / 2
        pts.append(f"{cx + r*math.cos(t):.1f},{cy + r*math.sin(t):.1f}")
    return " ".join(pts)


def wave_band(x0, x1, y, amp, period, count, gap, stroke, sw):
    """Stacked sine lines: the engraved band texture."""
    g = [f'<g fill="none" stroke="{stroke}" stroke-width="{sw}">']
    for k in range(count):
        yy = y + k * gap
        d = [f"M{x0},{yy:.1f}"]
        x = x0
        while x < x1:
            x2 = min(x + period, x1)
            d.append(f"Q{x + period/4:.1f},{yy - amp:.1f} {x + period/2:.1f},{yy:.1f} "
                     f"T{x2:.1f},{yy:.1f}")
            x = x2
        g.append(f'<path d="{" ".join(d)}"/>')
    g.append("</g>")
    return "".join(g)


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
  f'aria-label="The Yellowback certificate: an engraved gold certificate, One YED, backed by Ycash locked on chain, redeemable to the keyholder on unlock.">')
a("<defs>")
a('<filter id="cpaper" x="0" y="0" width="100%" height="100%">'
  '<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7" result="n"/>'
  '<feColorMatrix in="n" type="matrix" values="0 0 0 0 .35  0 0 0 0 .3  0 0 0 0 .2  0 0 0 .09 0" result="t"/>'
  '<feComposite in="t" in2="SourceGraphic" operator="in" result="tt"/>'
  '<feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="tt"/></feMerge></filter>')
a(f'<pattern id="chatch" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M0 0V5" stroke="{INK2}" stroke-width="1.6"/></pattern>')
a(f'<pattern id="cxhatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V4" stroke="{INK}" stroke-width="1.1"/></pattern>')
a(f'<pattern id="cframe" width="18" height="18" patternUnits="userSpaceOnUse">'
  f'<rect width="18" height="18" fill="{INK}"/>'
  f'<circle cx="9" cy="9" r="7" fill="none" stroke="{PAPER}" stroke-opacity=".35" stroke-width=".8"/>'
  f'<circle cx="0" cy="0" r="7" fill="none" stroke="{PAPER}" stroke-opacity=".25" stroke-width=".8"/>'
  f'<circle cx="18" cy="18" r="7" fill="none" stroke="{PAPER}" stroke-opacity=".25" stroke-width=".8"/></pattern>')
a('<linearGradient id="cshine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
  '<stop offset=".5" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
a('<radialGradient id="cvig" cx="50%" cy="45%" r="60%"><stop offset="0" stop-color="#fbf6e6"/><stop offset="1" stop-color="#e2d6b0"/></radialGradient>')
a('<clipPath id="cclip"><rect x="0" y="0" width="1300" height="552" rx="10"/></clipPath>')
a('<clipPath id="coval"><ellipse cx="650" cy="290" rx="128" ry="160"/></clipPath>')
a(f'<path id="carcTop" d="M312 150 C 475 50, 825 50, 988 150"/>')
a(f'<path id="cseal" d="M300 270 m -96 0 a 96 96 0 1 1 192 0 a 96 96 0 1 1 -192 0"/>')
a("</defs>")

a('<g clip-path="url(#cclip)">')
# paper
a(f'<rect width="{W}" height="{H}" fill="{PAPER}" filter="url(#cpaper)"/>')
# frame: engraved band with an inner cartouche cut-out
a(f'<path fill="url(#cframe)" fill-rule="evenodd" d="M0 0H{W}V{H}H0Z '
  f'M120 92 Q 120 70 150 70 H{W-150} Q {W-120} 70 {W-120} 92 V{H-112} Q {W-120} {H-92} {W-150} {H-92} H150 Q 120 {H-92} 120 {H-112} Z"/>')
a(f'<rect x="10" y="10" width="{W-20}" height="{H-20}" fill="none" stroke="{PAPER}" stroke-opacity=".5" stroke-width="2"/>')
a(f'<path fill="none" stroke="{INK}" stroke-width="3" d="M126 96 Q 126 76 152 76 H{W-152} Q {W-126} 76 {W-126} 96 V{H-116} Q {W-126} {H-98} {W-152} {H-98} H152 Q 126 {H-98} 126 {H-116} Z"/>')
# soft guilloche wash on the paper field
a(rosette(650, 290, 330, 72, 1.0, 0.42, INK2, 0.5, 0.12))
a(rosette(980, 300, 170, 48, 1.0, 0.5, INK2, 0.5, 0.10))

# side scroll curls (left/right of the cartouche)
for sx, flip in ((120, 1), (W - 120, -1)):
    a(f'<g transform="translate({sx} 276) scale({flip} 1)" fill="none" stroke="{PAPER}" stroke-width="3" opacity=".8">'
      '<path d="M0 -110 C 40 -100, 52 -40, 22 -20 C 2 -6, 4 20, 24 30 C 56 46, 44 104, 0 116"/>'
      '<path d="M22 -20 C 40 -30, 46 -8, 32 0 C 22 6, 20 -6, 28 -8" stroke-width="2"/></g>')
    a(f'<text x="{sx - 82*flip if flip==1 else sx + 82}" y="276" transform="rotate({-90*flip} {sx - 82*flip if flip==1 else sx + 82} 276)" '
      f'text-anchor="middle" font-family="{SERIF}" font-weight="900" font-size="22" letter-spacing="6" fill="{PAPER}" opacity=".9">YEC</text>')

# corner denominations
for cx, cy in ((76, 66), (W - 76, 66), (76, H - 66), (W - 76, H - 66)):
    a(rosette(cx, cy, 52, 36, 1.0, 0.45, PAPER, 0.7, 0.5))
    a(f'<circle cx="{cx}" cy="{cy}" r="42" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>')
    a(f'<circle cx="{cx}" cy="{cy}" r="36" fill="none" stroke="{INK2}" stroke-width="1" stroke-dasharray="2 2"/>')
    a(f'<text x="{cx}" y="{cy + 22}" text-anchor="middle" font-family="{SERIF}" font-weight="900" font-size="64" fill="{INK}">1</text>')

# top legend + ribbon banner
a(f'<rect x="300" y="22" width="700" height="24" fill="{PAPER}" stroke="{INK}" stroke-width="1.5"/>')
a(f'<text x="650" y="39.5" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="12.5" letter-spacing="1.6" fill="{INK}">'
  'THIS CERTIFIES THAT THERE HAS BEEN LOCKED IN A VAULT ON THE YCASH CHAIN</text>')
a(f'<path d="M300 158 C 470 52, 830 52, 1000 158 L 990 126 C 830 22, 470 22, 310 126 Z" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>')
a(f'<path d="M300 158 L 262 150 L 286 132 L 270 112 L 310 126" fill="{INK2}" stroke="{INK}" stroke-width="2"/>')
a(f'<path d="M1000 158 L 1038 150 L 1014 132 L 1030 112 L 990 126" fill="{INK2}" stroke="{INK}" stroke-width="2"/>')
a(f'<text font-family="{SERIF}" font-weight="900" font-size="31" letter-spacing="6" fill="url(#chatch)" stroke="{INK}" stroke-width="1.3">'
  f'<textPath href="#carcTop" startOffset="50%" text-anchor="middle">YCASH YELLOWBACK</textPath></text>')

# gold seal (left)
a(f'<polygon points="{star(300, 270, 112, 100, 48)}" fill="{GOLD}" opacity=".9"/>')
a(rosette(300, 270, 92, 40, 1.0, 0.36, GOLD_D, 0.8, 0.9))
a(f'<circle cx="300" cy="270" r="96" fill="none" stroke="{GOLD_D}" stroke-width="2"/>')
a(f'<circle cx="300" cy="270" r="74" fill="none" stroke="{GOLD_D}" stroke-width="1.5"/>')
a(f'<text font-family="{SERIF}" font-weight="700" font-size="13" letter-spacing="3" fill="{GOLD_D}">'
  f'<textPath href="#cseal" startOffset="0">· YELLOWBACK · AS GOOD AS GOLD · BACKED BY YCASH · SINCE BLOCK 3,075,000 </textPath></text>')
a(f'<text x="300" y="226" text-anchor="middle" font-family="{SERIF}" font-weight="900" font-size="30" letter-spacing="3" fill="{GOLD_D}" opacity=".95">GOLD</text>')
a(f'<text x="300" y="338" text-anchor="middle" font-family="{SERIF}" font-weight="900" font-size="24" letter-spacing="2" fill="{INK}" opacity=".75">CERTIFICATE</text>')
for i, line in enumerate(("THIS CERTIFICATE IS BACKED BY YEC",
                          "LOCKED ON CHAIN, REDEEMABLE IN FULL",
                          "TO THE KEYHOLDER AT THE UNLOCK HEIGHT.")):
    a(f'<text x="300" y="{262 + i*16}" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="10.5" letter-spacing=".4" fill="{INK}">{line}</text>')

# serials (gold)
for x, y, anchor in ((300, 404, "middle"), (848, 200, "start")):
    a(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{SERIF}" font-weight="700" font-size="34" letter-spacing="3" fill="{GOLD}" stroke="{GOLD_D}" stroke-width=".6">Y03075000A</text>')
a(f'<text x="220" y="190" font-family="{SERIF}" font-weight="700" font-size="20" fill="{INK}">Y</text>')
# series
a(f'<text x="420" y="196" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="12" letter-spacing="1" fill="{INK}">SERIES OF</text>')
a(f'<text x="420" y="212" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="13" letter-spacing="1" fill="{INK}">2026</text>')

# central oval vignette with the Ycash glyph engraved
a(f'<ellipse cx="650" cy="290" rx="140" ry="172" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>')
a(rosette(650, 290, 156, 60, 0.92, 1.1, INK2, 0.5, 0.35))
a(f'<ellipse cx="650" cy="290" rx="128" ry="160" fill="url(#cvig)" stroke="{INK}" stroke-width="2"/>')
a('<g clip-path="url(#coval)">')
for k in range(0, 34):  # concentric engraving
    a(f'<ellipse cx="650" cy="300" rx="{20 + k*4.2:.1f}" ry="{24 + k*5.2:.1f}" fill="none" stroke="{INK2}" stroke-width=".55" opacity="{0.55 - k*0.012:.2f}"/>')
a("</g>")
a(f'<circle cx="650" cy="284" r="86" fill="url(#cxhatch)" opacity=".35"/>')
a(f'<circle cx="650" cy="284" r="86" fill="none" stroke="{INK}" stroke-width="3"/>')
a(f'<g transform="translate(650 284) scale(1.2) translate(-50 -50)" fill="none" stroke="{INK}" stroke-linecap="round">'
  '<path d="M20 18V55" stroke-width="11"/><path d="M80 18V55" stroke-width="11"/>'
  '<path d="M20 55A30 30 0 0 0 80 55" stroke-width="9"/><path d="M38 36V58M50 36V58M62 36V58" stroke-width="10"/></g>')
a(f'<g transform="translate(650 284) scale(1.2) translate(-50 -50)" fill="none" stroke="{PAPER}" stroke-linecap="round" stroke-opacity=".55">'
  '<path d="M18 20V53M78 20V53M36 38V56M48 38V56M60 38V56" stroke-width="1.4"/></g>')
a(f'<path d="M590 420 Q 650 438 710 420 L 704 440 Q 650 456 596 440 Z" fill="{PAPER}" stroke="{INK}" stroke-width="1.6"/>')
a(f'<text x="650" y="439" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="12" letter-spacing="3" fill="{INK}">YCASH</text>')

# big hatched denomination (right)
a(f'<text x="988" y="350" text-anchor="middle" font-family="{SERIF}" font-weight="900" font-size="138" letter-spacing="2" '
  f'fill="url(#chatch)" stroke="{INK}" stroke-width="2.4">ONE</text>')
a(f'<text x="985" y="398" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="14" letter-spacing="4" fill="{INK}">YELLOWBACK DOLLAR · 1 YED</text>')

# signatures
a(f'<path d="M186 428 c 10 -22, 22 -24, 18 -4 c -3 14, 10 -20, 24 -12 c 10 6, -8 16, 6 10 c 16 -8, 26 -18, 30 -6 c 3 10, 18 -8, 30 -2 c 8 4, 18 -4, 28 -6" fill="none" stroke="{INK}" stroke-width="1.8"/>')
a(f'<text x="240" y="446" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="11" fill="{INK}">Keyholder of the Vault</text>')
a(f'<path d="M1006 428 c 8 -18, 18 -22, 22 -6 c 4 14, 12 -14, 22 -10 c 12 6, -2 16, 10 12 c 18 -6, 22 -16, 32 -8 c 10 8, 22 -6, 34 -4" fill="none" stroke="{INK}" stroke-width="1.8"/>')
a(f'<text x="1060" y="446" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="11" fill="{INK}">Enforced by the Miners</text>')
a(f'<text x="830" y="432" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="15" letter-spacing="1" fill="{INK}">ON THE YCASH CHAIN</text>')
a(f'<text x="830" y="448" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="10" letter-spacing="1.4" fill="{INK}">P2SH · CHECKLOCKTIMEVERIFY</text>')

# bottom banner
a(f'<rect x="300" y="470" width="700" height="46" fill="{INK}"/>')
a(wave_band(300, 1000, 476, 2.2, 14, 9, 4.4, PAPER, 0.5).replace('<g ', '<g opacity=".18" ', 1))
a(f'<text x="650" y="506" text-anchor="middle" font-family="{SERIF}" font-weight="900" font-size="38" letter-spacing="10" '
  f'fill="{PAPER}" stroke="{INK}" stroke-width="1">ONE DOLLAR</text>')
a(f'<rect x="300" y="518" width="700" height="22" fill="{PAPER}" stroke="{INK}" stroke-width="1.5"/>')
a(f'<text x="650" y="534" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="12.5" letter-spacing="1.8" fill="{INK}">'
  'IN YCASH COLLATERAL · RETURNED TO THE KEYHOLDER ON UNLOCK</text>')

# moving shine (CSS-animated when inlined: .cert-shine)
a(f'<rect class="cert-shine" x="-400" y="-60" width="260" height="{H + 120}" fill="url(#cshine)" transform="skewX(-18)" opacity=".5"/>')
a("</g>")
a("</svg>")

svg = "\n".join(out)
root = pathlib.Path(__file__).resolve().parent.parent
(root / "assets/img/yellowback-certificate.svg").write_text(svg + "\n")
if "--inline" in sys.argv:
    idx = root / "index.html"
    s = idx.read_text()
    b, e = "<!-- CERTIFICATE:BEGIN (generated by tools/make-certificate.py --inline) -->", "<!-- CERTIFICATE:END -->"
    i, j = s.index(b), s.index(e)
    idx.write_text(s[: i + len(b)] + "\n" + svg + "\n" + s[j:])
print("wrote", len(svg), "bytes")
