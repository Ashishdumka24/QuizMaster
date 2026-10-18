/* QuizMaster quiz player.
   - The server is the source of truth for time: the countdown is re-synchronised
     from every API response and the server rejects answers after the deadline.
   - Answers autosave (debounced) and are also kept in localStorage until the
     server confirms them, so a refresh, crash or network drop loses nothing.
   - Submission is idempotent: the server grades an attempt exactly once.
   - The answer key never reaches the browser. */
(function () {
  "use strict";
  var host = document.getElementById("player");
  if (!host || !window.QM) return;
  var QM = window.QM, esc = QM.escape;
  var urls = { state: host.getAttribute("data-state-url"), save: host.getAttribute("data-save-url"), submit: host.getAttribute("data-submit-url") };
  var attemptId = host.getAttribute("data-attempt-id");
  var LS_KEY = "qm-attempt-" + attemptId;
  var S = { qs: [], answers: {}, idx: 0, pending: {}, deadline: null, finished: false, submitting: false, imageBase: "", saveTimer: null, saving: false, startedLocal: Date.now() };
  var els = {};
  document.body.setAttribute("data-player", "1");

  /* --------------------------------------------------------------- storage */
  function loadBackup() { try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}") || {}; } catch (e) { return {}; } }
  function writeBackup() {
    try {
      if (Object.keys(S.pending).length) localStorage.setItem(LS_KEY, JSON.stringify(S.pending));
      else localStorage.removeItem(LS_KEY);
    } catch (e) { /* storage full/disabled: server autosave still runs */ }
  }

  /* ----------------------------------------------------------------- state */
  function answerOf(q) { return S.answers[q.id] || { response: null, marked: false }; }
  function isAnswered(q) {
    var r = answerOf(q).response;
    return !!(r && ((r.options && r.options.length) || (r.text && r.text.trim())));
  }
  function setAnswer(q, patch) {
    var cur = answerOf(q);
    var next = { response: "response" in patch ? patch.response : cur.response, marked: "marked" in patch ? patch.marked : cur.marked };
    S.answers[q.id] = next;
    S.pending[q.id] = { question_id: q.id, response: next.response, marked: next.marked };
    writeBackup();
    setSave("saving", "Saving…");
    clearTimeout(S.saveTimer);
    S.saveTimer = setTimeout(flush, 700);
    renderPalette();
  }

  /* ------------------------------------------------------------------ sync */
  function syncClock(remaining) {
    if (remaining === null || remaining === undefined) { S.deadline = null; return; }
    S.deadline = Date.now() + remaining * 1000;
  }
  function goResult(url, msg) {
    S.finished = true;
    try { localStorage.removeItem(LS_KEY); } catch (e) { /* ignore */ }
    if (msg) QM.toast(msg, "info");
    setTimeout(function () { window.location.href = url; }, msg ? 900 : 0);
  }
  function flush(opts) {
    opts = opts || {};
    var items = Object.keys(S.pending).map(function (k) { return S.pending[k]; });
    if (!items.length || S.finished) { if (!items.length) setSave("saved", "All answers saved"); return Promise.resolve(true); }
    if (S.saving && !opts.force) { clearTimeout(S.saveTimer); S.saveTimer = setTimeout(flush, 600); return Promise.resolve(false); }
    S.saving = true;
    var sent = {}; items.forEach(function (it) { sent[it.question_id] = JSON.stringify(it); });
    return QM.api(urls.save, { method: "POST", body: { answers: items }, keepalive: !!opts.keepalive }).then(function (r) {
      S.saving = false;
      if (r.ok) {
        Object.keys(sent).forEach(function (k) { if (S.pending[k] && JSON.stringify(S.pending[k]) === sent[k]) delete S.pending[k]; });
        writeBackup();
        syncClock(r.data.remaining);
        setSave(Object.keys(S.pending).length ? "saving" : "saved", Object.keys(S.pending).length ? "Saving…" : "All answers saved");
        return true;
      }
      if (r.result_url) { goResult(r.result_url, (r.error || {}).message); return false; }
      setSave("offline", r.network ? "Offline — answers kept on this device" : "Not saved — retrying");
      clearTimeout(S.saveTimer); S.saveTimer = setTimeout(flush, r.network ? 5000 : 8000);
      return false;
    });
  }
  function submit(auto) {
    if (S.submitting || S.finished) return;
    S.submitting = true;
    clearTimeout(S.saveTimer);
    var items = Object.keys(S.pending).map(function (k) { return S.pending[k]; });
    var btns = QM.$$("[data-submit-btn]"); btns.forEach(function (b) { b.classList.add("is-loading"); b.disabled = true; });
    setSave("saving", "Submitting…");
    QM.api(urls.submit, { method: "POST", body: { answers: items, auto: !!auto }, timeout: 30000 }).then(function (r) {
      if (r.ok && r.data.result_url) { goResult(r.data.result_url); return; }
      if (r.result_url) { goResult(r.result_url); return; }
      S.submitting = false;
      btns.forEach(function (b) { b.classList.remove("is-loading"); b.disabled = false; });
      setSave("offline", "Submission not confirmed");
      QM.toast(((r.error || {}).message || "Submission failed.") + " Your answers are safe — try again.", "error", 0);
      if (auto) setTimeout(function () { submit(true); }, 4000);
    });
  }

  /* ---------------------------------------------------------------- render */
  function setSave(cls, text) {
    if (!els.save) return;
    els.save.className = "save-state " + cls;
    els.save.innerHTML = '<span class="dot"></span>' + esc(text);
  }
  function shell(data) {
    var counts = S.qs.length;
    host.innerHTML =
      '<div class="player-head">' +
        '<div><div class="q-num">Attempt in progress</div><h1 style="margin:.15rem 0 0;font-size:clamp(1.2rem,1rem + 1vw,1.6rem)">' + esc(data.title) + "</h1></div>" +
        '<div class="row"><span class="save-state saved" data-save aria-live="polite"><span class="dot"></span>All answers saved</span>' +
        '<div class="timer" data-timer role="timer" aria-live="off">' + QM.icon("timer") + "<span>--:--</span></div></div>" +
      "</div>" +
      '<div class="player">' +
        '<section aria-live="polite"><div class="card q-card" data-qcard></div></section>' +
        '<aside class="card palette-card"><div class="row-between mb-2"><h3 style="margin:0;font-size:1rem">Questions</h3><span class="text-sm text-muted" data-progress-text></span></div>' +
          '<div class="progress progress-sm mb-2"><span data-progress style="width:0"></span></div>' +
          '<nav class="q-palette" data-palette aria-label="Question navigator"></nav>' +
          '<div class="palette-legend"><span><i class="a"></i>Answered</span><span><i></i>Not answered</span><span><i class="m"></i>Marked for review</span></div>' +
          (data.negative_marking ? '<div class="alert alert-warning mt-2 text-sm">' + QM.icon("alert") + "<div>Negative marking is on: wrong answers reduce your score. Leave a question blank if unsure.</div></div>" : "") +
          '<button type="button" class="btn btn-primary btn-block mt-2" data-submit-btn data-open-submit>' + QM.icon("send") + "Submit quiz</button>" +
          '<details class="mt-2 text-sm text-muted"><summary style="cursor:pointer">Keyboard shortcuts</summary><div class="kbd-list mt-1">' +
            "<kbd>1</kbd>–<kbd>9</kbd><span>Choose option</span>" +
            "<span><kbd>←</kbd> <kbd>→</kbd></span><span>Previous / next</span><kbd>M</kbd><span>Mark for review</span><kbd>X</kbd><span>Clear answer</span><kbd>S</kbd><span>Review &amp; submit</span>" +
          "</div></details>" +
        "</aside>" +
      "</div>";
    els.save = host.querySelector("[data-save]");
    els.timer = host.querySelector("[data-timer]");
    els.card = host.querySelector("[data-qcard]");
    els.palette = host.querySelector("[data-palette]");
    els.progress = host.querySelector("[data-progress]");
    els.progressText = host.querySelector("[data-progress-text]");
    host.querySelector("[data-open-submit]").addEventListener("click", openSubmit);
    els.palette.innerHTML = S.qs.map(function (q, i) { return '<button type="button" class="q-dot" data-goto="' + i + '" aria-label="Question ' + (i + 1) + '">' + (i + 1) + "</button>"; }).join("");
    els.palette.addEventListener("click", function (e) { var b = e.target.closest("[data-goto]"); if (b) go(parseInt(b.getAttribute("data-goto"), 10)); });
    if (!counts) els.card.innerHTML = '<div class="empty"><h3>No questions</h3><p>This quiz has no questions.</p></div>';
  }
  function renderPalette() {
    var answered = 0;
    QM.$$(".q-dot", els.palette).forEach(function (b, i) {
      var q = S.qs[i], a = isAnswered(q), m = answerOf(q).marked;
      if (a) answered++;
      b.classList.toggle("answered", a); b.classList.toggle("marked", !!m); b.classList.toggle("current", i === S.idx);
      b.setAttribute("aria-current", i === S.idx ? "step" : "false");
      b.setAttribute("aria-label", "Question " + (i + 1) + (a ? ", answered" : ", not answered") + (m ? ", marked for review" : ""));
    });
    els.progress.style.width = (S.qs.length ? (answered / S.qs.length) * 100 : 0) + "%";
    els.progressText.textContent = answered + " / " + S.qs.length + " answered";
  }
  var TYPE_HINT = { single: "Choose one answer", multiple: "Select all that apply", truefalse: "True or false", short: "Type a short answer", fill: "Fill in the blank" };
  function renderQuestion() {
    var q = S.qs[S.idx]; if (!q) return;
    var a = answerOf(q), sel = (a.response && a.response.options) || [];
    var choice = q.type === "single" || q.type === "multiple" || q.type === "truefalse";
    var multi = q.type === "multiple";
    var html =
      '<div class="q-meta"><span class="q-num">Question ' + (S.idx + 1) + " of " + S.qs.length + "</span>" +
      '<span class="row" style="gap:.4rem"><span class="badge badge-outline">' + esc(TYPE_HINT[q.type] || "") + "</span>" +
      '<span class="badge badge-accent">' + q.marks + (q.marks === 1 ? " mark" : " marks") + "</span>" +
      (q.negative ? '<span class="badge badge-bad">−' + q.negative + " if wrong</span>" : "") + "</span></div>" +
      '<h2 class="q-text" id="q-text">' + esc(q.text) + "</h2>" +
      (q.image ? '<img class="q-image" src="' + esc(S.imageBase + q.image) + '" alt="Image for question ' + (S.idx + 1) + '">' : "");
    if (choice) {
      html += '<div class="options" role="' + (multi ? "group" : "radiogroup") + '" aria-labelledby="q-text">' +
        q.options.map(function (o, i) {
          var on = sel.indexOf(o.id) !== -1;
          return '<button type="button" class="option' + (on ? " selected" : "") + '" role="' + (multi ? "checkbox" : "radio") + '" aria-checked="' + on + '" data-opt="' + o.id + '">' +
            '<span class="key">' + (q.type === "truefalse" ? (i ? "F" : "T") : String.fromCharCode(65 + i)) + "</span><span>" + esc(o.text) + "</span>" +
            '<span class="tick">' + QM.icon("check-circle") + "</span></button>";
        }).join("") + "</div>";
    } else {
      html += '<label class="label" for="text-answer">Your answer</label><input class="input text-answer" id="text-answer" maxlength="500" autocomplete="off" spellcheck="false" placeholder="' +
        (q.type === "fill" ? "Type the missing word or phrase" : "Type your answer") + '" value="' + esc((a.response && a.response.text) || "") + '">' +
        '<p class="hint">Answers are matched ignoring capitalisation and extra spaces.</p>';
    }
    var last = S.idx === S.qs.length - 1;
    html += '<div class="q-actions"><div class="row">' +
      '<button type="button" class="btn btn-ghost" data-prev' + (S.idx === 0 ? " disabled" : "") + ">" + QM.icon("arrow-left") + "Previous</button>" +
      '<button type="button" class="btn btn-soft" data-mark aria-pressed="' + !!a.marked + '">' + QM.icon("flag") + (a.marked ? "Unmark review" : "Mark for review") + "</button>" +
      '<button type="button" class="btn btn-ghost" data-clear>' + QM.icon("eraser") + "Clear</button></div>" +
      (last ? '<button type="button" class="btn btn-primary" data-submit-btn data-open-submit2>' + QM.icon("send") + "Review &amp; submit</button>"
            : '<button type="button" class="btn btn-primary" data-next>Next' + QM.icon("arrow-right") + "</button>") + "</div>";
    els.card.innerHTML = html;
    els.card.classList.remove("enter"); void els.card.offsetWidth; els.card.classList.add("enter");
    var ti = els.card.querySelector("#text-answer");
    if (ti) {
      ti.addEventListener("input", function () { var v = ti.value; setAnswer(q, { response: v.trim() ? { text: v } : null }); });
      ti.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); if (!last) go(S.idx + 1); } });
    }
    renderPalette();
  }
  function toggleOption(q, oid) {
    var a = answerOf(q), sel = ((a.response && a.response.options) || []).slice();
    var i = sel.indexOf(oid);
    if (q.type === "multiple") { if (i === -1) sel.push(oid); else sel.splice(i, 1); }
    else sel = i === -1 ? [oid] : [];
    setAnswer(q, { response: sel.length ? { options: sel } : null });
    QM.$$("[data-opt]", els.card).forEach(function (b) {
      var on = sel.indexOf(parseInt(b.getAttribute("data-opt"), 10)) !== -1;
      b.classList.toggle("selected", on); b.setAttribute("aria-checked", String(on));
    });
  }
  function go(i) {
    if (i < 0 || i >= S.qs.length) return;
    S.idx = i; renderQuestion();
    var f = els.card.querySelector("#text-answer, [data-opt]"); if (f && window.innerWidth > 980) f.focus({ preventScroll: true });
    if (window.innerWidth <= 980) els.card.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function openSubmit() {
    var unanswered = S.qs.filter(function (q) { return !isAnswered(q); }).length;
    var marked = S.qs.filter(function (q) { return answerOf(q).marked; }).length;
    var extra = '<div class="grid grid-3" style="gap:.6rem;margin-top:.8rem">' +
      '<div class="callout text-center"><b style="font-size:1.4rem;display:block">' + (S.qs.length - unanswered) + '</b><span class="text-xs text-muted">Answered</span></div>' +
      '<div class="callout text-center"><b style="font-size:1.4rem;display:block">' + unanswered + '</b><span class="text-xs text-muted">Unanswered</span></div>' +
      '<div class="callout text-center"><b style="font-size:1.4rem;display:block">' + marked + '</b><span class="text-xs text-muted">Marked</span></div></div>';
    QM.confirm({
      title: "Submit your quiz?",
      message: unanswered ? "You have " + unanswered + " unanswered question" + (unanswered > 1 ? "s" : "") + ". Once submitted, answers cannot be changed." : "All questions answered. Once submitted, answers cannot be changed.",
      ok: "Submit now", cancel: "Keep working", danger: false, icon: "send", extraHTML: extra
    }).then(function (yes) { if (yes) submit(false); });
  }

  /* ----------------------------------------------------------------- timer */
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function tick() {
    if (S.finished) return;
    var span = els.timer && els.timer.querySelector("span");
    if (!span) return;
    if (S.deadline === null) {
      var el = Math.floor((Date.now() - S.startedLocal) / 1000);
      span.textContent = "No time limit";
      els.timer.title = "Elapsed this session: " + Math.floor(el / 60) + " min";
      return;
    }
    var left = Math.max(0, Math.round((S.deadline - Date.now()) / 1000));
    var h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
    span.textContent = (h ? h + ":" + pad(m) : pad(m)) + ":" + pad(s);
    els.timer.classList.toggle("warn", left <= 120 && left > 30);
    els.timer.classList.toggle("danger", left <= 30);
    els.timer.setAttribute("aria-label", "Time remaining " + m + " minutes " + s + " seconds");
    if (left === 60 && !S.warned60) { S.warned60 = true; QM.toast("One minute left. Your answers are saved automatically.", "warning"); }
    if (left <= 0 && !S.submitting) { QM.toast("Time is up — submitting your answers…", "warning"); submit(true); }
  }

  /* -------------------------------------------------------------- keyboard */
  document.addEventListener("keydown", function (e) {
    if (S.finished || !S.qs.length || e.ctrlKey || e.metaKey || e.altKey) return;
    var modalOpen = QM.$(".modal:not([hidden])"); if (modalOpen) return;
    var typing = e.target && /INPUT|TEXTAREA/.test(e.target.tagName);
    if (typing) return;
    var q = S.qs[S.idx], k = e.key;
    if (k === "ArrowRight" || k === "n" || k === "N") { e.preventDefault(); go(S.idx + 1); }
    else if (k === "ArrowLeft" || k === "p" || k === "P") { e.preventDefault(); go(S.idx - 1); }
    else if (k === "m" || k === "M") { setAnswer(q, { marked: !answerOf(q).marked }); renderQuestion(); }
    else if (k === "x" || k === "X") { setAnswer(q, { response: null }); renderQuestion(); }
    else if (k === "s" || k === "S") { openSubmit(); }
    else if (/^[1-9]$/.test(k) && q.options && q.options[parseInt(k, 10) - 1]) { toggleOption(q, q.options[parseInt(k, 10) - 1].id); }
    else if (/^[a-hA-H]$/.test(k) && q.type !== "truefalse" && q.options && q.options[k.toUpperCase().charCodeAt(0) - 65]) { toggleOption(q, q.options[k.toUpperCase().charCodeAt(0) - 65].id); }
    else if ((k === "t" || k === "T" || k === "f" || k === "F") && q.type === "truefalse") { toggleOption(q, q.options[k.toLowerCase() === "t" ? 0 : 1].id); }
  });

  host.addEventListener("click", function (e) {
    var q = S.qs[S.idx]; if (!q) return;
    var opt = e.target.closest("[data-opt]");
    if (opt) { toggleOption(q, parseInt(opt.getAttribute("data-opt"), 10)); return; }
    if (e.target.closest("[data-next]")) go(S.idx + 1);
    else if (e.target.closest("[data-prev]")) go(S.idx - 1);
    else if (e.target.closest("[data-mark]")) { setAnswer(q, { marked: !answerOf(q).marked }); renderQuestion(); }
    else if (e.target.closest("[data-clear]")) { setAnswer(q, { response: null }); renderQuestion(); }
    else if (e.target.closest("[data-open-submit2]")) openSubmit();
  });

  /* ------------------------------------------------------------- lifecycle */
  window.addEventListener("beforeunload", function (e) {
    if (S.finished) return;
    if (Object.keys(S.pending).length) { flush({ keepalive: true, force: true }); e.preventDefault(); e.returnValue = ""; }
  });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flush({ keepalive: true });
    else if (!S.finished) heartbeat();
  });
  window.addEventListener("online", function () { QM.toast("Back online — syncing your answers.", "success", 2500); flush(); });
  window.addEventListener("offline", function () { setSave("offline", "Offline — answers kept on this device"); });

  function heartbeat() {
    if (S.finished || S.submitting) return;
    if (Object.keys(S.pending).length) { flush(); return; }
    QM.api(urls.state, { noRedirect: false }).then(function (r) {
      if (!r.ok) return;
      if (r.data.result_url) { goResult(r.data.result_url, "This attempt has been submitted."); return; }
      syncClock(r.data.remaining);
    });
  }

  function boot() {
    QM.api(urls.state).then(function (r) {
      if (!r.ok) {
        host.innerHTML = '<div class="card empty"><div class="empty-art">' + QM.icon("alert") + "</div><h3>Could not load the quiz</h3><p>" + esc((r.error || {}).message || "Please try again.") +
          '</p><button type="button" class="btn btn-primary" data-retry>' + QM.icon("refresh") + "Try again</button></div>";
        host.querySelector("[data-retry]").addEventListener("click", boot);
        return;
      }
      var d = r.data;
      if (d.result_url) { goResult(d.result_url); return; }
      S.qs = d.questions || []; S.imageBase = d.image_base || "";
      Object.keys(d.answers || {}).forEach(function (k) { S.answers[k] = d.answers[k]; });
      // Re-apply answers that never reached the server (crash, refresh while offline).
      var backup = loadBackup(), restored = 0;
      Object.keys(backup).forEach(function (k) {
        if (S.qs.some(function (q) { return String(q.id) === k; })) { S.answers[k] = { response: backup[k].response, marked: backup[k].marked }; S.pending[k] = backup[k]; restored++; }
      });
      syncClock(d.remaining);
      shell(d);
      var firstOpen = 0;
      for (var i = 0; i < S.qs.length; i++) { if (!isAnswered(S.qs[i])) { firstOpen = i; break; } }
      S.idx = Object.keys(S.answers).length ? firstOpen : 0;
      if (S.qs.length) renderQuestion();
      if (restored) { QM.toast("Restored " + restored + " unsaved answer" + (restored > 1 ? "s" : "") + " from this device.", "info"); flush(); }
      tick(); setInterval(tick, 500); setInterval(heartbeat, 30000);
    });
  }
  boot();
})();
