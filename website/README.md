# yellowbacks.com — the Yellowback website

The public site and documentation for **Ycash Yellowback (YED)**: what it is, how it works, and
how to use it. Plain static HTML, CSS and JavaScript — no framework, no build step, no tracking.
It can be hosted on any static host (GitHub Pages, Netlify, Cloudflare Pages, S3, nginx) as-is.

## Run it locally

```bash
make site                                  # from the workspace root, then open http://localhost:8000
# or, equivalently:
python3 -m http.server 8000 -d website
```

Opening `website/index.html` straight from disk (`file://`) also works; only the footer's
page-hash line needs an HTTP server.

## Layout

```
website/
├── index.html          home: hero, the gold-certificate story, the Lock→Mint→Spend→Unlock line,
│                       the mint calculator, sell-vs-keep, the vault timeline, cypherpunk roots
├── how-it-works.html   vault anatomy, network map, price feed, lock terms, scenarios, safety rails
├── docs.html           public documentation: quick start, glossary, lifecycle, fees, claims,
│                       parameters, price feed, enforcement, RPCs, components, privacy, risks
├── faq.html
├── assets/
│   ├── css/site.css    design tokens and every component style
│   ├── js/site.js      progressive enhancement: fiber-line backdrops, stepper, calculator,
│   │                   sell-vs-keep slider, reveal/scramble effects, certificate tilt
│   └── img/            yellowback-mark.svg, favicon.svg, yellowback-certificate.svg,
│                       ycash-logo.svg (YecWallet's res/logo.svg, MIT, The Ycash developers)
└── tools/make-certificate.py   regenerates the certificate SVG (and, with --inline, the copy
                                inlined in index.html between the CERTIFICATE markers)
```

The header, footer and SVG sprite are repeated in each page (there is no templating step); change
them in all four files.

## Keeping it accurate

Every number on the site comes from the plans in `docs/plans/` — mainly the v2 plan §3.1
(parameters) and the v3 plan (price attestation) — and the release state in the top-level
`README.md`. When a parameter or the release status changes, update:

- the status bar (all four pages) and `docs.html#status`;
- `docs.html#parameters` and `#fees`;
- the calculator constants in `assets/js/site.js` (term-class ratios, fee, mint limits, 110 %).

Naming follows `AGENTS.md` §6: **Yellowback** is the system, **YED** is the unit.
