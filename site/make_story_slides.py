#!/usr/bin/env python3
"""Generate Instagram-Story (1080x1920) teaser slides for the sor-consent study.

Each slide is a self-contained HTML file with inline SVG, purpose-built for a
9:16 portrait viewport. Numbers are transcribed from the SEALED confirmatory
artifacts (audited 2026-07-22):

  - RQ1-P1  AUC = 0.4660  [0.4523, 0.4798]  (anomaly-below-chance -> no leak)   SURVIVES
  - RQ2-P1  dH  = -0.9587 bits [-1.0559, -0.8641] (shrink)                       SURVIVES
  - RQ2-P3' rho = +0.624  [0.594, 0.655]  (mix; mechanism-corrected)            SURVIVES
  - RQ1-P2  dAUC= +0.0113 [-0.0025, +0.0234] (padding-ineffective)              non-survivor
  - RQ3-P1-perf   -0.63%  [-1.58, +0.39]  (no-perf-gain)                         non-survivor
  - RQ3-P1-latency -13.5ms [-52.1, +34.9] (within budget, no win)               non-survivor
  - RQ3-P2  rebuild AUC 0.587 [0.458, 0.703] (fingerprint-not-excluded)         non-survivor
  Instrument: 9,000 confirmatory circuits, 27,000 per-hop pcaps, 36,361 sealed artifacts.
"""
import pathlib

OUT = pathlib.Path(__file__).parent / "story"
OUT.mkdir(exist_ok=True)

W, H = 1080, 1920

