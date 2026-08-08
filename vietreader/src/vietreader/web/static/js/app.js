// Quick-add popup (select text in the reader -> popup with KEEP/REPLACE/ASK) and
// throttled reading-position save. No localStorage for anything that matters -- position
// is written through the API (spec: "Không dùng localStorage cho dữ liệu quan trọng").

(function () {
  "use strict";

  function closeQuickAddPopup() {
    var existing = document.getElementById("quick-add-popup");
    if (existing) existing.remove();
  }

  function setupQuickAdd() {
    document.addEventListener("mouseup", function (event) {
      if (event.target.closest("#quick-add-popup")) return;
      var readerText = event.target.closest(".reader-text");
      closeQuickAddPopup();
      if (!readerText) return;

      var selection = window.getSelection();
      var text = selection ? selection.toString().trim() : "";
      if (!text || text.length > 60) return;

      var range = selection.getRangeAt(0);
      var rect = range.getBoundingClientRect();
      var popup = document.createElement("div");
      popup.id = "quick-add-popup";
      popup.className = "quick-add-popup";
      popup.style.left = window.scrollX + rect.left + "px";
      popup.style.top = window.scrollY + rect.bottom + 6 + "px";

      ["keep", "replace", "ask"].forEach(function (policy) {
        var btn = document.createElement("button");
        btn.textContent = policy.toUpperCase();
        btn.type = "button";
        btn.addEventListener("click", function () {
          quickAdd(text, policy);
          closeQuickAddPopup();
        });
        popup.appendChild(btn);
      });

      document.body.appendChild(popup);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeQuickAddPopup();
    });
  }

  function quickAdd(surface, policy) {
    var body = { surface: surface, policy: policy };
    if (policy === "replace") {
      var replacement = window.prompt("Thay \"" + surface + "\" bằng:", "");
      if (replacement === null) return;
      body.replacement = replacement;
    } else if (policy === "ask") {
      var raw = window.prompt(
        "Các lựa chọn cho \"" + surface + "\" (phân cách bằng dấu phẩy):",
        surface
      );
      if (raw === null) return;
      body.candidates = raw.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
      if (body.candidates.length < 2) {
        window.alert("ASK cần ít nhất 2 lựa chọn.");
        return;
      }
    }

    fetch("/api/dictionary/quick-add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (resp) {
      if (resp.ok) {
        window.alert('Đã thêm "' + surface + '" vào từ điển (' + policy.toUpperCase() + ").");
      } else {
        resp.json().then(function (data) {
          window.alert("Lỗi: " + (data.error ? data.error.message : resp.statusText));
        });
      }
    });
  }

  var POSITION_THROTTLE_MS = 3000;
  function setupPositionTracking() {
    var container = document.querySelector("[data-series-key]");
    if (!container) return;
    var seriesKey = container.dataset.seriesKey;
    var url = container.dataset.url;
    var lastSent = 0;
    var pending = null;

    function sendPosition(paraIndex) {
      fetch("/api/position/" + encodeURIComponent(seriesKey), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, para_index: paraIndex }),
      });
    }

    function onScroll() {
      var paragraphs = container.querySelectorAll(".reader-text p");
      var paraIndex = 0;
      for (var i = 0; i < paragraphs.length; i++) {
        var rect = paragraphs[i].getBoundingClientRect();
        if (rect.top <= window.innerHeight / 2) paraIndex = i;
      }
      var now = Date.now();
      if (now - lastSent >= POSITION_THROTTLE_MS) {
        lastSent = now;
        sendPosition(paraIndex);
      } else {
        clearTimeout(pending);
        pending = setTimeout(function () {
          lastSent = Date.now();
          sendPosition(paraIndex);
        }, POSITION_THROTTLE_MS - (now - lastSent));
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupQuickAdd();
    setupPositionTracking();
  });
  document.body.addEventListener("htmx:afterSwap", function () {
    setupPositionTracking();
  });
})();
