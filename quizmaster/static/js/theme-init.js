/* QuizMaster theme bootstrap — loaded synchronously in <head> to avoid a flash
   of the wrong theme. Signed-in users: preferences come from the server and are
   rendered as data-* attributes on <html>. Guests: preferences live in
   localStorage. "system" resolves through prefers-color-scheme. */
(function () {
  var root = document.documentElement;
  root.classList.remove("no-js");
  root.classList.add("js");
  var guest = root.getAttribute("data-auth") !== "1";
  var store = {};
  if (guest) {
    try { store = JSON.parse(localStorage.getItem("qm-prefs") || "{}") || {}; } catch (e) { store = {}; }
  }
  var pref = (guest && store.theme) || root.getAttribute("data-theme-pref") || "system";
  function resolve(p) {
    if (p === "dark" || p === "light") return p;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  root.setAttribute("data-theme-pref", pref);
  root.setAttribute("data-theme", resolve(pref));
  if (guest) {
    if (store.palette) root.setAttribute("data-palette", store.palette);
    if (store.contrast) root.setAttribute("data-contrast", store.contrast);
    if (store.motion) root.setAttribute("data-motion", store.motion);
    if (store.font_scale) root.style.setProperty("--font-scale", String(store.font_scale / 100));
  }
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var onChange = function () {
      if (root.getAttribute("data-theme-pref") === "system") root.setAttribute("data-theme", resolve("system"));
    };
    if (mq.addEventListener) mq.addEventListener("change", onChange); else if (mq.addListener) mq.addListener(onChange);
  }
})();
