/* QuizMaster lightweight SVG charts (no third-party libraries, CSP-safe).
   Usage: <div class="chart" data-chart="line|bar|hbar|donut" data-series='{"labels":[],"values":[]}'
          data-max="100" data-suffix="%" aria-label="..."></div>
   All data is rendered from the server (real database values). When there is no
   data the element shows an honest empty state instead of placeholder numbers. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var PALETTE = ["#6366F1", "#06B6D4", "#8B5CF6", "#14B8A6", "#F97362", "#F59E0B", "#EC4899", "#3B82F6", "#22C55E", "#A855F7"];
  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fmt(v, suffix) { var r = Math.round(v * 10) / 10; return (r % 1 === 0 ? r.toFixed(0) : r.toFixed(1)) + (suffix || ""); }
  function niceMax(v) { if (v <= 0) return 1; var p = Math.pow(10, Math.floor(Math.log10(v))); var n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; }

  function tooltip(host) {
    var tip = document.createElement("div"); tip.className = "chart-tooltip"; tip.hidden = true; host.appendChild(tip);
    return {
      show: function (html, evt) {
        tip.innerHTML = html; tip.hidden = false;
        var r = host.getBoundingClientRect();
        var x = (evt.touches ? evt.touches[0].clientX : evt.clientX) - r.left, y = (evt.touches ? evt.touches[0].clientY : evt.clientY) - r.top;
        tip.style.left = Math.min(Math.max(x - tip.offsetWidth / 2, 0), r.width - tip.offsetWidth) + "px";
        tip.style.top = Math.max(y - tip.offsetHeight - 12, 0) + "px";
      },
      hide: function () { tip.hidden = true; }
    };
  }
  function empty(host, msg) {
    host.innerHTML = '<div class="chart-empty">' + esc(msg || host.getAttribute("data-empty") || "No data yet.") + "</div>";
  }
  function gradient(svg, id, c1, c2, vertical) {
    var defs = svg.querySelector("defs") || el("defs", {}, svg);
    var g = el("linearGradient", { id: id, x1: "0", y1: "0", x2: vertical ? "0" : "1", y2: vertical ? "1" : "0" }, defs);
    el("stop", { offset: "0%", "stop-color": c1 }, g); el("stop", { offset: "100%", "stop-color": c2 }, g);
    return "url(#" + id + ")";
  }
  var uid = 0;

  function line(host, d) {
    var W = Math.max(host.clientWidth, 280), H = parseInt(host.getAttribute("data-height"), 10) || 240;
    var m = { t: 16, r: 14, b: 34, l: 38 };
    var vals = d.values, n = vals.length, suffix = host.getAttribute("data-suffix") || "";
    var max = parseFloat(host.getAttribute("data-max")) || niceMax(Math.max.apply(null, vals.concat([1])));
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": host.getAttribute("aria-label") || "Line chart" });
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var x = function (i) { return m.l + (n === 1 ? iw / 2 : (i * iw) / (n - 1)); };
    var y = function (v) { return m.t + ih - (v / max) * ih; };
    var grid = el("g", { class: "grid" }, svg), axis = el("g", { class: "axis" }, svg);
    for (var k = 0; k <= 4; k++) {
      var gv = (max * k) / 4;
      el("line", { x1: m.l, x2: W - m.r, y1: y(gv), y2: y(gv) }, grid);
      el("text", { x: m.l - 8, y: y(gv) + 4, "text-anchor": "end" }, axis).textContent = fmt(gv, suffix);
    }
    var step = Math.ceil(n / Math.max(1, Math.floor(iw / 70)));
    d.labels.forEach(function (lab, i) { if (i % step === 0 || i === n - 1) el("text", { x: x(i), y: H - 10, "text-anchor": "middle" }, axis).textContent = lab; });
    var id = "lg" + (++uid);
    var stroke = gradient(svg, id, "#6366F1", "#06B6D4", false);
    var fill = gradient(svg, id + "f", "rgba(99,102,241,.28)", "rgba(6,182,212,0)", true);
    if (d.target != null) {
      el("line", { x1: m.l, x2: W - m.r, y1: y(d.target), y2: y(d.target), stroke: "#F97362", "stroke-dasharray": "5 5", "stroke-width": 1.5 }, svg);
      el("text", { x: W - m.r, y: y(d.target) - 6, "text-anchor": "end", fill: "#F97362", "font-size": 11, "font-weight": 700 }, svg).textContent = d.targetLabel || "Target";
    }
    var pts = vals.map(function (v, i) { return [x(i), y(v)]; });
    var path = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
    if (n > 1) el("path", { d: path + " L" + x(n - 1) + " " + (m.t + ih) + " L" + x(0) + " " + (m.t + ih) + " Z", fill: fill }, svg);
    var p = el("path", { d: path, fill: "none", stroke: stroke, "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round" }, svg);
    host.innerHTML = ""; host.appendChild(svg);
    if (n > 1 && p.getTotalLength && document.documentElement.getAttribute("data-motion") !== "reduce") {
      var L = p.getTotalLength(); p.style.strokeDasharray = L; p.style.strokeDashoffset = L;
      p.getBoundingClientRect(); p.style.transition = "stroke-dashoffset 1.1s cubic-bezier(.22,1,.36,1)"; p.style.strokeDashoffset = "0";
    }
    var tip = tooltip(host);
    pts.forEach(function (pt, i) {
      var c = el("circle", { cx: pt[0], cy: pt[1], r: 4.5, fill: "var(--surface)", stroke: "#6366F1", "stroke-width": 2.5, tabindex: 0 }, svg);
      var show = function (e) { c.setAttribute("r", 6.5); tip.show("<b>" + esc(fmt(vals[i], suffix)) + "</b><br>" + esc((d.tips && d.tips[i]) || d.labels[i]), e); };
      c.addEventListener("mouseenter", show); c.addEventListener("mousemove", show);
      c.addEventListener("mouseleave", function () { c.setAttribute("r", 4.5); tip.hide(); });
      c.addEventListener("focus", function () { var r = c.getBoundingClientRect(); show({ clientX: r.left + 4, clientY: r.top }); });
      c.addEventListener("blur", tip.hide);
    });
  }

  function bar(host, d, horizontal) {
    var n = d.values.length, suffix = host.getAttribute("data-suffix") || "";
    var max = parseFloat(host.getAttribute("data-max")) || niceMax(Math.max.apply(null, d.values.concat([1])));
    var colors = d.colors || [];
    var W = Math.max(host.clientWidth, 280);
    var svg, tip;
    if (horizontal) {
      var rowH = 34, lw = Math.min(150, W * 0.35), H = n * rowH + 10;
      svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": host.getAttribute("aria-label") || "Bar chart" });
      var iw = W - lw - 52;
      d.values.forEach(function (v, i) {
        var yy = i * rowH + 6;
        var lab = el("text", { x: lw - 10, y: yy + 16, "text-anchor": "end", class: "axis" }, svg);
        lab.setAttribute("fill", "var(--ink-2)"); lab.setAttribute("font-size", "12"); lab.setAttribute("font-weight", "600");
        lab.textContent = d.labels[i].length > 22 ? d.labels[i].slice(0, 21) + "…" : d.labels[i];
        el("rect", { x: lw, y: yy + 4, width: iw, height: 16, rx: 8, fill: "var(--surface-3)" }, svg);
        var r = el("rect", { x: lw, y: yy + 4, width: Math.max(4, (v / max) * iw), height: 16, rx: 8, fill: colors[i] || gradient(svg, "hb" + (++uid), PALETTE[i % PALETTE.length], PALETTE[(i + 1) % PALETTE.length], false), class: "bar" }, svg);
        el("text", { x: lw + iw + 8, y: yy + 17, class: "value-label" }, svg).textContent = fmt(v, suffix);
        r.__tip = "<b>" + esc(d.labels[i]) + "</b><br>" + esc(fmt(v, suffix)) + (d.tips ? "<br>" + esc(d.tips[i]) : "");
      });
    } else {
      var H2 = parseInt(host.getAttribute("data-height"), 10) || 240, m = { t: 18, r: 10, b: 38, l: 38 };
      svg = el("svg", { viewBox: "0 0 " + W + " " + H2, role: "img", "aria-label": host.getAttribute("aria-label") || "Bar chart" });
      var iw2 = W - m.l - m.r, ih = H2 - m.t - m.b, slot = iw2 / n, bw = Math.min(46, slot * 0.62);
      var grid = el("g", { class: "grid" }, svg), axis = el("g", { class: "axis" }, svg);
      for (var k = 0; k <= 4; k++) {
        var gy = m.t + ih - (ih * k) / 4;
        el("line", { x1: m.l, x2: W - m.r, y1: gy, y2: gy }, grid);
        el("text", { x: m.l - 8, y: gy + 4, "text-anchor": "end" }, axis).textContent = fmt((max * k) / 4, suffix);
      }
      d.values.forEach(function (v, i) {
        var h = Math.max(2, (v / max) * ih), xx = m.l + i * slot + (slot - bw) / 2;
        var fill = colors[i] || gradient(svg, "vb" + (++uid), PALETTE[i % PALETTE.length], PALETTE[(i + 2) % PALETTE.length], true);
        var r = el("rect", { x: xx, y: m.t + ih - h, width: bw, height: h, rx: Math.min(10, bw / 3), fill: fill, class: "bar" }, svg);
        if (n <= 12) el("text", { x: xx + bw / 2, y: m.t + ih - h - 6, "text-anchor": "middle", class: "value-label" }, svg).textContent = fmt(v, suffix);
        var lab = d.labels[i]; if (lab.length > 12) lab = lab.slice(0, 11) + "…";
        el("text", { x: xx + bw / 2, y: H2 - 14, "text-anchor": "middle" }, axis).textContent = lab;
        r.__tip = "<b>" + esc(d.labels[i]) + "</b><br>" + esc(fmt(v, suffix)) + (d.tips ? "<br>" + esc(d.tips[i]) : "");
      });
    }
    host.innerHTML = ""; host.appendChild(svg);
    tip = tooltip(host);
    Array.prototype.forEach.call(svg.querySelectorAll(".bar"), function (r) {
      r.addEventListener("mousemove", function (e) { tip.show(r.__tip, e); });
      r.addEventListener("mouseleave", tip.hide);
    });
  }

  function donut(host, d) {
    var total = d.values.reduce(function (a, b) { return a + b; }, 0);
    if (!total) return empty(host);
    var S = 200, R = 80, T = 26, cx = S / 2, cy = S / 2;
    var svg = el("svg", { viewBox: "0 0 " + S + " " + S, role: "img", "aria-label": host.getAttribute("aria-label") || "Donut chart", style: "max-width:220px;display:block;margin:0 auto" });
    var a0 = -Math.PI / 2, tip;
    var arcs = [];
    d.values.forEach(function (v, i) {
      if (!v) return;
      var a1 = a0 + (v / total) * Math.PI * 2 - (v === total ? 0.0001 : 0);
      var large = a1 - a0 > Math.PI ? 1 : 0;
      var p = function (a, r) { return (cx + r * Math.cos(a)).toFixed(2) + " " + (cy + r * Math.sin(a)).toFixed(2); };
      var path = "M" + p(a0, R) + " A" + R + " " + R + " 0 " + large + " 1 " + p(a1, R) + " L" + p(a1, R - T) + " A" + (R - T) + " " + (R - T) + " 0 " + large + " 0 " + p(a0, R - T) + " Z";
      var arc = el("path", { d: path, fill: (d.colors && d.colors[i]) || PALETTE[i % PALETTE.length], class: "bar" }, svg);
      arc.__tip = "<b>" + esc(d.labels[i]) + "</b><br>" + v + " (" + fmt((v / total) * 100, "%") + ")";
      arcs.push(arc);
      a0 = a1;
    });
    var c = el("text", { x: cx, y: cy - 2, "text-anchor": "middle", "font-size": 30, "font-weight": 800, fill: "var(--ink)", "font-family": "var(--font-display)" }, svg);
    c.textContent = d.center != null ? d.center : total;
    el("text", { x: cx, y: cy + 20, "text-anchor": "middle", "font-size": 11, fill: "var(--muted)", "font-weight": 600 }, svg).textContent = d.centerLabel || "total";
    host.innerHTML = ""; host.appendChild(svg);
    var legend = document.createElement("div"); legend.className = "legend"; legend.style.justifyContent = "center";
    legend.innerHTML = d.labels.map(function (l, i) { return '<span><i style="background:' + ((d.colors && d.colors[i]) || PALETTE[i % PALETTE.length]) + '"></i>' + esc(l) + " · " + d.values[i] + "</span>"; }).join("");
    host.appendChild(legend);
    tip = tooltip(host);
    arcs.forEach(function (a) { a.addEventListener("mousemove", function (e) { tip.show(a.__tip, e); }); a.addEventListener("mouseleave", tip.hide); });
  }

  function render(host) {
    var d;
    try { d = JSON.parse(host.getAttribute("data-series") || "{}"); } catch (e) { return empty(host, "Chart data could not be read."); }
    if (!d || !d.values || !d.values.length) return empty(host);
    var type = host.getAttribute("data-chart");
    if (type === "line") line(host, d);
    else if (type === "bar") bar(host, d, false);
    else if (type === "hbar") bar(host, d, true);
    else if (type === "donut") donut(host, d);
  }
  function renderAll() { Array.prototype.forEach.call(document.querySelectorAll("[data-chart]"), render); }
  window.QMCharts = { render: render, renderAll: renderAll };
  renderAll();
  var lastW = window.innerWidth, t;
  window.addEventListener("resize", function () {
    clearTimeout(t);
    t = setTimeout(function () { if (Math.abs(window.innerWidth - lastW) > 40) { lastW = window.innerWidth; renderAll(); } }, 250);
  });
})();