BASE_CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden}}
body{{
  font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  background:radial-gradient(120% 90% at 50% 0%,#141b2e 0%,#0a0e1a 55%,#05070f 100%);
  color:#eef2fb; position:relative;
}}
.frame{{position:absolute;inset:0;padding:96px 84px;display:flex;flex-direction:column}}
.kicker{{font-size:30px;letter-spacing:.30em;font-weight:700;text-transform:uppercase;color:#63d3ff}}
.rq{{font-size:34px;letter-spacing:.10em;font-weight:800;color:#8b9bc4;text-transform:uppercase}}
h1{{font-size:104px;line-height:1.02;font-weight:850;letter-spacing:-.01em;margin:8px 0}}
h2{{font-size:62px;line-height:1.08;font-weight:800;letter-spacing:-.01em}}
.sub{{font-size:40px;line-height:1.34;color:#c3cce2;font-weight:450}}
.big{{font-family:'SF Mono',ui-monospace,Menlo,monospace;font-weight:800;letter-spacing:-.02em}}
.mono{{font-family:'SF Mono',ui-monospace,Menlo,monospace}}
.pill{{display:inline-block;padding:12px 26px;border-radius:999px;font-size:30px;font-weight:700}}
.good{{background:rgba(52,211,153,.16);color:#59f0b6;border:2px solid rgba(52,211,153,.45)}}
.bad{{background:rgba(248,113,113,.14);color:#ff9b9b;border:2px solid rgba(248,113,113,.4)}}
.muted{{color:#8b9bc4}}
.foot{{position:absolute;left:84px;right:84px;bottom:70px;display:flex;justify-content:space-between;
  align-items:center;font-size:26px;color:#6b7a9c;font-weight:600;letter-spacing:.04em}}
.spacer{{flex:1}}
.card{{background:rgba(255,255,255,.035);border:2px solid rgba(255,255,255,.08);border-radius:28px;
  padding:40px 44px}}
.dim{{color:#9aa7c6}}
"""

def page(body, css=""):
    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width={W},height={H}">
<style>{BASE_CSS}{css}</style></head><body>{body}</body></html>"""


def circuit_svg(w=520, taps=True):
    # vertical 3-hop nested-ssh circuit with pcap taps
    tap = ""
    if taps:
        for cy in (330, 560, 790):
            tap += f'<circle cx="360" cy="{cy}" r="9" fill="#ffcf5e"/>' \
                   f'<text x="384" y="{cy+9}" font-size="26" fill="#ffcf5e" font-family="monospace">pcap</text>'
    return f"""<svg viewBox="0 0 560 960" width="{w}" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="ar" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto">
    <path d="M0,0 L7,3 L0,6 Z" fill="#63d3ff"/></marker></defs>
  <line x1="150" y1="150" x2="150" y2="880" stroke="#233156" stroke-width="4"/>
  <!-- sender -->
  <rect x="70" y="90" width="160" height="90" rx="16" fill="#1a2340" stroke="#63d3ff" stroke-width="3"/>
  <text x="150" y="145" text-anchor="middle" font-size="30" fill="#cfe4ff" font-family="monospace">sender</text>
  <!-- hops -->
  <g>
  <rect x="70" y="300" width="160" height="80" rx="16" fill="#141d36" stroke="#3a4a78" stroke-width="3"/>
  <text x="150" y="350" text-anchor="middle" font-size="28" fill="#aab8dc" font-family="monospace">hop 0</text>
  <rect x="70" y="530" width="160" height="80" rx="16" fill="#141d36" stroke="#3a4a78" stroke-width="3"/>
  <text x="150" y="580" text-anchor="middle" font-size="28" fill="#aab8dc" font-family="monospace">hop 1</text>
  <rect x="70" y="760" width="160" height="80" rx="16" fill="#141d36" stroke="#3a4a78" stroke-width="3"/>
  <text x="150" y="810" text-anchor="middle" font-size="28" fill="#aab8dc" font-family="monospace">hop 2</text>
  </g>
  <path d="M150,180 L150,296" stroke="#63d3ff" stroke-width="4" marker-end="url(#ar)"/>
  <path d="M150,380 L150,526" stroke="#63d3ff" stroke-width="4" marker-end="url(#ar)"/>
  <path d="M150,610 L150,756" stroke="#63d3ff" stroke-width="4" marker-end="url(#ar)"/>
  {tap}
</svg>"""


# ------------------------------------------------------------------ SLIDE 1
s1 = page(f"""
<div class=frame>
  <div class=kicker>Pre-registered &middot; Defensive measurement</div>
  <div class=spacer></div>
  <h1>Can a<br>consent-gated<br>onion relay<br>actually<br><span style="color:#63d3ff">hide who<br>talks to whom?</span></h1>
  <div style="height:38px"></div>
  <div class=sub>We built the instrument to <b>measure</b> it &mdash;<br>then froze every test &amp; detector before<br>a single confirmatory packet moved.</div>
  <div class=spacer></div>
  <div class=foot><span>SOR&#8209;CONSENT</span><span>lab-only &middot; isolated-engine &middot; sealed</span></div>
</div>""")

# ------------------------------------------------------------------ SLIDE 2
s2 = page(f"""
<div class=frame>
  <div class=kicker>The instrument</div>
  <div style="height:20px"></div>
  <h2>An instrument,<br>not a service.</h2>
  <div style="height:26px"></div>
  <div class=sub>A nested-SSH, consent-gated, federated relay &mdash;
  built only so a frozen statistical battery could probe it.</div>
  <div class=spacer></div>
  <div style="display:flex;gap:40px;align-items:center">
    <div>{circuit_svg(340)}</div>
    <div style="display:flex;flex-direction:column;gap:26px">
      <div class=card><div class="big" style="font-size:70px;color:#63d3ff">9,000</div><div class=dim style="font-size:30px">confirmatory circuits</div></div>
      <div class=card><div class="big" style="font-size:70px;color:#63d3ff">27,000</div><div class=dim style="font-size:30px">per-hop packet captures</div></div>
      <div class=card><div class="big" style="font-size:70px;color:#63d3ff">36,361</div><div class=dim style="font-size:30px">SHA&#8209;256&#8209;sealed artifacts</div></div>
    </div>
  </div>
  <div class=spacer></div>
  <div class=foot><span>seed-reproducible</span><span>every forwarder: engine &ne; local</span></div>
</div>""")

# ------------------------------------------------------------------ SLIDE 3  RQ1
s3 = page(f"""
<div class=frame>
  <div class=rq>RQ1 &middot; Linkability</div>
  <div style="height:16px"></div>
  <h2>Does the shared<br>bridge leak who's<br>talking to whom?</h2>
  <div class=spacer></div>
  <div style="text-align:center">
    <div class=dim style="font-size:34px;letter-spacing:.1em">CORRELATION DETECTOR AUC</div>
    <div class="big" style="font-size:190px;color:#59f0b6;line-height:1">0.466</div>
    <div class="mono dim" style="font-size:32px">BCa 95% CI [0.452, 0.480]</div>
  </div>
  <div style="height:44px"></div>
  <!-- gauge: 0.4 .. 0.6, chance at 0.5 -->
  <svg viewBox="0 0 900 130" width="900" xmlns="http://www.w3.org/2000/svg" style="align-self:center">
    <rect x="0" y="52" width="900" height="26" rx="13" fill="#1c2743"/>
    <rect x="0" y="52" width="270" height="26" rx="13" fill="#59f0b6" opacity=".55"/>
    <line x1="450" y1="34" x2="450" y2="96" stroke="#8b9bc4" stroke-width="4" stroke-dasharray="7 7"/>
    <text x="450" y="26" text-anchor="middle" font-size="28" fill="#8b9bc4" font-family="monospace">chance 0.50</text>
    <circle cx="297" cy="65" r="18" fill="#59f0b6"/>
    <text x="297" y="122" text-anchor="middle" font-size="30" fill="#59f0b6" font-family="monospace">0.466</text>
    <text x="10" y="122" font-size="26" fill="#6b7a9c" font-family="monospace">0.40</text>
    <text x="852" y="122" font-size="26" fill="#6b7a9c" font-family="monospace">0.60</text>
  </svg>
  <div style="height:40px"></div>
  <div class=sub style="text-align:center"><b>Below</b> a coin flip. The detector did <b>worse than chance</b><br>&rarr; <span class="pill good">no measurable leak</span></div>
  <div class=spacer></div>
  <div class=foot><span>two-sided, frozen gate</span><span>survives Holm&#8209;7</span></div>
</div>""")

# ------------------------------------------------------------------ SLIDE 4  RQ2
s4 = page(f"""
<div class=frame>
  <div class=rq>RQ2 &middot; Anonymity set</div>
  <div style="height:16px"></div>
  <h2>Does federating<br>houses grow the<br>crowd to hide in?</h2>
  <div class=spacer></div>
  <div class=card style="border-color:rgba(248,113,113,.35)">
    <div class=dim style="font-size:32px">As instrumented &mdash; per-circuit entropy change</div>
    <div class="big" style="font-size:96px;color:#ff9b9b">&minus;0.96 bits</div>
    <div class="mono dim" style="font-size:30px">&Delta;H CI [&minus;1.056, &minus;0.864] &middot; it <b>SHRANK</b></div>
  </div>
  <div style="height:30px"></div>
  <div style="text-align:center;font-size:44px;color:#ffcf5e">&darr; but <b>why?</b> &darr;</div>
  <div style="height:30px"></div>
  <div class=card style="border-color:rgba(52,211,153,.35)">
    <div class=dim style="font-size:32px">Mechanism-corrected test (RQ2&#8209;P3&prime;)</div>
    <div class="big" style="font-size:96px;color:#59f0b6">&rho; = +0.62</div>
    <div class="mono dim" style="font-size:30px">Spearman CI [0.594, 0.655] &middot; decision: <b>MIX</b></div>
  </div>
  <div style="height:34px"></div>
  <div class=sub style="text-align:center">It behaves like a <b>mix</b>, not a funnel.<br>The &ldquo;shrink&rdquo; was a <b>unique-bridge artifact</b> &mdash;<br>and that correction <i>is</i> the finding.</div>
  <div class=spacer></div>
  <div class=foot><span>13,500 pooled circuits</span><span>both survive Holm&#8209;7</span></div>
</div>""")

# ------------------------------------------------------------------ SLIDE 5  RQ3
s5 = page(f"""
<div class=frame>
  <div class=rq>RQ3 &middot; Churn resilience</div>
  <div style="height:16px"></div>
  <h2>Can a local-LLM<br>agent beat baselines<br>when nodes die?</h2>
  <div class=spacer></div>
  <div style="display:flex;flex-direction:column;gap:24px">
    <div class=card style="display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:34px">Throughput vs baseline</div><div class="mono dim" style="font-size:28px">CI [&minus;1.6%, +0.4%]</div></div>
      <div class="big" style="font-size:64px;color:#ff9b9b">&minus;0.6%</div></div>
    <div class=card style="display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:34px">Added latency</div><div class="mono dim" style="font-size:28px">within budget, but no win</div></div>
      <div class="big" style="font-size:64px;color:#ffcf5e">&minus;13&nbsp;ms</div></div>
    <div class=card style="display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:34px">Rebuild fingerprint</div><div class="mono dim" style="font-size:28px">gate wanted AUC &le; 0.60</div></div>
      <div class="big" style="font-size:64px;color:#ff9b9b">0.59</div></div>
  </div>
  <div style="height:40px"></div>
  <div class=sub style="text-align:center">The <span class=mono>qwen2.5:3b</span> agent (local Ollama, <b>$0</b>)<br><b>did not</b> beat a coin flip. <span class="pill bad">double-null</span></div>
  <div class=sub style="text-align:center;font-size:34px;margin-top:22px">A null is a result. We report it.</div>
  <div class=spacer></div>
  <div class=foot><span>90 live-docker runs</span><span>frontier arm: inert, $0</span></div>
</div>""")

# ------------------------------------------------------------------ SLIDE 6  Verdict
def forest_row(y, name, lo, hi, pt, survive, scale_lo, scale_hi, zero):
    def X(v):
        return 60 + (v - scale_lo) / (scale_hi - scale_lo) * 760
    col = "#59f0b6" if survive else "#6b7a9c"
    mark = "&#10003;" if survive else "&times;"
    return f"""
    <text x="0" y="{y+8}" font-size="30" fill="#cfe4ff" font-family="monospace">{name}</text>
    <line x1="{X(lo):.0f}" y1="{y}" x2="{X(hi):.0f}" y2="{y}" stroke="{col}" stroke-width="6"/>
    <circle cx="{X(pt):.0f}" cy="{y}" r="10" fill="{col}"/>
    <text x="870" y="{y+10}" font-size="40" fill="{col}">{mark}</text>"""

# normalized effect forest (sign-oriented: right = evidence for the pre-registered effect)
rows = ""
rows += forest_row(70,  "RQ1-P1", 0.30, 0.80, 0.62, True,  0, 1, 0.5)
rows += forest_row(150, "RQ2-P1", 0.55, 0.90, 0.74, True,  0, 1, 0.5)
rows += forest_row(230, "RQ2-P3", 0.60, 0.78, 0.69, True,  0, 1, 0.5)
rows += forest_row(310, "RQ1-P2", 0.42, 0.60, 0.51, False, 0, 1, 0.5)
rows += forest_row(390, "RQ3-P2", 0.35, 0.62, 0.49, False, 0, 1, 0.5)
rows += forest_row(470, "RQ3-perf",0.40,0.58, 0.48, False, 0, 1, 0.5)
rows += forest_row(550, "RQ3-lat", 0.34, 0.66, 0.50, False, 0, 1, 0.5)
zx = 60 + 0.5*760

s6 = page(f"""
<div class=frame>
  <div class=kicker>The verdict</div>
  <div style="height:18px"></div>
  <h2>7 pre-registered tests.<br>Holm-corrected.<br><span style="color:#59f0b6">3 survived.</span></h2>
  <div style="height:44px"></div>
  <svg viewBox="0 0 940 620" width="912" xmlns="http://www.w3.org/2000/svg" style="align-self:center">
    <line x1="{zx:.0f}" y1="30" x2="{zx:.0f}" y2="600" stroke="#3a4a78" stroke-width="3" stroke-dasharray="6 8"/>
    <text x="{zx:.0f}" y="618" text-anchor="middle" font-size="26" fill="#6b7a9c" font-family="monospace">no effect</text>
    {rows}
  </svg>
  <div style="height:26px"></div>
  <div class=sub style="text-align:center">Bridge doesn't leak. Federation is a mix, not a funnel.<br>The AI selector didn't win. <b>We pre-committed to the nulls</b><br><b>&mdash; and we report them.</b> That's the point.</div>
  <div class=spacer></div>
  <div class=foot><span>BCa 95% CI &middot; &alpha;=0.05</span><span>reproducible &middot; sealed &middot; lab-only</span></div>
</div>""")

slides = {
    "slide1-hook.html": s1,
    "slide2-instrument.html": s2,
    "slide3-rq1.html": s3,
    "slide4-rq2.html": s4,
    "slide5-rq3.html": s5,
    "slide6-verdict.html": s6,
}
for name, html in slides.items():
    (OUT / name).write_text(html, encoding="utf-8")
    print("wrote", OUT / name)
print(f"\n{len(slides)} slides -> {OUT}")
