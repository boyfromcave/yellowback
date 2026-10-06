/* Yellowback site — progressive enhancement only. Every page reads fine without it. */
(function () {
  "use strict";
  document.documentElement.classList.remove("no-js");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SVGNS = "http://www.w3.org/2000/svg";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }
  function rng(seed) { // mulberry32: deterministic so the map looks the same on every visit
    return function () {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var fmtUSD = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  var fmtUSD2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 });
  var fmtNum = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

  /* ---------- nav ---------- */
  var toggle = $(".nav-toggle");
  if (toggle) toggle.addEventListener("click", function () {
    var links = $(".nav-links");
    var open = links.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  /* ---------- fiber / transit backdrop ----------
     Subway-map routes: horizontal runs joined by 45° bends, with a light pulse travelling
     along each one. <div class="fiber" data-seed="7" data-lines="6"></div> */
  var LINE_COLORS = ["#f7b733", "#45e0ff", "#f56733", "#ff5fa2", "#4dffb0", "#ffe38a"];
  $$(".fiber").forEach(function (host) {
    var r = rng(+host.dataset.seed || 1);
    var n = +host.dataset.lines || 6;
    var W = 1400, H = +host.dataset.h || 800;
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "xMidYMid slice", "aria-hidden": "true" });
    var defs = el("defs", {});
    var f = el("filter", { id: "glow", x: "-20%", y: "-20%", width: "140%", height: "140%" });
    f.appendChild(el("feGaussianBlur", { stdDeviation: "3", result: "b" }));
    var m = el("feMerge", {});
    m.appendChild(el("feMergeNode", { in: "b" }));
    m.appendChild(el("feMergeNode", { in: "SourceGraphic" }));
    f.appendChild(m); defs.appendChild(f); svg.appendChild(defs);
    for (var i = 0; i < n; i++) {
      var color = LINE_COLORS[i % LINE_COLORS.length];
      var y = 60 + r() * (H - 120);
      var x = -40;
      var d = "M" + x + "," + y.toFixed(0);
      var stations = [];
      while (x < W + 40) {
        var run = 120 + r() * 260;
        x += run;
        d += " H" + x.toFixed(0);
        stations.push([x, y]);
        var dy = (r() < 0.5 ? -1 : 1) * (40 + r() * 120);
        if (y + dy < 30 || y + dy > H - 30) dy = -dy;
        x += Math.abs(dy); y += dy;
        d += " L" + x.toFixed(0) + "," + y.toFixed(0);
      }
      svg.appendChild(el("path", { d: d, class: "route", stroke: color }));
      if (!reduce) {
        var p = el("path", { d: d, class: "pulse " + (i % 2 ? "slow " : "") + ["", "d2", "d3"][i % 3], stroke: color, pathLength: "1440" });
        svg.appendChild(p);
      }
      stations.forEach(function (s, j) {
        if (j % 2 === 0 && s[0] > 0 && s[0] < W) svg.appendChild(el("circle", { cx: s[0], cy: s[1], r: 5, class: "node", stroke: color }));
      });
    }
    host.appendChild(svg);
  });

  /* ---------- reveal on scroll ---------- */
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("in"); scramble(e.target); io.unobserve(e.target); }
    });
  }, { threshold: 0.12 }) : null;
  $$(".reveal").forEach(function (n) { io ? io.observe(n) : n.classList.add("in"); });

  /* ---------- decrypt-style text scramble ---------- */
  var GLYPHS = "0123456789abcdef#$%&*+<>/\\|";
  function scramble(root) {
    var targets = root.matches && root.matches("[data-scramble]") ? [root] : $$("[data-scramble]", root);
    targets.forEach(function (t) {
      if (t.dataset.done || reduce) return;
      t.dataset.done = "1";
      var final = t.textContent, frame = 0, total = 22;
      (function tick() {
        var out = "";
        for (var i = 0; i < final.length; i++) {
          if (final[i] === " " || i < (frame / total) * final.length) out += final[i];
          else out += GLYPHS[(Math.random() * GLYPHS.length) | 0];
        }
        t.textContent = out;
        if (frame++ < total) requestAnimationFrame(tick); else t.textContent = final;
      })();
    });
  }
  $$(".hero [data-scramble]").forEach(scramble);

  /* ---------- hex rain behind the manifesto ---------- */
  $$(".hex").forEach(function (h) {
    var r = rng(1993), s = "";
    for (var i = 0; i < 2600; i++) s += "0123456789abcdef"[(r() * 16) | 0] + (i % 64 === 63 ? "\n" : "");
    h.textContent = s;
  });

  /* ---------- footer: a real SHA-256, because we can ---------- */
  var hashEl = $("[data-pagehash]");
  if (hashEl && window.crypto && crypto.subtle && window.fetch) {
    fetch(location.href).then(function (r) { return r.arrayBuffer(); })
      .then(function (buf) { return crypto.subtle.digest("SHA-256", buf); })
      .then(function (d) {
        hashEl.textContent = "sha256(" + (location.pathname.split("/").pop() || "index.html") + ") = " +
          Array.prototype.map.call(new Uint8Array(d), function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
        hashEl.title = "SHA-256 of the HTML your browser just loaded. Don't trust, verify.";
      })
      .catch(function () { /* file:// or offline: leave it blank */ });
  }

  /* ---------- transit-line stepper: Lock → Mint → Spend → Unlock ---------- */
  var metro = $(".metro");
  if (metro) {
    var steps = JSON.parse($("#metro-steps").textContent);
    var stations = $$(".station", metro);
    var tabs = $$(".metro-tabs button", metro);
    var panel = $(".metro-panel", metro);
    var cur = 0, timer = null;
    function show(i) {
      cur = i;
      stations.forEach(function (s, j) { s.classList.toggle("active", j === i); });
      tabs.forEach(function (b, j) { b.setAttribute("aria-selected", j === i ? "true" : "false"); });
      var s = steps[i];
      $(".step-no", panel).textContent = "STOP " + (i + 1) + " / " + steps.length + " · " + s.code;
      $("h3", panel).textContent = s.title;
      $("p", panel).innerHTML = s.body;
      $(".viz", panel).innerHTML = $("#viz-" + i).innerHTML;
    }
    function go(i) { show(i); restart(); }
    function restart() {
      if (reduce) return;
      clearInterval(timer);
      timer = setInterval(function () { show((cur + 1) % steps.length); }, 6000);
    }
    stations.forEach(function (s, j) {
      s.addEventListener("click", function () { go(j); });
      s.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(j); } });
    });
    tabs.forEach(function (b, j) { b.addEventListener("click", function () { go(j); }); });
    metro.addEventListener("mouseenter", function () { clearInterval(timer); });
    metro.addEventListener("mouseleave", restart);
    show(0); restart();
  }

  /* ---------- mint calculator ----------
     Parameters from docs/plans/yellowback-v2-development-plan.md §3.1 (unchanged in v3):
     term-class base ratios 500 / 400 / 300 %, volatility multiplier 1×–3×, claim threshold 110 %,
     enforcement fee max(0.5 YEC, 0.25 % of collateral), MIN_MINT $100, MAX_MINT $10,000. */
  var calc = $("#calc");
  if (calc) {
    var CLASSES = { A: { ratio: 5, name: "30–90 days" }, B: { ratio: 4, name: "90 days – 1 year" }, C: { ratio: 3, name: "1–5 years" } };
    var state = { yec: 10000, price: 0.4, cls: "B", sigma: 1 };
    var yecIn = $("#c-yec"), yecRange = $("#c-yec-range"), priceIn = $("#c-price"), sigmaIn = $("#c-sigma");
    function sync(from) {
      if (from === "yec") yecRange.value = Math.min(+yecIn.value, +yecRange.max);
      if (from === "range") yecIn.value = yecRange.value;
      state.yec = Math.max(0, +yecIn.value || 0);
      state.price = Math.max(0, +priceIn.value || 0);
      state.sigma = +sigmaIn.value;
      render();
    }
    function render() {
      var c = CLASSES[state.cls];
      var ratio = c.ratio * state.sigma;
      var value = state.yec * state.price;
      var yed = value / ratio;
      var fee = Math.max(0.5, state.yec * 0.0025);
      var claimPrice = state.price ? (1.1 * yed) / state.yec : 0;
      var drop = state.price ? 1 - claimPrice / state.price : 0;
      $("#c-sigma-out").textContent = state.sigma.toFixed(2) + "×";
      $("#c-yec-out").textContent = fmtNum.format(state.yec) + " YEC";
      $("#r-yed").firstChild.nodeValue = fmtUSD.format(Math.floor(yed)).replace("$", "");
      $("#r-value").textContent = fmtUSD.format(value);
      $("#r-ratio").textContent = Math.round(ratio * 100) + "%";
      $("#r-share").textContent = "1 / " + fmtNum.format(ratio);
      $("#r-fee").textContent = fmtNum.format(fee) + " YEC";
      $("#r-claim").textContent = fmtUSD2.format(claimPrice);
      $("#r-drop").textContent = Math.round(drop * 100) + "%";
      $("#r-term").textContent = c.name;
      var pct = Math.max(0, Math.min(100, 100 / ratio));
      $(".seg-yed").style.width = pct + "%";
      $(".seg-yed").textContent = pct > 14 ? "YED " + Math.round(pct) + "%" : "";
      $(".seg-buffer").style.width = 100 - pct + "%";
      $(".seg-buffer").textContent = "safety buffer " + Math.round(100 - pct) + "%";
      var w = $("#c-warn");
      if (yed > 0 && yed < 100) { w.textContent = "Below the $100 minimum per mint. Lock a little more YEC, or pick a longer term."; w.classList.add("show"); }
      else if (yed > 10000) { w.textContent = "One vault mints at most $10,000. You could open " + Math.ceil(yed / 10000) + " vaults to mint " + fmtUSD.format(Math.floor(yed)) + " in total."; w.classList.add("show"); }
      else w.classList.remove("show");
    }
    yecIn.addEventListener("input", function () { sync("yec"); });
    yecRange.addEventListener("input", function () { sync("range"); });
    priceIn.addEventListener("input", function () { sync(); });
    sigmaIn.addEventListener("input", function () { sync(); });
    $$("#c-term button").forEach(function (b) {
      b.addEventListener("click", function () {
        state.cls = b.dataset.cls;
        $$("#c-term button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        render();
      });
    });
    sync();
  }

  /* ---------- sell vs. Yellowback ---------- */
  var vs = $("#versus");
  if (vs) {
    var YEC = 10000, P = 0.4, RATIO = 4; // class B example at 1× volatility
    var V = YEC * P, MINT = V / RATIO;
    var mv = $("#vs-move");
    function vsRender() {
      var pctMove = +mv.value;               // −80 … +400
      var m = 1 + pctMove / 100;
      var end = YEC * P * m;
      $("#vs-move-out").textContent = (pctMove > 0 ? "+" : "") + pctMove + "%";
      var max = Math.max(V, end, 1);
      function bar(id, val, label) {
        $("#" + id + " .fill").style.width = (100 * val) / max + "%";
        $("#" + id + " b").textContent = label;
      }
      bar("vs-sell-usd", V, fmtUSD.format(V));
      bar("vs-sell-yec", 0, "0 YEC · $0");
      bar("vs-yb-usd", MINT, fmtUSD.format(MINT) + " YED");
      bar("vs-yb-yec", end, fmtNum.format(YEC) + " YEC · " + fmtUSD.format(end));
      var note = $("#vs-verdict");
      var claimM = 1.1 / RATIO;
      if (m < claimM) {
        note.innerHTML = "<b>Deep crash.</b> At this price the vault is below 110% of its debt. Redeem as soon as it unlocks: after the 30-day grace period YED holders could claim it, paying off the debt — and everything above the debt plus a 10% margin still comes back to you.";
      } else if (pctMove > 0) {
        note.innerHTML = "<b>You kept the upside.</b> The seller missed " + fmtUSD.format(end - V) + " of gains. You had " + fmtUSD.format(MINT) + " to use the whole time, and return the same " + fmtUSD.format(MINT) + " of YED to unlock all " + fmtNum.format(YEC) + " YEC.";
      } else if (pctMove < 0) {
        note.innerHTML = "<b>Price fell, vault still healthy.</b> You still owe only " + fmtUSD.format(MINT) + " of YED — the debt is in dollars and doesn't grow. Return it at unlock and your " + fmtNum.format(YEC) + " YEC are yours again, ready for the recovery.";
      } else {
        note.innerHTML = "<b>Flat market.</b> Return " + fmtUSD.format(MINT) + " of YED at unlock and every one of your " + fmtNum.format(YEC) + " YEC comes home.";
      }
    }
    mv.addEventListener("input", vsRender);
    vsRender();
  }

  /* ---------- certificate tilt ---------- */
  $$("[data-tilt]").forEach(function (card) {
    if (reduce || !window.matchMedia("(hover: hover)").matches) return;
    card.addEventListener("mousemove", function (e) {
      var r = card.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      card.style.transform = "rotateY(" + (x * 10).toFixed(2) + "deg) rotateX(" + (-y * 8).toFixed(2) + "deg)";
    });
    card.addEventListener("mouseleave", function () { card.style.transform = ""; });
  });

  /* ---------- docs: highlight the section in view ---------- */
  var docNav = $(".docs nav");
  if (docNav && io) {
    var links = $$("a[href^='#']", docNav);
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle("active", a.getAttribute("href") === "#" + e.target.id); });
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    $$(".docs article h2[id]").forEach(function (h) { spy.observe(h); });
  }

  var y = $("[data-year]");
  if (y) y.textContent = new Date().getFullYear();
})();
