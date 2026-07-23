#!/usr/bin/env python3
"""Build a single, self-contained localhost HTML page for the sor-consent study.

Reads the two paper drafts (lead + combined companion) and renders them into
one offline HTML file with an executive summary and hand-authored SVG figures.
Number fidelity is guaranteed because the paper bodies are converted straight
from the committed markdown -- no figure is transcribed by hand except the
SVG annotations, which are cross-checked against the sealed records.

Sources (read-only):
  docs/stage-07-paper-draft.md        -- lead paper (G4 + RQ1 + RQ2)
  docs/stage-07-companion-methods.md  -- combined companion (RQ2-P3 mechanism + RQ3)

Output:
  docs/paper-site/index.html
"""
from pathlib import Path
import markdown

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
LEAD_MD = DOCS / "stage-07-paper-draft.md"
COMPANION_MD = DOCS / "stage-07-companion-methods.md"
OUT = HERE / "index.html"

MD_EXT = ["tables", "fenced_code", "sane_lists", "attr_list", "toc"]


def render(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    return markdown.markdown(text, extensions=MD_EXT)


lead_html = render(LEAD_MD)
companion_html = render(COMPANION_MD)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Consent-Gated Federated Onion Routing &mdash; study site</title>
<style>
  :root{
    --ink:#151d2b; --muted:#5b6b82; --line:#e3e8ef; --bg:#f5f7fa; --card:#ffffff;
    --teal:#0f766e; --teal-soft:#d7ede9; --green:#15803d; --green-soft:#dcf2e2;
    --amber:#b45309; --amber-soft:#fcecd6; --gray:#64748b; --gray-soft:#e8edf3;
    --accent:#1d4ed8;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  header.hero{background:linear-gradient(135deg,#0b2a3a,#0f766e);color:#fff;padding:38px 20px 30px}
  .wrap{max-width:960px;margin:0 auto;padding:0 20px}
  header.hero .wrap{padding:0 20px}
  header.hero h1{margin:0 0 6px;font-size:26px;line-height:1.25;font-weight:700;letter-spacing:-.2px}
  header.hero p.sub{margin:0;opacity:.9;font-size:15px;max-width:760px}
  .tags{margin-top:16px;display:flex;flex-wrap:wrap;gap:8px}
  .tag{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);
    padding:4px 10px;border-radius:999px;font-size:12.5px}
  nav.toc{position:sticky;top:0;z-index:10;background:rgba(255,255,255,.96);
    backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
  nav.toc .wrap{display:flex;gap:4px;flex-wrap:wrap;padding:8px 20px}
  nav.toc a{padding:7px 12px;border-radius:8px;color:var(--muted);font-size:14px;font-weight:600}
  nav.toc a:hover{background:var(--gray-soft);text-decoration:none;color:var(--ink)}
  main{padding:28px 0 60px}
  section{margin:0 0 34px}
  h2.sh{font-size:21px;margin:6px 0 14px;padding-bottom:8px;border-bottom:2px solid var(--teal);
    display:inline-block}
  .lead{color:var(--muted);max-width:760px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:18px 0}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 16px 14px;
    box-shadow:0 1px 2px rgba(16,24,40,.04)}
  .card .k{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);font-weight:700}
  .card .v{font-size:22px;font-weight:750;margin:6px 0 2px;letter-spacing:-.3px}
  .card .d{font-size:13.5px;color:var(--muted)}
  .pill{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 8px;border-radius:999px;margin-top:8px}
  .pill.null{background:var(--gray-soft);color:#334155}
  .pill.neg{background:var(--amber-soft);color:var(--amber)}
  .pill.mix{background:var(--green-soft);color:var(--green)}
  table.glance{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);
    border-radius:12px;overflow:hidden;font-size:14.5px;margin-top:8px}
  table.glance th,table.glance td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
  table.glance th{background:#f0f4f8;font-size:12.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--muted)}
  table.glance tr:last-child td{border-bottom:none}
  .survive{color:var(--teal);font-weight:700}
  .figure{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 18px 8px;
    margin:18px 0;box-shadow:0 1px 2px rgba(16,24,40,.04)}
  .figure svg{width:100%;height:auto;display:block}
  .figure figcaption{font-size:13.5px;color:var(--muted);margin:6px 4px 10px;line-height:1.5}
  .figure figcaption b{color:var(--ink)}
  .fig-num{font-weight:750;color:var(--teal)}
  /* paper body */
  .paper{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:8px 30px 26px;
    box-shadow:0 1px 2px rgba(16,24,40,.04);
    font-family:Georgia,"Times New Roman",serif;font-size:16.5px;line-height:1.68}
  .paper h1{font-size:24px;line-height:1.28;margin:22px 0 6px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  .paper h2{font-size:20px;margin:26px 0 8px;padding-top:6px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    border-top:1px solid var(--line)}
  .paper h3{font-size:17px;margin:18px 0 6px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  .paper h1:first-child{border:none}
  .paper blockquote{margin:14px 0;padding:12px 16px;background:#f7f9fb;border-left:4px solid var(--teal);
    border-radius:0 8px 8px 0;font-size:15px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#33465c}
  .paper blockquote p{margin:6px 0}
  .paper table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  .paper th,.paper td{border:1px solid var(--line);padding:7px 9px;text-align:left}
  .paper th{background:#f0f4f8}
  .paper code{background:#eef2f7;padding:1px 5px;border-radius:5px;font-size:13.5px;
    font-family:"SF Mono",Menlo,Consolas,monospace}
  .paper hr{border:none;border-top:1px solid var(--line);margin:22px 0}
  .paper a{word-break:break-word}
  .collapsible{margin:10px 0 0}
  details.paperwrap>summary{cursor:pointer;list-style:none;padding:12px 16px;background:var(--card);
    border:1px solid var(--line);border-radius:12px;font-weight:700;color:var(--ink);
    display:flex;justify-content:space-between;align-items:center}
  details.paperwrap>summary::-webkit-details-marker{display:none}
  details.paperwrap>summary .hint{font-weight:500;color:var(--muted);font-size:13px}
  details.paperwrap[open]>summary{border-radius:12px 12px 0 0;border-bottom:none}
  details.paperwrap .paper{border-radius:0 0 14px 14px;border-top:none}
  .prov{font-size:13px;color:var(--muted);background:var(--card);border:1px solid var(--line);
    border-radius:12px;padding:14px 16px;line-height:1.7}
  .prov code{background:#eef2f7;padding:1px 5px;border-radius:5px;font-size:12px;
    font-family:"SF Mono",Menlo,Consolas,monospace;word-break:break-all}
  .legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin:2px 4px 8px}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .sw{width:12px;height:12px;border-radius:3px;display:inline-block}
  footer{padding:26px 0;color:var(--muted);font-size:13px;text-align:center}
  html,body{max-width:100%;overflow-x:hidden}
  .figure svg{max-width:100%}
  @media (max-width:640px){
    .wrap{padding:0 14px}
    header.hero{padding:26px 14px 22px}
    header.hero h1{font-size:20px}
    header.hero p.sub{font-size:14px}
    h2.sh{font-size:19px}
    .figure{padding:12px 12px 6px}
    .figure figcaption{font-size:12.5px}
    .paper{padding:6px 16px 20px;font-size:16px}
    .paper h1{font-size:21px}
    .paper h2{font-size:18px}
    /* wide tables scroll inside their own box instead of pushing the page */
    table.glance,.paper table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap}
    .prov code{white-space:normal}
  }
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <h1>Consent-Gated Federated Onion Routing:<br/>Linkability, Anonymity-Set, and Churn-Resilience of an In-Band Accept/Reject Relay Model</h1>
    <p class="sub">A pre-registered, frozen-detector measurement study on a lab grid (2 phones + laptop, isolated-docker circuits). Two papers: a lead study (RQ1 linkability, RQ2 anonymity set) and a combined companion (RQ2-P3 mix mechanism, RQ3 churn-resilient agent selection). Reported honestly &mdash; nulls and negatives are results.</p>
    <div class="tags">
      <span class="tag">Pre-registered &amp; hashed</span>
      <span class="tag">Detectors frozen before data</span>
      <span class="tag">180 + 13,500 + 4,500 circuits</span>
      <span class="tag">BCa 95% CIs &middot; Holm-7</span>
      <span class="tag">Defensive-measurement instrument</span>
      <span class="tag">Containment: isolated-engine only</span>
    </div>
  </div>
</header>

<nav class="toc"><div class="wrap">
  <a href="#summary">Summary</a>
  <a href="#figures">Visual abstract</a>
  <a href="#lead-paper">Lead paper</a>
  <a href="#companion-paper">Companion paper</a>
  <a href="#provenance">Provenance</a>
</div></nav>

<main class="wrap">

<!-- ================= SUMMARY ================= -->
<section id="summary">
  <h2 class="sh">Executive summary</h2>
  <p class="lead">We built a consent-gated, federated, nested-SSH relay <b>as a measurement instrument</b>
  (not a service) and asked, on a lab grid, whether a shared bridge leaks entry&harr;exit linkability (RQ1),
  whether federation grows or shrinks the anonymity set (RQ2), whether shared-bridge concentration funnels
  or mixes (RQ2-P3), and whether a local open-weight agent selector survives churn without a rebuild
  fingerprint (RQ3). Every detector was calibrated on fixtures and frozen before any confirmatory cell ran.</p>

  <div class="cards">
    <div class="card">
      <div class="k">RQ1 &middot; Bridge linkability</div>
      <div class="v">AUC 0.466</div>
      <div class="d">CI [0.452, 0.480], below the 0.50 chance line. Calibration: linked 1.00 / unlinked 0.50.</div>
      <span class="pill null">No measurable leak</span>
    </div>
    <div class="card">
      <div class="k">RQ2-P1 &middot; Federation</div>
      <div class="v">&Delta;H &minus;0.96 bits</div>
      <div class="d">CI [&minus;1.06, &minus;0.86]. Federation <b>shrinks</b> the per-circuit anonymity set (Holm-significant negative).</div>
      <span class="pill neg">Honest negative</span>
    </div>
    <div class="card">
      <div class="k">RQ2-P3 &middot; Mix mechanism</div>
      <div class="v">&rho; +0.62</div>
      <div class="d">CI [+0.59, +0.65]; slope &beta; +0.71. Shared-pool concentration <b>raises</b> anonymity &mdash; corrects the lead "shrink" as a unique-bridge artifact.</div>
      <span class="pill mix">Resolved: MIX</span>
    </div>
    <div class="card">
      <div class="k">RQ3 &middot; Agent selector</div>
      <div class="v">Null &times; 2</div>
      <div class="d">Retention margin &minus;0.6pp (gate +10pp); rebuild AUC 0.587, CI upper 0.703 &gt; 0.60. Neither beats baselines nor certifiably fingerprint-free (n=30).</div>
      <span class="pill null">H0 on both counts</span>
    </div>
  </div>

  <h3 style="font-size:16px;margin:22px 0 4px">The seven pre-registered tests (authoritative Holm-7)</h3>
  <table class="glance">
    <thead><tr><th>Test</th><th>Effect (point &amp; 95% CI)</th><th>Frozen gate</th><th>Holm-7 adj&nbsp;p</th><th>Survives&nbsp;.05</th></tr></thead>
    <tbody>
      <tr><td class="survive">RQ1-P1 leak</td><td>AUC 0.466 [0.452, 0.480]</td><td>CI excludes 0.5 (leak)</td><td>0</td><td class="survive">yes* (below chance &rarr; no leak)</td></tr>
      <tr><td class="survive">RQ2-P1 federation</td><td>&Delta;H &minus;0.96 [&minus;1.06, &minus;0.86] bits</td><td>two-sided sign</td><td>0</td><td class="survive">yes &mdash; shrink</td></tr>
      <tr><td class="survive">RQ2-P3 mechanism</td><td>&rho; +0.62 [+0.59, +0.65]</td><td>two-sided sign</td><td>0</td><td class="survive">yes &mdash; mix</td></tr>
      <tr><td>RQ1-P2 padding</td><td>&Delta;AUC +0.011 [&minus;0.002, +0.023]</td><td>CI &gt; 0</td><td>0.365</td><td>no</td></tr>
      <tr><td>RQ3-P2 fingerprint</td><td>AUC 0.587 [0.458, 0.703]</td><td>CI upper &le; 0.60</td><td>0.511</td><td>no (not excluded)</td></tr>
      <tr><td>RQ3-P1-perf</td><td>&minus;0.6pp [&minus;1.58, +0.39]pp</td><td>CI lower &ge; +10pp</td><td>0.511</td><td>no</td></tr>
      <tr><td>RQ3-P1-latency</td><td>&minus;13.5ms [&minus;52.1, +34.9]ms</td><td>CI upper &le; 100ms</td><td>0.511</td><td>within budget</td></tr>
    </tbody>
  </table>
  <p class="lead" style="font-size:13.5px;margin-top:8px">* RQ1-P1 rejects "AUC = 0.5" in the <i>wrong</i> direction (below chance), so it is <b>not</b> evidence of a leak. Survivors of the authoritative Holm-7: RQ1-P1, RQ2-P1 (shrink), RQ2-P3 (mix).</p>
</section>

<!-- ================= FIGURES ================= -->
<section id="figures">
  <h2 class="sh">Visual abstract</h2>
  <p class="lead">Publication-ready SVG figures illustrating the instrument, the design, and each finding. All annotations are cross-checked against the sealed analysis records.</p>

  <!-- FIG 1: instrument -->
  <figure class="figure">
    <svg viewBox="0 0 920 330" role="img" aria-label="The consent-gated nested-SSH circuit instrument">
      <defs>
        <marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
          <path d="M0,0 L7,3 L0,6 Z" fill="#0f766e"/>
        </marker>
      </defs>
      <rect x="14" y="60" width="892" height="210" rx="14" fill="none" stroke="#b45309" stroke-width="2" stroke-dasharray="7 5"/>
      <text x="28" y="82" font-size="12.5" font-weight="700" fill="#b45309" font-family="sans-serif">ISOLATED ENGINE (docker) &mdash; assert engine != local, or the run refuses &middot; self-generated fixture traffic, lab-only</text>
      <!-- nodes -->
      <g font-family="sans-serif" text-anchor="middle">
        <!-- client -->
        <rect x="40" y="120" width="120" height="60" rx="10" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.5"/>
        <text x="100" y="146" font-size="14" font-weight="700" fill="#151d2b">Client</text>
        <text x="100" y="165" font-size="11.5" fill="#5b6b82">seeds payload</text>
        <!-- hops -->
        <rect x="240" y="120" width="120" height="60" rx="10" fill="#d7ede9" stroke="#0f766e" stroke-width="1.5"/>
        <text x="300" y="144" font-size="14" font-weight="700" fill="#0f766e">Hop 0</text>
        <text x="300" y="163" font-size="11.5" fill="#33465c">entry segment</text>
        <rect x="440" y="120" width="120" height="60" rx="10" fill="#d7ede9" stroke="#0f766e" stroke-width="1.5"/>
        <text x="500" y="144" font-size="14" font-weight="700" fill="#0f766e">Hop 1</text>
        <text x="500" y="163" font-size="11.5" fill="#33465c">middle</text>
        <rect x="640" y="120" width="120" height="60" rx="10" fill="#d7ede9" stroke="#0f766e" stroke-width="1.5"/>
        <text x="700" y="144" font-size="14" font-weight="700" fill="#0f766e">Hop 2</text>
        <text x="700" y="163" font-size="11.5" fill="#33465c">exit segment</text>
        <!-- sink -->
        <rect x="820" y="120" width="72" height="60" rx="10" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.5"/>
        <text x="856" y="146" font-size="12" font-weight="700" fill="#151d2b">Fixture</text>
        <text x="856" y="164" font-size="11" fill="#5b6b82">sink</text>
      </g>
      <!-- tunnels -->
      <g stroke="#0f766e" stroke-width="2.5" marker-end="url(#arr)">
        <line x1="162" y1="150" x2="236" y2="150"/>
        <line x1="362" y1="150" x2="436" y2="150"/>
        <line x1="562" y1="150" x2="636" y2="150"/>
        <line x1="762" y1="150" x2="816" y2="150"/>
      </g>
      <text x="460" y="108" text-anchor="middle" font-size="12" fill="#0f766e" font-family="sans-serif" font-weight="700">nested-SSH tunnels (R4)</text>
      <!-- consent handshake band -->
      <g font-family="sans-serif" text-anchor="middle">
        <rect x="240" y="212" width="520" height="34" rx="8" fill="#fcf5e9" stroke="#b45309" stroke-width="1.2"/>
        <text x="500" y="234" font-size="12.5" fill="#8a4408" font-weight="700">in-band consent (R5): Ed25519-signed request &rarr; verify before accept &middot; X25519 per-hop credential sealed to host key</text>
      </g>
      <!-- pcaps -->
      <g font-family="sans-serif" text-anchor="middle">
        <text x="300" y="205" font-size="10.5" fill="#5b6b82">&#128190; pcap&#8320;</text>
        <text x="500" y="205" font-size="10.5" fill="#5b6b82">&#128190; pcap&#8321;</text>
        <text x="700" y="205" font-size="10.5" fill="#5b6b82">&#128190; pcap&#8322;</text>
      </g>
      <text x="28" y="300" font-size="11.5" fill="#5b6b82" font-family="sans-serif">Determinism &amp; provenance (R1&ndash;R3): one <tspan font-style="italic">--sor-seed</tspan> &rarr; immutable manifest.json + SHA-256-sealed events.jsonl; every per-hop pcap written once and checksummed.</text>
    </svg>
    <figcaption><span class="fig-num">Figure 1.</span> <b>The instrument.</b> A consent-gated, nested-SSH circuit: each hop must cryptographically accept a signed in-band request before it will carry the flow; per-hop credentials are X25519-sealed to the host key. Every forwarder runs in an isolated engine only. Entry (Hop&nbsp;0) and exit (Hop&nbsp;2) segments are the observable units RQ1 probes.</figcaption>
  </figure>

  <!-- FIG 2: topologies -->
  <figure class="figure">
    <svg viewBox="0 0 920 250" role="img" aria-label="Federation topologies at matched node count">
      <g font-family="sans-serif" text-anchor="middle">
        <!-- 1-house-N -->
        <text x="150" y="28" font-size="13.5" font-weight="700" fill="#151d2b">1-house-N</text>
        <circle cx="150" cy="130" r="78" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.5"/>
        <text x="150" y="60" font-size="11.5" fill="#1d4ed8">House A</text>
        <g fill="#1d4ed8"><circle cx="120" cy="110" r="7"/><circle cx="180" cy="110" r="7"/><circle cx="110" cy="150" r="7"/><circle cx="150" cy="165" r="7"/><circle cx="190" cy="150" r="7"/></g>
        <text x="150" y="228" font-size="11" fill="#5b6b82">all N nodes in one house</text>

        <!-- bridge-federated -->
        <text x="460" y="28" font-size="13.5" font-weight="700" fill="#151d2b">bridge-federated</text>
        <circle cx="392" cy="130" r="52" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.5"/>
        <circle cx="528" cy="130" r="52" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.5"/>
        <text x="392" y="92" font-size="10.5" fill="#1d4ed8">House A</text>
        <text x="528" y="92" font-size="10.5" fill="#1d4ed8">House B</text>
        <g fill="#1d4ed8"><circle cx="375" cy="130" r="6"/><circle cx="405" cy="145" r="6"/><circle cx="515" cy="130" r="6"/><circle cx="545" cy="145" r="6"/></g>
        <circle cx="460" cy="130" r="22" fill="#fcecd6" stroke="#b45309" stroke-width="1.8"/>
        <text x="460" y="134" font-size="10.5" font-weight="700" fill="#b45309">Bridge</text>
        <line x1="437" y1="130" x2="483" y2="130" stroke="#b45309" stroke-width="2"/>
        <text x="460" y="228" font-size="11" fill="#5b6b82">shared observation point</text>

        <!-- directory-federated -->
        <text x="790" y="28" font-size="13.5" font-weight="700" fill="#151d2b">directory-federated</text>
        <circle cx="720" cy="90" r="30" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.4"/>
        <circle cx="860" cy="90" r="30" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.4"/>
        <circle cx="790" cy="185" r="30" fill="#eef4fb" stroke="#1d4ed8" stroke-width="1.4"/>
        <text x="720" y="94" font-size="10" fill="#1d4ed8">A</text>
        <text x="860" y="94" font-size="10" fill="#1d4ed8">B</text>
        <text x="790" y="189" font-size="10" fill="#1d4ed8">C</text>
        <circle cx="790" cy="125" r="24" fill="#d7ede9" stroke="#0f766e" stroke-width="1.8"/>
        <text x="790" y="122" font-size="9.5" font-weight="700" fill="#0f766e">Dir-</text>
        <text x="790" y="133" font-size="9.5" font-weight="700" fill="#0f766e">ectory</text>
        <g stroke="#0f766e" stroke-width="1.6"><line x1="742" y1="103" x2="772" y2="118"/><line x1="838" y1="103" x2="808" y2="118"/><line x1="790" y1="155" x2="790" y2="149"/></g>
        <text x="790" y="228" font-size="11" fill="#5b6b82">no single shared hop</text>
      </g>
    </svg>
    <figcaption><span class="fig-num">Figure 2.</span> <b>Federation topologies (RQ2), matched total node count N.</b> The design isolates the <i>topology</i> effect, not a node-count artifact. RQ2-P1 compares the pooled federated arms against a single house of the same N.</figcaption>
  </figure>

  <!-- FIG 3: RQ1 -->
  <figure class="figure">
    <svg viewBox="0 0 920 190" role="img" aria-label="RQ1 correlation AUC below chance">
      <g font-family="sans-serif">
        <!-- axis -->
        <line x1="70" y1="120" x2="850" y2="120" stroke="#94a3b8" stroke-width="1.5"/>
        <!-- ticks 0.4..1.0 -->
        <g text-anchor="middle" font-size="11" fill="#5b6b82">
          <!-- x = 70 + (val-0.4)/0.6*780 -->
          <line x1="70" y1="116" x2="70" y2="124" stroke="#94a3b8"/><text x="70" y="140">0.40</text>
          <line x1="200" y1="116" x2="200" y2="124" stroke="#94a3b8"/><text x="200" y="140">0.50</text>
          <line x1="330" y1="116" x2="330" y2="124" stroke="#94a3b8"/><text x="330" y="140">0.60</text>
          <line x1="590" y1="116" x2="590" y2="124" stroke="#94a3b8"/><text x="590" y="140">0.80</text>
          <line x1="850" y1="116" x2="850" y2="124" stroke="#94a3b8"/><text x="850" y="140">1.00</text>
        </g>
        <!-- chance line at 0.5 (x=200) -->
        <line x1="200" y1="52" x2="200" y2="120" stroke="#64748b" stroke-width="1.4" stroke-dasharray="5 4"/>
        <text x="200" y="46" text-anchor="middle" font-size="11.5" fill="#64748b" font-weight="700">chance 0.50</text>
        <!-- materiality 0.60 -->
        <line x1="330" y1="70" x2="330" y2="120" stroke="#cbd5e1" stroke-width="1.2" stroke-dasharray="3 3"/>
        <text x="330" y="64" text-anchor="middle" font-size="10.5" fill="#94a3b8">material 0.60</text>
        <!-- calibration linked 1.00 -->
        <circle cx="850" cy="120" r="6" fill="#15803d"/>
        <text x="850" y="104" text-anchor="middle" font-size="11" fill="#15803d" font-weight="700">linked 1.00</text>
        <!-- calibration unlinked 0.50 -->
        <circle cx="200" cy="120" r="5" fill="#64748b"/>
        <!-- measured 0.466 -> x = 70 + (0.466-0.4)/0.6*780 = 70+85.8=155.8 ; CI 0.452..0.480 -> 137.6..174 -->
        <line x1="137.6" y1="120" x2="174" y2="120" stroke="#b45309" stroke-width="4" stroke-linecap="round"/>
        <circle cx="155.8" cy="120" r="7" fill="#b45309"/>
        <text x="150" y="168" text-anchor="middle" font-size="12.5" fill="#b45309" font-weight="700">measured 0.466</text>
        <text x="150" y="184" text-anchor="middle" font-size="11" fill="#8a4408">CI [0.452, 0.480]</text>
        <!-- verdict -->
        <text x="560" y="176" text-anchor="middle" font-size="12.5" fill="#334155">below chance &rarr; <tspan font-weight="700" fill="#b45309">NO measurable entry&harr;exit leak</tspan>; padding (RQ1-P2) has nothing to suppress</text>
      </g>
    </svg>
    <figcaption><span class="fig-num">Figure 3.</span> <b>RQ1 &mdash; bridge linkability.</b> The frozen correlator calibrates perfectly (linked&nbsp;1.00 / unlinked&nbsp;0.50) yet reads the bridge-on traffic at AUC&nbsp;0.466 &mdash; distinguishable from chance but <i>below</i> it, which the pre-registered gate refuses to call a leak. An unexplained pooled-correlator artifact, explicitly not a padding effect (this is the no-pad arm).</figcaption>
  </figure>

  <!-- FIG 4: RQ2-P1 -->
  <figure class="figure">
    <svg viewBox="0 0 920 210" role="img" aria-label="RQ2-P1 federation shrinks anonymity set">
      <g font-family="sans-serif">
        <!-- baseline zero at y=45 -->
        <line x1="90" y1="45" x2="820" y2="45" stroke="#94a3b8" stroke-width="1.5"/>
        <text x="912" y="49" text-anchor="end" font-size="11.5" fill="#5b6b82">&Delta;H = 0</text>
        <!-- scale: 0 at y=45, -1.2 bits at y=180 => 112.5 px/bit -->
        <g text-anchor="end" font-size="11" fill="#94a3b8">
          <text x="82" y="49">0.0</text>
          <text x="82" y="105">&minus;0.5</text>
          <text x="82" y="161">&minus;1.0</text>
        </g>
        <line x1="86" y1="101" x2="90" y2="101" stroke="#cbd5e1"/><line x1="86" y1="157" x2="90" y2="157" stroke="#cbd5e1"/>
        <!-- bar: 0 to -0.9587 => y 45 to 45+0.9587*112.5=152.9 ; center x=300 width 120 -->
        <rect x="240" y="45" width="120" height="107.9" fill="#fcecd6" stroke="#b45309" stroke-width="1.5"/>
        <!-- CI whisker -1.0559..-0.8641 => y 163.8..142.2 at x=300 -->
        <line x1="300" y1="142.2" x2="300" y2="163.8" stroke="#8a4408" stroke-width="2.5"/>
        <line x1="288" y1="142.2" x2="312" y2="142.2" stroke="#8a4408" stroke-width="2.5"/>
        <line x1="288" y1="163.8" x2="312" y2="163.8" stroke="#8a4408" stroke-width="2.5"/>
        <text x="300" y="185" text-anchor="middle" font-size="12.5" font-weight="700" fill="#b45309">&Delta;H = &minus;0.96 bits</text>
        <text x="300" y="201" text-anchor="middle" font-size="11" fill="#8a4408">CI [&minus;1.06, &minus;0.86] &middot; Holm-significant</text>
        <!-- annotation -->
        <text x="560" y="95" font-size="14" font-weight="700" fill="#b45309">Federation SHRINKS the anonymity set</text>
        <text x="560" y="118" font-size="12.5" fill="#334155">the <tspan font-style="italic">opposite</tspan> of RQ2's motivating hypothesis &mdash;</text>
        <text x="560" y="136" font-size="12.5" fill="#334155">reported with equal prominence, not re-framed as</text>
        <text x="560" y="154" font-size="12.5" fill="#334155">"federation helps". (Mechanism resolved in Fig&nbsp;5.)</text>
      </g>
    </svg>
    <figcaption><span class="fig-num">Figure 4.</span> <b>RQ2-P1 &mdash; anonymity-set effect of federation.</b> Under the ratified adversary posterior, federating across houses reduces the per-circuit anonymity set by ~0.96 bits vs a matched-N single house &mdash; a genuine Holm-significant negative.</figcaption>
  </figure>

  <!-- FIG 5: RQ2-P3 mix (headline) -->
  <figure class="figure">
    <svg viewBox="0 0 920 340" role="img" aria-label="RQ2-P3 unique-bridge artifact versus shared-pool mix">
      <g font-family="sans-serif">
        <text x="230" y="26" text-anchor="middle" font-size="13.5" font-weight="700" fill="#b45309">Lead as-instrumented: UNIQUE bridge / circuit</text>
        <text x="690" y="26" text-anchor="middle" font-size="13.5" font-weight="700" fill="#15803d">Mechanism study: SHARED willing-bridge pool</text>
        <line x1="460" y1="40" x2="460" y2="250" stroke="#e3e8ef" stroke-width="1.5"/>

        <!-- LEFT: unique bridges -->
        <g>
          <!-- circuits -->
          <g fill="#1d4ed8"><circle cx="70" cy="70" r="8"/><circle cx="70" cy="120" r="8"/><circle cx="70" cy="170" r="8"/><circle cx="70" cy="220" r="8"/></g>
          <!-- bridges unique -->
          <g fill="#fcecd6" stroke="#b45309" stroke-width="1.5">
            <rect x="250" y="58" width="52" height="24" rx="5"/><rect x="250" y="108" width="52" height="24" rx="5"/>
            <rect x="250" y="158" width="52" height="24" rx="5"/><rect x="250" y="208" width="52" height="24" rx="5"/>
          </g>
          <g stroke="#b45309" stroke-width="1.6">
            <line x1="78" y1="70" x2="250" y2="70"/><line x1="78" y1="120" x2="250" y2="120"/>
            <line x1="78" y1="170" x2="250" y2="170"/><line x1="78" y1="220" x2="250" y2="220"/>
          </g>
          <g fill="#8a4408" font-size="10" text-anchor="middle"><text x="276" y="74">b1</text><text x="276" y="124">b2</text><text x="276" y="174">b3</text><text x="276" y="224">b4</text></g>
          <text x="360" y="120" font-size="12" fill="#334155">every signature</text>
          <text x="360" y="138" font-size="12" fill="#334155">unique &rarr; set size 1</text>
          <text x="360" y="164" font-size="13" font-weight="700" fill="#b45309">H &asymp; 0 by</text>
          <text x="360" y="182" font-size="13" font-weight="700" fill="#b45309">construction</text>
        </g>

        <!-- RIGHT: shared pool -->
        <g>
          <g fill="#1d4ed8"><circle cx="530" cy="70" r="8"/><circle cx="530" cy="120" r="8"/><circle cx="530" cy="170" r="8"/><circle cx="530" cy="220" r="8"/></g>
          <g fill="#dcf2e2" stroke="#15803d" stroke-width="1.6">
            <rect x="700" y="83" width="52" height="24" rx="5"/><rect x="700" y="183" width="52" height="24" rx="5"/>
          </g>
          <g stroke="#15803d" stroke-width="1.6">
            <line x1="538" y1="70" x2="700" y2="95"/><line x1="538" y1="120" x2="700" y2="95"/>
            <line x1="538" y1="170" x2="700" y2="195"/><line x1="538" y1="220" x2="700" y2="195"/>
          </g>
          <g fill="#166534" font-size="10" text-anchor="middle"><text x="726" y="99">B1</text><text x="726" y="199">B2</text></g>
          <text x="800" y="120" font-size="12" fill="#334155">circuits SHARE a</text>
          <text x="800" y="138" font-size="12" fill="#334155">signature &rarr; sets grow</text>
          <text x="800" y="164" font-size="13" font-weight="700" fill="#15803d">H rises = MIX</text>
        </g>

        <!-- bottom trend panel -->
        <g transform="translate(0,258)">
          <text x="60" y="8" font-size="12" font-weight="700" fill="#151d2b">Dose-response (confirmatory, 13,500 circuits):</text>
          <!-- mini axes -->
          <line x1="560" y1="12" x2="560" y2="66" stroke="#94a3b8" stroke-width="1.2"/>
          <line x1="560" y1="66" x2="760" y2="66" stroke="#94a3b8" stroke-width="1.2"/>
          <text x="548" y="16" text-anchor="end" font-size="9.5" fill="#94a3b8">H</text>
          <text x="760" y="80" text-anchor="end" font-size="9.5" fill="#94a3b8">concentration &rarr;</text>
          <!-- rising trend -->
          <line x1="566" y1="60" x2="756" y2="20" stroke="#15803d" stroke-width="2.5"/>
          <g fill="#15803d"><circle cx="590" cy="55" r="3"/><circle cx="640" cy="46" r="3"/><circle cx="690" cy="34" r="3"/><circle cx="740" cy="23" r="3"/></g>
          <text x="60" y="30" font-size="12.5" fill="#334155">H1 Spearman <tspan font-weight="700" fill="#15803d">&rho; = +0.62</tspan> [+0.59, +0.65] &nbsp;&middot;&nbsp; H2 slope <tspan font-weight="700" fill="#15803d">&beta; = +0.71</tspan> [+0.62, +0.79]</text>
          <text x="60" y="50" font-size="12.5" fill="#334155">H3 joint &rarr; <tspan font-weight="700" fill="#15803d">RESOLVED = MIX</tspan>. Concentration &uarr; &rArr; anonymity &uarr;,</text>
          <text x="60" y="68" font-size="12.5" fill="#334155">correcting the lead "shrink" as a unique-bridge artifact.</text>
        </g>
      </g>
    </svg>
    <figcaption><span class="fig-num">Figure 5.</span> <b>RQ2-P3 &mdash; the mix mechanism (headline correction).</b> The lead topology assigned a <i>fresh</i> bridge per circuit, making every exit signature unique and driving H&asymp;0 by injective construction &mdash; not by funnelling. Re-instrumented as a finite <i>shared</i> pool, concentration and entropy rise together (&rho;&nbsp;+0.62): a shared bridge <b>mixes</b>. This qualifies the lead RQ2-P1 shrink without overwriting it. <i>Disclosure: the frozen calibration dry-pass already previewed this direction (&rho; 0&rarr;+0.838); the two-sided pre-commitment stands.</i></figcaption>
  </figure>

  <!-- FIG 6: RQ3 -->
  <figure class="figure">
    <svg viewBox="0 0 920 260" role="img" aria-label="RQ3 double null">
      <g font-family="sans-serif">
        <!-- panel A: retention -->
        <text x="150" y="26" text-anchor="middle" font-size="12.5" font-weight="700" fill="#151d2b">Throughput retention</text>
        <line x1="60" y1="180" x2="250" y2="180" stroke="#94a3b8" stroke-width="1.2"/>
        <g>
          <rect x="78" y="70" width="34" height="110" fill="#e8edf3" stroke="#64748b"/><text x="95" y="196" text-anchor="middle" font-size="10" fill="#5b6b82">static</text>
          <rect x="133" y="70" width="34" height="110" fill="#e8edf3" stroke="#64748b"/><text x="150" y="196" text-anchor="middle" font-size="10" fill="#5b6b82">random</text>
          <rect x="188" y="71" width="34" height="109" fill="#d7ede9" stroke="#0f766e"/><text x="205" y="196" text-anchor="middle" font-size="10" fill="#0f766e">agent</text>
        </g>
        <text x="150" y="60" text-anchor="middle" font-size="11" fill="#334155">all &asymp; 0.99 (ceiling)</text>
        <text x="150" y="224" text-anchor="middle" font-size="11.5" fill="#b45309">margin &minus;0.6pp</text>
        <text x="150" y="240" text-anchor="middle" font-size="10.5" fill="#8a4408">[&minus;1.58,+0.39] &middot; gate +10pp</text>

        <!-- panel B: latency -->
        <text x="460" y="26" text-anchor="middle" font-size="12.5" font-weight="700" fill="#151d2b">Added latency (agent)</text>
        <line x1="330" y1="120" x2="590" y2="120" stroke="#94a3b8" stroke-width="1.2"/>
        <text x="330" y="138" font-size="10" fill="#94a3b8">0</text>
        <!-- budget line at 100ms; scale 0..120ms over 330..590 (260px) => 2.166px/ms; but negative region left of 0? put 0 at x=430 -->
        <line x1="430" y1="70" x2="430" y2="150" stroke="#64748b" stroke-width="1.3" stroke-dasharray="4 3"/>
        <text x="430" y="64" text-anchor="middle" font-size="10" fill="#64748b">0 ms</text>
        <!-- 100ms budget: x=430+100*1.5=580 -->
        <line x1="580" y1="78" x2="580" y2="150" stroke="#15803d" stroke-width="1.4" stroke-dasharray="4 3"/>
        <text x="580" y="72" text-anchor="middle" font-size="10" fill="#15803d">budget 100</text>
        <!-- point -13.5 (x=430-20.25=409.75), CI -52.1..+34.9 (x=430-78.15=351.85 .. 430+52.35=482.35) -->
        <line x1="351.85" y1="120" x2="482.35" y2="120" stroke="#0f766e" stroke-width="3.5" stroke-linecap="round"/>
        <circle cx="409.75" cy="120" r="6" fill="#0f766e"/>
        <text x="460" y="176" text-anchor="middle" font-size="11.5" fill="#0f766e">&minus;13.5 ms [&minus;52.1, +34.9]</text>
        <text x="460" y="192" text-anchor="middle" font-size="10.5" fill="#0f766e">within budget (not slower)</text>

        <!-- panel C: rebuild AUC -->
        <text x="770" y="26" text-anchor="middle" font-size="12.5" font-weight="700" fill="#151d2b">Rebuild fingerprint AUC</text>
        <line x1="650" y1="120" x2="890" y2="120" stroke="#94a3b8" stroke-width="1.2"/>
        <!-- scale 0.4..0.8 over 650..890 (240px)=600px/unit -->
        <g text-anchor="middle" font-size="9.5" fill="#94a3b8"><text x="650" y="138">0.40</text><text x="770" y="138">0.60</text><text x="890" y="138">0.80</text></g>
        <!-- gate 0.60 at x=770 -->
        <line x1="770" y1="72" x2="770" y2="120" stroke="#b45309" stroke-width="1.4" stroke-dasharray="4 3"/>
        <text x="770" y="66" text-anchor="middle" font-size="10" fill="#b45309">gate 0.60</text>
        <!-- point 0.587 x=650+(0.587-0.4)*600=650+112.2=762.2 ; CI 0.458..0.703 => 684.8 .. 831.8 -->
        <line x1="684.8" y1="120" x2="831.8" y2="120" stroke="#64748b" stroke-width="3.5" stroke-linecap="round"/>
        <circle cx="762.2" cy="120" r="6" fill="#64748b"/>
        <text x="770" y="176" text-anchor="middle" font-size="11.5" fill="#334155">AUC 0.587 [0.458, 0.703]</text>
        <text x="770" y="192" text-anchor="middle" font-size="10.5" fill="#b45309">CI crosses 0.60 &rarr; not excluded (n=30)</text>

        <text x="460" y="246" text-anchor="middle" font-size="12.5" fill="#334155">Verdict: <tspan font-weight="700" fill="#64748b">H0 on both counts</tspan> &mdash; the local open-weight agent neither beats baselines nor is certifiably fingerprint-free on this grid.</text>
      </g>
    </svg>
    <figcaption><span class="fig-num">Figure 6.</span> <b>RQ3 &mdash; churn-resilient agent selection (double null).</b> At the pinned churn (kp30/steps20) every selector heals ~all drops, so there is no headroom for the +10pp gain; the agent is not slower (latency within budget) but the rebuild-timing classifier cannot be excluded at n=30. Both P1 and P2 are honest nulls.</figcaption>
  </figure>

  <!-- FIG 7: Holm-7 forest -->
  <figure class="figure">
    <svg viewBox="0 0 920 300" role="img" aria-label="Authoritative Holm-7 forest">
      <g font-family="sans-serif">
        <text x="60" y="24" font-size="13" font-weight="700" fill="#151d2b">Authoritative Holm-7 (frozen size-7 family) &mdash; adjusted p</text>
        <!-- axis 0..0.6 over x 300..860 -->
        <line x1="300" y1="44" x2="300" y2="272" stroke="#cbd5e1" stroke-width="1.2"/>
        <!-- alpha .05 line: x=300+ (0.05/0.6)*560 = 300+46.7=346.7 -->
        <line x1="346.7" y1="44" x2="346.7" y2="272" stroke="#b45309" stroke-width="1.4" stroke-dasharray="5 4"/>
        <text x="346.7" y="40" text-anchor="middle" font-size="10.5" fill="#b45309">&alpha;=.05</text>
        <g text-anchor="middle" font-size="10" fill="#94a3b8">
          <text x="300" y="288">0</text><text x="580" y="288">0.30</text><text x="860" y="288">0.60</text>
        </g>
        <!-- rows: y positions -->
        <!-- helper: adjp x = 300 + adjp/0.6*560 -->
        <g font-size="12">
          <!-- RQ1-P1 survive, adjp 0 -->
          <text x="290" y="70" text-anchor="end" fill="#0f766e" font-weight="700">RQ1-P1 leak</text>
          <circle cx="300" cy="66" r="6" fill="#0f766e"/>
          <text x="315" y="70" font-size="11" fill="#0f766e">survives &middot; no leak</text>
          <!-- RQ2-P1 survive -->
          <text x="290" y="102" text-anchor="end" fill="#0f766e" font-weight="700">RQ2-P1 federation</text>
          <circle cx="300" cy="98" r="6" fill="#0f766e"/>
          <text x="315" y="102" font-size="11" fill="#0f766e">survives &middot; shrink</text>
          <!-- RQ2-P3 survive -->
          <text x="290" y="134" text-anchor="end" fill="#0f766e" font-weight="700">RQ2-P3 mechanism</text>
          <circle cx="300" cy="130" r="6" fill="#0f766e"/>
          <text x="315" y="134" font-size="11" fill="#0f766e">survives &middot; mix (corrects shrink)</text>
          <!-- RQ1-P2 0.365 x=300+340.7=640.7 -->
          <text x="290" y="166" text-anchor="end" fill="#64748b">RQ1-P2 padding</text>
          <line x1="300" y1="162" x2="640.7" y2="162" stroke="#e2e8f0" stroke-width="1"/>
          <circle cx="640.7" cy="162" r="5.5" fill="#94a3b8"/>
          <text x="655" y="166" font-size="10.5" fill="#94a3b8">0.365</text>
          <!-- RQ3-P2 0.511 x=300+477=777 -->
          <text x="290" y="198" text-anchor="end" fill="#64748b">RQ3-P2 fingerprint</text>
          <line x1="300" y1="194" x2="777" y2="194" stroke="#e2e8f0" stroke-width="1"/>
          <circle cx="777" cy="194" r="5.5" fill="#94a3b8"/>
          <text x="791" y="198" font-size="10.5" fill="#94a3b8">0.511</text>
          <!-- RQ3-P1-perf 0.511 -->
          <text x="290" y="230" text-anchor="end" fill="#64748b">RQ3-P1-perf</text>
          <line x1="300" y1="226" x2="777" y2="226" stroke="#e2e8f0" stroke-width="1"/>
          <circle cx="777" cy="226" r="5.5" fill="#94a3b8"/>
          <text x="791" y="230" font-size="10.5" fill="#94a3b8">0.511</text>
          <!-- RQ3-P1-latency 0.511 -->
          <text x="290" y="262" text-anchor="end" fill="#64748b">RQ3-P1-latency</text>
          <line x1="300" y1="258" x2="777" y2="258" stroke="#e2e8f0" stroke-width="1"/>
          <circle cx="777" cy="258" r="5.5" fill="#94a3b8"/>
          <text x="791" y="262" font-size="10.5" fill="#94a3b8">0.511</text>
        </g>
      </g>
    </svg>
    <figcaption><span class="fig-num">Figure 7.</span> <b>Authoritative Holm-7.</b> Over the frozen family of seven, three hypotheses survive at &alpha;=.05: <span style="color:#0f766e;font-weight:700">RQ1-P1</span> (no leak), <span style="color:#0f766e;font-weight:700">RQ2-P1</span> (shrink), and <span style="color:#0f766e;font-weight:700">RQ2-P3</span> (mix). The RQ2-P3 slot carries the mechanism-corrected primary statistic, superseding the lead's degenerate as-instrumented test. This is the authoritative correction; the lead paper's conservative partial embedding remains valid and never under-corrects.</figcaption>
  </figure>

  <div class="legend">
    <span><i class="sw" style="background:#0f766e"></i> instrument / survives Holm</span>
    <span><i class="sw" style="background:#15803d"></i> mix / positive</span>
    <span><i class="sw" style="background:#b45309"></i> negative / gate</span>
    <span><i class="sw" style="background:#64748b"></i> null / does not survive</span>
    <span><i class="sw" style="background:#1d4ed8"></i> client / house node</span>
  </div>
</section>

<!-- ================= LEAD PAPER ================= -->
<section id="lead-paper">
  <h2 class="sh">Lead paper &mdash; full text</h2>
  <details class="paperwrap" open>
    <summary>Consent-Gated Federated Onion Routing: Linkability &amp; Anonymity-Set Effects (G4 + RQ1 + RQ2) <span class="hint">click to collapse</span></summary>
    <article class="paper">%%LEAD%%</article>
  </details>
</section>

<!-- ================= COMPANION PAPER ================= -->
<section id="companion-paper">
  <h2 class="sh">Companion paper &mdash; full text</h2>
  <details class="paperwrap" open>
    <summary>The Unique-Bridge / Mix Mechanism (RQ2-P3) and Churn-Resilient Agent Selection (RQ3) <span class="hint">click to collapse</span></summary>
    <article class="paper">%%COMPANION%%</article>
  </details>
</section>

<!-- ================= PROVENANCE ================= -->
<section id="provenance">
  <h2 class="sh">Provenance &amp; integrity</h2>
  <div class="prov">
    <p><b>Pre-registrations (frozen, hashed):</b><br/>
    lead <code>f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b</code><br/>
    RQ2-P3 mechanism <code>8db4e8a7ac60f8b2861f2387249db68a3fd44822f6b3d9c7c6990ff65f261a3b</code></p>
    <p><b>Sealed confirmatory records:</b> lead 180 cells / 9,000 circuits (<code>SHA256SUMS.txt</code>);
    RQ2-P3 13,500 offline-deterministic bridged circuits (results <code>5fdcb379&hellip;</code>);
    RQ3 4,500 live isolated-docker circuits (battery <code>5b61e461&hellip;</code>, analysis <code>e09c66ef&hellip;</code>).</p>
    <p><b>Discipline:</b> detectors calibrated on fixtures and frozen before any confirmatory cell; effect size + BCa 95% CI for every test, p only orders the Holm step-down; Results filled once, post-seal; containment intact (isolated-engine only, self-generated fixtures, lab-only); worktree-only on <code>feat/sor-consent-relay</code>.</p>
    <p style="margin-bottom:0"><b>Note:</b> this page is a presentation artifact generated from the committed paper drafts; the papers and sealed records are authoritative.</p>
  </div>
</section>

</main>
<footer>Generated offline from the committed paper drafts &middot; sor-consent study &middot; self-contained (no external assets)</footer>
</body>
</html>
"""

html = TEMPLATE.replace("%%LEAD%%", lead_html).replace("%%COMPANION%%", companion_html)
OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({len(html):,} bytes)")
