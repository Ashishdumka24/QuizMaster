/* QuizMaster core UI behaviours (no inline scripts — CSP script-src 'self').
   Every interactive feature degrades gracefully: forms and links still work
   without JavaScript; this file only enhances them. */
(function () {
  "use strict";
  var root = document.documentElement;
  var QM = (window.QM = window.QM || {});
  var $ = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };
  QM.$ = $; QM.$$ = $$;
  var isAuth = root.getAttribute("data-auth") === "1";

  /* ---------------------------------------------------------------- helpers */
  QM.escape = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  QM.csrf = function () { var m = $('meta[name="csrf-token"]'); return m ? m.content : ""; };
  QM.debounce = function (fn, ms) {
    var t; return function () { var a = arguments, s = this; clearTimeout(t); t = setTimeout(function () { fn.apply(s, a); }, ms); };
  };
  QM.icon = function (name) {
    var tpl = document.getElementById("icon-" + name);
    return tpl ? tpl.innerHTML : "";
  };

  /* JSON fetch with CSRF header, timeout and uniform error handling. */
  QM.api = function (url, opts) {
    opts = opts || {};
    var ctrl = window.AbortController ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, opts.timeout || 15000) : null;
    var init = {
      method: opts.method || "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
      signal: ctrl ? ctrl.signal : undefined,
      keepalive: !!opts.keepalive
    };
    if (init.method !== "GET") {
      init.headers["X-CSRFToken"] = QM.csrf();
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.body || {});
    }
    return fetch(url, init).then(function (res) {
      if (timer) clearTimeout(timer);
      return res.json().catch(function () { return { ok: false, error: { message: "Unexpected server response." } }; })
        .then(function (data) {
          data = data || {};
          data.status = res.status;
          if (res.status === 401 && !opts.noRedirect) {
            QM.toast("Your session has ended. Redirecting to sign in…", "warning");
            setTimeout(function () { window.location.href = (root.getAttribute("data-login-url") || "/auth/login") + "?next=" + encodeURIComponent(location.pathname); }, 1200);
          }
          return data;
        });
    }, function (err) {
      if (timer) clearTimeout(timer);
      return { ok: false, network: true, status: 0, error: { message: err && err.name === "AbortError" ? "The request timed out." : "Network error — check your connection." } };
    });
  };

  /* ----------------------------------------------------------------- toasts */
  function toastHost() {
    var host = $(".toasts");
    if (!host) { host = document.createElement("div"); host.className = "toasts"; host.setAttribute("aria-live", "polite"); document.body.appendChild(host); }
    return host;
  }
  var toastIcons = { success: "check-circle", error: "x-circle", warning: "alert", info: "info" };
  function armToast(el, ms) {
    var close = $(".toast-close", el);
    var dismiss = function () { if (!el.parentNode) return; el.classList.add("leaving"); setTimeout(function () { el.remove(); }, 300); };
    if (close) close.addEventListener("click", dismiss);
    if (ms) { var t = setTimeout(dismiss, ms); el.addEventListener("mouseenter", function () { clearTimeout(t); }); el.addEventListener("mouseleave", function () { t = setTimeout(dismiss, 2500); }); }
  }
  QM.toast = function (message, type, ms) {
    type = type || "info";
    var el = document.createElement("div");
    el.className = "toast " + type;
    el.setAttribute("role", type === "error" ? "alert" : "status");
    el.innerHTML = QM.icon(toastIcons[type] || "info") + '<div style="flex:1">' + QM.escape(message) + '</div><button type="button" class="toast-close icon-btn" style="width:26px;height:26px" aria-label="Dismiss">' + QM.icon("x") + "</button>";
    toastHost().appendChild(el);
    armToast(el, ms === 0 ? 0 : (ms || (type === "error" ? 8000 : 5000)));
    return el;
  };
  $$(".toasts .toast").forEach(function (el) { armToast(el, el.classList.contains("error") ? 9000 : 6000); });

  /* ------------------------------------------------------- confirm dialogs */
  var modal = null, lastFocus = null;
  function buildModal() {
    modal = document.createElement("div");
    modal.className = "modal"; modal.hidden = true;
    modal.setAttribute("role", "dialog"); modal.setAttribute("aria-modal", "true"); modal.setAttribute("aria-labelledby", "qm-modal-title");
    modal.innerHTML = '<div class="modal-card"><div class="modal-icon"></div><h2 id="qm-modal-title"></h2><p class="text-muted qm-modal-body"></p>' +
      '<div class="qm-modal-extra"></div><div class="modal-actions"><button type="button" class="btn btn-ghost" data-modal-cancel>Cancel</button>' +
      '<button type="button" class="btn btn-danger" data-modal-ok>Confirm</button></div></div>';
    document.body.appendChild(modal);
    modal.addEventListener("click", function (e) { if (e.target === modal || e.target.closest("[data-modal-cancel]")) QM.closeModal(false); });
  }
  var modalResolve = null;
  QM.confirm = function (o) {
    if (!modal) buildModal();
    o = o || {};
    lastFocus = document.activeElement;
    var danger = o.danger !== false;
    $(".modal-icon", modal).className = "modal-icon" + (danger ? "" : " info");
    $(".modal-icon", modal).innerHTML = QM.icon(o.icon || (danger ? "alert" : "info"));
    $("#qm-modal-title", modal).textContent = o.title || "Are you sure?";
    $(".qm-modal-body", modal).textContent = o.message || "";
    $(".qm-modal-extra", modal).innerHTML = o.extraHTML || "";
    var ok = $("[data-modal-ok]", modal);
    ok.textContent = o.ok || "Confirm";
    ok.className = "btn " + (danger ? "btn-danger" : "btn-primary");
    $("[data-modal-cancel]", modal).textContent = o.cancel || "Cancel";
    modal.hidden = false;
    setTimeout(function () { ok.focus(); }, 30);
    return new Promise(function (resolve) {
      modalResolve = resolve;
      ok.onclick = function () { QM.closeModal(true); };
    });
  };
  QM.closeModal = function (val) {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    if (modalResolve) { var r = modalResolve; modalResolve = null; r(val); }
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  };
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { QM.closeModal(false); closeDropdowns(); }
    if (e.key === "Tab" && modal && !modal.hidden) {
      var f = $$("button, [href], input, select, textarea", modal).filter(function (x) { return !x.disabled && x.offsetParent !== null; });
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  });

  /* Forms/buttons with data-confirm ask before submitting. */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var submitter = e.submitter;
    var msgSrc = (submitter && submitter.hasAttribute("data-confirm")) ? submitter : (form.hasAttribute("data-confirm") ? form : null);
    if (msgSrc && !form.__confirmed) {
      e.preventDefault();
      QM.confirm({
        title: msgSrc.getAttribute("data-confirm-title") || "Please confirm",
        message: msgSrc.getAttribute("data-confirm"),
        ok: msgSrc.getAttribute("data-confirm-ok") || "Confirm",
        danger: msgSrc.getAttribute("data-confirm-danger") !== "false"
      }).then(function (yes) {
        if (!yes) return;
        form.__confirmed = true;
        if (submitter && submitter.name) {
          var h = document.createElement("input"); h.type = "hidden"; h.name = submitter.name; h.value = submitter.value; form.appendChild(h);
        }
        markLoading(form, submitter);
        HTMLFormElement.prototype.submit.call(form);
      });
      return;
    }
    if (!e.defaultPrevented) markLoading(form, submitter);
  });
  /* Poka-yoke: prevent double submission by disabling the clicked button. */
  function markLoading(form, submitter) {
    if (form.hasAttribute("data-no-loading") || form.method.toLowerCase() === "get") return;
    var btn = submitter || $('button[type="submit"], button:not([type])', form);
    if (!btn) return;
    setTimeout(function () { btn.classList.add("is-loading"); btn.disabled = true; }, 0);
    setTimeout(function () { btn.classList.remove("is-loading"); btn.disabled = false; }, 12000);
  }
  window.addEventListener("pageshow", function () { $$(".is-loading").forEach(function (b) { b.classList.remove("is-loading"); b.disabled = false; }); });

  /* -------------------------------------------------------------- dropdowns */
  function closeDropdowns(except) {
    $$(".dropdown.open").forEach(function (d) {
      if (d !== except) { d.classList.remove("open"); var t = $("[data-dropdown-toggle]", d); if (t) t.setAttribute("aria-expanded", "false"); }
    });
  }
  document.addEventListener("click", function (e) {
    var toggle = e.target.closest("[data-dropdown-toggle]");
    if (toggle) {
      e.preventDefault();
      var dd = toggle.closest(".dropdown");
      var open = !dd.classList.contains("open");
      closeDropdowns(dd);
      dd.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", String(open));
      if (open) dd.dispatchEvent(new CustomEvent("dropdown:open"));
      return;
    }
    if (!e.target.closest(".dropdown-menu")) closeDropdowns();
  });

  /* --------------------------------------------------------- theme & prefs */
  function savePrefs(changes) {
    if (isAuth) {
      return QM.api(root.getAttribute("data-prefs-url") || "/account/api/prefs", { method: "POST", body: changes, noRedirect: true });
    }
    var store = {};
    try { store = JSON.parse(localStorage.getItem("qm-prefs") || "{}") || {}; } catch (e) { store = {}; }
    Object.keys(changes).forEach(function (k) { store[k] = changes[k]; });
    try { localStorage.setItem("qm-prefs", JSON.stringify(store)); } catch (e) { /* storage disabled */ }
    return Promise.resolve({ ok: true });
  }
  QM.savePrefs = savePrefs;
  function applyTheme(pref) {
    var dark = pref === "dark" || (pref === "system" && window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-theme-pref", pref);
    root.setAttribute("data-theme", dark ? "dark" : "light");
  }
  QM.applyTheme = applyTheme;
  $$("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      savePrefs({ theme: next });
      btn.setAttribute("aria-label", next === "dark" ? "Switch to light theme" : "Switch to dark theme");
    });
  });
  /* Live preview of appearance settings (settings page). */
  $$("[data-pref-live]").forEach(function (input) {
    input.addEventListener("change", function () {
      var k = input.getAttribute("data-pref-live"), v = input.type === "checkbox" ? input.checked : input.value;
      if (k === "theme") applyTheme(v);
      else if (k === "palette") root.setAttribute("data-palette", v);
      else if (k === "contrast") root.setAttribute("data-contrast", v);
      else if (k === "reduce_motion") root.setAttribute("data-motion", v ? "reduce" : "normal");
      else if (k === "font_scale") root.style.setProperty("--font-scale", String(parseInt(v, 10) / 100));
      if (!isAuth) {
        var c = {}; c[k === "reduce_motion" ? "motion" : k] = k === "reduce_motion" ? (v ? "reduce" : "normal") : v; savePrefs(c);
      }
    });
  });

  /* ------------------------------------------------------ navigation shells */
  var app = $(".app");
  $$("[data-sidebar-toggle]").forEach(function (b) {
    b.addEventListener("click", function () { var open = !app.classList.contains("nav-open"); app.classList.toggle("nav-open", open); b.setAttribute("aria-expanded", String(open)); });
  });
  var scrim = $(".sidebar-scrim");
  if (scrim) scrim.addEventListener("click", function () { app.classList.remove("nav-open"); });
  $$("[data-nav-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var links = document.getElementById(b.getAttribute("aria-controls"));
      var open = !links.classList.contains("open");
      links.classList.toggle("open", open); b.setAttribute("aria-expanded", String(open));
    });
  });
  var header = $(".site-header");
  if (header) {
    var onScroll = function () { header.classList.toggle("scrolled", window.scrollY > 8); };
    window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
  }

  /* ------------------------------------------------------ password helpers */
  $$("[data-pw-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var input = document.getElementById(b.getAttribute("data-pw-toggle"));
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      b.setAttribute("aria-pressed", String(show));
      b.setAttribute("aria-label", show ? "Hide password" : "Show password");
      b.innerHTML = QM.icon(show ? "eye-off" : "eye");
    });
  });
  var COMMON = ["password", "12345678", "123456789", "qwerty123", "iloveyou", "password1", "11111111", "abc12345", "quizmaster"];
  QM.passwordScore = function (pw) {
    var rules = { len: pw.length >= 8, long: pw.length >= 12, lower: /[a-z]/.test(pw), upper: /[A-Z]/.test(pw), digit: /\d/.test(pw), symbol: /[^A-Za-z0-9]/.test(pw) };
    var variety = [rules.lower, rules.upper, rules.digit, rules.symbol].filter(Boolean).length;
    var score = 0;
    if (pw.length) score = 1;
    if (rules.len && variety >= 2) score = 2;
    if (rules.len && variety >= 3) score = 3;
    if ((rules.long && variety >= 3) || pw.length >= 16) score = 4;
    if (COMMON.indexOf(pw.toLowerCase()) !== -1) score = 1;
    return { score: score, rules: rules };
  };
  $$("[data-strength]").forEach(function (input) {
    var meter = document.getElementById(input.getAttribute("data-strength"));
    var label = document.getElementById(input.getAttribute("data-strength") + "-label");
    var rules = document.getElementById(input.getAttribute("data-strength") + "-rules");
    var words = ["", "Weak", "Fair", "Good", "Strong"];
    var update = function () {
      var r = QM.passwordScore(input.value);
      if (meter) meter.setAttribute("data-score", String(r.score));
      if (label) label.textContent = input.value ? words[r.score] : "";
      if (rules) $$("[data-rule]", rules).forEach(function (li) { li.classList.toggle("met", !!r.rules[li.getAttribute("data-rule")]); });
    };
    input.addEventListener("input", update); update();
  });
  $$("[data-match]").forEach(function (input) {
    var other = document.getElementById(input.getAttribute("data-match"));
    var note = document.getElementById(input.id + "-match");
    var check = function () {
      var bad = input.value && other.value !== input.value;
      input.setCustomValidity(bad ? "Passwords do not match." : "");
      if (note) { note.textContent = !input.value ? "" : (bad ? "Passwords do not match." : "Passwords match."); note.className = "hint " + (bad ? "bad" : "ok"); }
    };
    input.addEventListener("input", check); other.addEventListener("input", check);
  });
  /* Caps-lock warning on password fields. */
  $$('input[type="password"]').forEach(function (input) {
    var warn = document.getElementById(input.id + "-caps");
    if (!warn) return;
    var f = function (e) { if (e.getModifierState) warn.hidden = !e.getModifierState("CapsLock"); };
    input.addEventListener("keyup", f); input.addEventListener("keydown", f);
    input.addEventListener("blur", function () { warn.hidden = true; });
  });

  /* ------------------------------------------------------------- OTP input */
  $$("[data-otp]").forEach(function (wrap) {
    var boxes = $$("input.otp-digit", wrap);
    var hidden = document.getElementById(wrap.getAttribute("data-otp"));
    var form = wrap.closest("form");
    var sync = function () {
      hidden.value = boxes.map(function (b) { return b.value; }).join("");
      boxes.forEach(function (b) { b.classList.toggle("filled", !!b.value); });
      if (hidden.value.length === boxes.length && /^\d+$/.test(hidden.value) && form && wrap.hasAttribute("data-autosubmit") && !form.__autoSent) {
        form.__autoSent = true;
        if (form.requestSubmit) form.requestSubmit(); else form.submit();
      }
    };
    var fill = function (start, text) {
      var digits = text.replace(/\D/g, "").split("");
      for (var i = start; i < boxes.length && digits.length; i++) boxes[i].value = digits.shift();
      var next = boxes.filter(function (b) { return !b.value; })[0] || boxes[boxes.length - 1];
      next.focus(); sync();
    };
    boxes.forEach(function (box, i) {
      box.addEventListener("input", function () {
        if (box.value.length > 1) { fill(i, box.value); return; }
        box.value = box.value.replace(/\D/g, "");
        if (box.value && boxes[i + 1]) boxes[i + 1].focus();
        sync();
      });
      box.addEventListener("keydown", function (e) {
        if (e.key === "Backspace" && !box.value && boxes[i - 1]) { boxes[i - 1].focus(); boxes[i - 1].value = ""; sync(); e.preventDefault(); }
        if (e.key === "ArrowLeft" && boxes[i - 1]) { boxes[i - 1].focus(); e.preventDefault(); }
        if (e.key === "ArrowRight" && boxes[i + 1]) { boxes[i + 1].focus(); e.preventDefault(); }
      });
      box.addEventListener("paste", function (e) { e.preventDefault(); fill(i, (e.clipboardData || window.clipboardData).getData("text")); });
      box.addEventListener("focus", function () { box.select(); });
    });
    if (wrap.hasAttribute("data-invalid")) { wrap.classList.add("shake"); }
    if (boxes[0] && !boxes[0].value) boxes[0].focus();
  });

  /* Countdown for "resend code" style buttons: data-cooldown="seconds". */
  $$("[data-cooldown]").forEach(function (btn) {
    var left = parseInt(btn.getAttribute("data-cooldown"), 10) || 0;
    var label = btn.getAttribute("data-label") || btn.textContent.trim();
    var tick = function () {
      if (left <= 0) { btn.disabled = false; btn.textContent = label; return; }
      btn.disabled = true; btn.textContent = label + " (" + left + "s)"; left -= 1; setTimeout(tick, 1000);
    };
    tick();
  });

  /* Live countdown to a timestamp: data-countdown="ISO". */
  $$("[data-countdown]").forEach(function (el) {
    var target = Date.parse(el.getAttribute("data-countdown"));
    if (isNaN(target)) return;
    var tick = function () {
      var s = Math.max(0, Math.round((target - Date.now()) / 1000));
      var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
      el.textContent = (d ? d + "d " : "") + (d || h ? h + "h " : "") + m + "m " + (d ? "" : sec + "s");
      if (s > 0) setTimeout(tick, 1000); else if (el.hasAttribute("data-reload")) setTimeout(function () { location.reload(); }, 1500);
    };
    tick();
  });

  /* ------------------------------------------------------------------ tabs */
  $$("[data-tabs]").forEach(function (group) {
    var tabs = $$("[data-tab]", group);
    var scope = group.parentElement;
    var show = function (id, focus) {
      tabs.forEach(function (t) { var on = t.getAttribute("data-tab") === id; t.classList.toggle("active", on); t.setAttribute("aria-selected", String(on)); t.tabIndex = on ? 0 : -1; if (on && focus) t.focus(); });
      $$("[data-panel]", scope).forEach(function (p) { p.hidden = p.getAttribute("data-panel") !== id; });
    };
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function (e) { e.preventDefault(); show(t.getAttribute("data-tab")); if (history.replaceState) history.replaceState(null, "", "#" + t.getAttribute("data-tab")); });
      t.addEventListener("keydown", function (e) {
        var n = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (n) { e.preventDefault(); var nt = tabs[(i + n + tabs.length) % tabs.length]; show(nt.getAttribute("data-tab"), true); }
      });
    });
    var initial = location.hash.slice(1);
    var match = tabs.filter(function (t) { return t.getAttribute("data-tab") === initial; })[0];
    show(match ? initial : tabs[0].getAttribute("data-tab"));
  });

  /* ------------------------------------------------------- small enhancers */
  $$("[data-autosubmit]").forEach(function (el) {
    if (el.tagName === "FORM" || el.closest("[data-otp]")) return;
    el.addEventListener("change", function () { var f = el.form || el.closest("form"); if (f) { if (f.requestSubmit) f.requestSubmit(); else f.submit(); } });
  });
  $$("[data-counter]").forEach(function (field) {
    var out = document.getElementById(field.getAttribute("data-counter"));
    var max = parseInt(field.getAttribute("maxlength"), 10);
    var upd = function () { out.textContent = field.value.length + (max ? " / " + max : ""); out.classList.toggle("warn", max && field.value.length > max * 0.9); };
    field.addEventListener("input", upd); upd();
  });
  $$("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var txt = b.getAttribute("data-copy");
      var done = function () { QM.toast("Copied to clipboard.", "success", 2500); };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(txt).then(done, function () { QM.toast("Copy failed — select the text manually.", "error"); });
      else { var ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); done(); } catch (e) { QM.toast("Copy failed.", "error"); } ta.remove(); }
    });
  });
  $$("[data-print]").forEach(function (b) { b.addEventListener("click", function () { window.print(); }); });
  $$("[data-back]").forEach(function (b) { b.addEventListener("click", function (e) { if (history.length > 1 && document.referrer.indexOf(location.host) !== -1) { e.preventDefault(); history.back(); } }); });
  $$("[data-href]").forEach(function (row) {
    row.style.cursor = "pointer";
    row.addEventListener("click", function (e) { if (!e.target.closest("a, button, input, select, label, form")) location.href = row.getAttribute("data-href"); });
  });
  /* Image preview for file inputs. */
  $$("input[type=file][data-preview]").forEach(function (input) {
    input.addEventListener("change", function () {
      var target = document.getElementById(input.getAttribute("data-preview"));
      var f = input.files && input.files[0];
      if (!f || !target) return;
      var max = parseInt(input.getAttribute("data-max-bytes"), 10);
      if (max && f.size > max) { QM.toast("That file is larger than " + Math.round(max / 1048576 * 10) / 10 + " MB. Choose a smaller image.", "error"); input.value = ""; return; }
      if (!/^image\/(png|jpe?g|webp|gif)$/.test(f.type)) { QM.toast("Choose a PNG, JPG, WEBP or GIF image.", "error"); input.value = ""; return; }
      var url = URL.createObjectURL(f);
      var av = target.classList.contains("avatar") ? target : (target.querySelector(".avatar") || target);
      if (av.tagName === "IMG") av.src = url; else av.innerHTML = '<img alt="Selected image preview" src="' + url + '">';
      var name = document.getElementById(input.id + "-name"); if (name) name.textContent = f.name;
    });
  });
  /* Warn before leaving a form with unsaved edits. */
  $$("form[data-dirty-guard]").forEach(function (form) {
    var dirty = false;
    form.addEventListener("input", function () { dirty = true; });
    form.addEventListener("submit", function () { dirty = false; });
    window.addEventListener("beforeunload", function (e) { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
  });
  /* Select-all checkboxes for bulk actions. */
  $$("[data-check-all]").forEach(function (master) {
    var name = master.getAttribute("data-check-all");
    var boxes = function () { return $$('input[type=checkbox][name="' + name + '"]'); };
    var bar = document.getElementById(master.getAttribute("data-bulk-bar") || "");
    var refresh = function () {
      var n = boxes().filter(function (b) { return b.checked; }).length;
      if (bar) { bar.hidden = n === 0; var c = $("[data-bulk-count]", bar); if (c) c.textContent = n; }
    };
    master.addEventListener("change", function () { boxes().forEach(function (b) { b.checked = master.checked; }); refresh(); });
    document.addEventListener("change", function (e) { if (e.target.name === name) refresh(); });
    refresh();
  });
  /* Scroll reveal. */
  var reveals = $$(".reveal");
  if (reveals.length) {
    if ("IntersectionObserver" in window && root.getAttribute("data-motion") !== "reduce") {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
      }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
      reveals.forEach(function (el) { io.observe(el); });
    } else reveals.forEach(function (el) { el.classList.add("in"); });
  }
  /* Animated number counters: data-count-to. */
  $$("[data-count-to]").forEach(function (el) {
    var end = parseFloat(el.getAttribute("data-count-to")); var dec = (el.getAttribute("data-count-to").split(".")[1] || "").length;
    if (isNaN(end) || root.getAttribute("data-motion") === "reduce") return;
    var t0 = null, dur = 900;
    var step = function (ts) { if (!t0) t0 = ts; var p = Math.min(1, (ts - t0) / dur); el.textContent = (end * (1 - Math.pow(1 - p, 3))).toFixed(dec); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
  /* Confetti on a passed result. */
  QM.confetti = function () {
    if (root.getAttribute("data-motion") === "reduce" || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var wrap = document.createElement("div"); wrap.className = "confetti"; wrap.setAttribute("aria-hidden", "true");
    var colors = ["#6366F1", "#8B5CF6", "#06B6D4", "#14B8A6", "#F97362", "#F59E0B", "#EC4899"];
    for (var i = 0; i < 90; i++) {
      var p = document.createElement("i");
      p.style.left = Math.random() * 100 + "vw"; p.style.background = colors[i % colors.length];
      p.style.animationDuration = 2.2 + Math.random() * 2 + "s"; p.style.animationDelay = Math.random() * 0.6 + "s";
      p.style.transform = "rotate(" + Math.random() * 360 + "deg)"; wrap.appendChild(p);
    }
    document.body.appendChild(wrap); setTimeout(function () { wrap.remove(); }, 5200);
  };
  if ($("[data-confetti]")) setTimeout(QM.confetti, 400);

  /* --------------------------------------------------------- notifications */
  $$("[data-notif]").forEach(function (dd) {
    var list = $("[data-notif-list]", dd), badge = $("[data-notif-badge]", dd);
    var apiUrl = dd.getAttribute("data-notif"), readUrl = dd.getAttribute("data-notif-read");
    var setBadge = function (n) { if (!badge) return; badge.textContent = n > 9 ? "9+" : String(n); badge.hidden = !n; };
    var render = function (data) {
      setBadge(data.unread);
      if (!data.items.length) { list.innerHTML = '<div class="empty" style="padding:1.5rem"><p class="text-muted text-sm" style="margin:0">You’re all caught up. New results and announcements will appear here.</p></div>'; return; }
      list.innerHTML = data.items.map(function (n) {
        var href = n.link && n.link.charAt(0) === "/" ? n.link : (dd.getAttribute("data-notif-page") || "#notifications");
        return '<a class="notif-item ' + (n.read ? "read" : "unread") + '" href="' + QM.escape(href) + '" data-nid="' + n.id + '"><span class="n-dot"></span><span><b>' +
          QM.escape(n.title) + '</b>' + QM.escape(n.body || "").slice(0, 140) + '<br><small class="text-faint">' + QM.escape(n.ago) + "</small></span></a>";
      }).join("");
    };
    dd.addEventListener("dropdown:open", function () {
      list.innerHTML = '<div class="skeleton" style="height:56px;margin:.4rem"></div><div class="skeleton" style="height:56px;margin:.4rem"></div>';
      QM.api(apiUrl).then(function (r) { if (r.ok) render(r.data); else list.innerHTML = '<p class="text-muted text-sm" style="padding:1rem">' + QM.escape((r.error || {}).message || "Could not load notifications.") + "</p>"; });
    });
    list.addEventListener("click", function (e) {
      var a = e.target.closest("[data-nid]"); if (!a || a.classList.contains("read")) return;
      QM.api(readUrl, { method: "POST", body: { id: parseInt(a.getAttribute("data-nid"), 10) }, keepalive: true });
    });
    var all = $("[data-notif-readall]", dd);
    if (all) all.addEventListener("click", function () {
      QM.api(readUrl, { method: "POST", body: {} }).then(function (r) {
        if (r.ok) { setBadge(0); $$(".notif-item.unread", list).forEach(function (x) { x.classList.replace("unread", "read"); }); QM.toast("All notifications marked as read.", "success", 2500); }
      });
    });
  });

  /* ---------------------------------------------------------- autocomplete */
  $$("[data-suggest]").forEach(function (input) {
    var wrap = input.parentElement; wrap.style.position = "relative";
    var box = document.createElement("div"); box.className = "search-suggest"; box.hidden = true; box.setAttribute("role", "listbox"); box.id = input.id + "-suggest";
    input.setAttribute("aria-controls", box.id); input.setAttribute("aria-autocomplete", "list"); input.setAttribute("autocomplete", "off");
    wrap.appendChild(box);
    var active = -1, items = [];
    var close = function () { box.hidden = true; active = -1; input.setAttribute("aria-expanded", "false"); };
    var run = QM.debounce(function () {
      var q = input.value.trim();
      if (q.length < 2) { close(); return; }
      QM.api(input.getAttribute("data-suggest") + "?q=" + encodeURIComponent(q), { noRedirect: true }).then(function (r) {
        if (!r.ok) return close();
        items = r.data || [];
        if (!items.length) { box.innerHTML = '<div class="text-muted text-sm" style="padding:.6rem .7rem">No quizzes match “' + QM.escape(q) + "”. Press Enter to search all.</div>"; }
        else box.innerHTML = items.map(function (it, i) { return '<a role="option" href="' + QM.escape(it.url) + '" data-i="' + i + '"><span>' + QM.escape(it.title) + "</span><small>" + QM.escape(it.category) + "</small></a>"; }).join("");
        box.hidden = false; input.setAttribute("aria-expanded", "true");
      });
    }, 220);
    input.addEventListener("input", run);
    input.addEventListener("keydown", function (e) {
      var links = $$("a", box);
      if (box.hidden || !links.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); active = (active + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        links.forEach(function (l, i) { l.classList.toggle("active", i === active); });
      } else if (e.key === "Enter" && active >= 0) { e.preventDefault(); location.href = links[active].href; }
    });
    input.addEventListener("blur", function () { setTimeout(close, 180); });
  });

  /* ------------------------------------------------------------- shortcuts */
  var gPressed = 0;
  document.addEventListener("keydown", function (e) {
    var t = e.target;
    if (e.ctrlKey || e.metaKey || e.altKey || (t && (t.isContentEditable || /INPUT|TEXTAREA|SELECT/.test(t.tagName)))) return;
    if (document.body.hasAttribute("data-player")) return; // the quiz player owns the keyboard
    if (e.key === "/") { var s = $("[data-search-focus]"); if (s) { e.preventDefault(); s.focus(); } return; }
    if (e.key === "?") { var u = root.getAttribute("data-shortcuts-url"); if (u) location.href = u; return; }
    if (e.key === "g") { gPressed = Date.now(); return; }
    if (Date.now() - gPressed < 1000) {
      var map = { d: "data-nav-dashboard", e: "data-nav-explore", h: "data-nav-history", r: "data-nav-results", p: "data-nav-profile", s: "data-nav-settings" };
      var attr = map[e.key.toLowerCase()];
      if (attr && root.getAttribute(attr)) { location.href = root.getAttribute(attr); }
      gPressed = 0;
    }
  });

  /* ----------------------------------------------- admin: question editor */
  var qform = $("[data-question-form]");
  if (qform) {
    var typeSel = $("[data-qtype]", qform);
    var optList = $("[data-options]", qform);
    var tpl = $("template[data-option-template]", qform);
    var reindex = function () {
      $$(".option-row", optList).forEach(function (row, i) {
        var cb = $("input[type=checkbox]", row); cb.value = String(i);
        var key = $(".opt-key", row); if (key) key.textContent = String.fromCharCode(65 + i);
        var txt = $("input[type=text]", row); txt.setAttribute("aria-label", "Option " + String.fromCharCode(65 + i));
      });
      var n = $$(".option-row", optList).length;
      var add = $("[data-add-option]", qform); if (add) add.disabled = n >= 8;
    };
    var applyType = function () {
      var t = typeSel.value;
      $$("[data-for-types]", qform).forEach(function (sec) {
        var on = sec.getAttribute("data-for-types").split(" ").indexOf(t) !== -1;
        sec.hidden = !on;
        $$("input, textarea, select", sec).forEach(function (f) { f.disabled = !on; });
      });
      var hint = $("[data-correct-hint]", qform);
      if (hint) hint.textContent = t === "multiple" ? "Tick every correct option (all-or-nothing scoring)." : "Tick exactly one correct option.";
    };
    typeSel.addEventListener("change", applyType);
    optList.addEventListener("change", function (e) {
      if (e.target.type === "checkbox" && e.target.checked && typeSel.value === "single") {
        $$("input[type=checkbox]", optList).forEach(function (cb) { if (cb !== e.target) cb.checked = false; });
      }
    });
    qform.addEventListener("click", function (e) {
      if (e.target.closest("[data-add-option]")) {
        e.preventDefault(); optList.appendChild(tpl.content.cloneNode(true)); reindex();
        var rows = $$(".option-row", optList); $("input[type=text]", rows[rows.length - 1]).focus();
      }
      var rm = e.target.closest("[data-remove-option]");
      if (rm) {
        e.preventDefault();
        if ($$(".option-row", optList).length <= 2) { QM.toast("A choice question needs at least two options.", "warning"); return; }
        rm.closest(".option-row").remove(); reindex();
      }
    });
    reindex(); applyType();
    /* Search-before-add duplicate check (Q06). */
    var textArea = $("[data-similar]", qform), simBox = $("[data-similar-results]", qform);
    if (textArea && simBox) {
      textArea.addEventListener("input", QM.debounce(function () {
        var v = textArea.value.trim();
        if (v.length < 12) { simBox.hidden = true; return; }
        QM.api(textArea.getAttribute("data-similar") + "?text=" + encodeURIComponent(v) + "&exclude=" + (textArea.getAttribute("data-exclude") || ""), { noRedirect: true }).then(function (r) {
          if (!r.ok || !r.data.length) { simBox.hidden = true; return; }
          simBox.hidden = false;
          simBox.innerHTML = '<div class="alert alert-warning">' + QM.icon("alert") + '<div><b>Possible duplicates found</b><ul style="margin:.3rem 0 0;padding-left:1.1rem">' +
            r.data.map(function (d) { return "<li>" + QM.escape(d.text) + " <span class=\"badge badge-warn\">" + d.similarity + "% similar</span>" + (d.archived ? ' <span class="badge">archived</span>' : "") + "</li>"; }).join("") +
            "</ul></div></div>";
        });
      }, 500));
    }
  }

  /* Quiz form: show negative marking field only when enabled, etc. */
  $$("[data-toggle-target]").forEach(function (ctl) {
    var target = document.getElementById(ctl.getAttribute("data-toggle-target"));
    var upd = function () { var on = ctl.type === "checkbox" ? ctl.checked : !!ctl.value; target.hidden = !on; };
    ctl.addEventListener("change", upd); upd();
  });
})();

/* Range output mirror (settings text size). */
(function () {
  var r = document.getElementById("font-scale"), o = document.getElementById("fs-out");
  if (r && o) r.addEventListener("input", function () { o.textContent = r.value + "%"; document.documentElement.style.setProperty("--font-scale", String(r.value / 100)); });

  /* File inputs: show the chosen file name (import dropzone). */
  $$("input[type=file][data-filename-target]").forEach(function (inp) {
    var out = document.getElementById(inp.getAttribute("data-filename-target"));
    var zone = inp.closest(".dropzone");
    inp.addEventListener("change", function () {
      if (out) out.textContent = inp.files && inp.files[0] ? inp.files[0].name + " (" + Math.ceil(inp.files[0].size / 1024) + " KB)" : "No file selected";
    });
    if (zone) {
      ["dragenter", "dragover"].forEach(function (ev) { zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("drag"); }); });
      ["dragleave", "drop"].forEach(function (ev) { zone.addEventListener(ev, function () { zone.classList.remove("drag"); }); });
      zone.addEventListener("drop", function (e) {
        e.preventDefault();
        if (e.dataTransfer && e.dataTransfer.files.length) { inp.files = e.dataTransfer.files; inp.dispatchEvent(new Event("change", { bubbles: true })); }
      });
    }
  });
})();
