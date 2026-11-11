// The version picker keeps the reader on the same method when the target version has it, and the
// sidebar filter narrows the method list. Both are optional: every page works without JavaScript.
(function () {
  "use strict";
  var body = document.body;
  var root = body.getAttribute("data-root") || "";
  var page = body.getAttribute("data-page") || "index.html";
  var manifest = null;

  function load() {
    if (manifest) return Promise.resolve(manifest);
    return fetch(root + "versions.json").then(function (r) { return r.json(); }).then(function (m) { manifest = m; return m; });
  }

  var picker = document.querySelector(".version-picker");
  if (picker) {
    picker.addEventListener("change", function () {
      var target = picker.value;
      if (!target) return;
      load().then(function (m) {
        var version = m.channels[target] || target;
        var info = m.versions[version];
        var method = page.replace(/\.html$/, "");
        var keep = page === "" || /^(index|changes|contracts|addresses)\.html$/.test(page) ||
          (info && info.methods.indexOf(method) >= 0);
        window.location.href = root + target + "/" + (keep && page ? page : "index.html");
      }).catch(function () {
        window.location.href = root + target + "/index.html";
      });
    });
  }

  var filter = document.querySelector(".side .filter");
  if (filter) {
    var side = document.querySelector(".side");
    filter.addEventListener("input", function () {
      var q = filter.value.trim().toLowerCase();
      side.classList.toggle("filtering", q !== "");
      side.querySelectorAll("details").forEach(function (d) {
        var shown = 0;
        d.querySelectorAll("li").forEach(function (li) {
          var hit = !q || li.textContent.toLowerCase().indexOf(q) >= 0;
          li.hidden = !hit;
          if (hit) shown++;
        });
        d.hidden = shown === 0;
        if (q) d.open = true;
      });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== filter && !/input|select|textarea/i.test(document.activeElement.tagName)) {
        e.preventDefault();
        filter.focus();
      }
    });
  }
})();
