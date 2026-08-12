// Reader behaviour: theme, typography, keyboard shortcuts, reading-position save AND restore,
// reading progress, and an inline quick-add popup.
//
// localStorage holds UI preferences only (theme, text size). Reading data -- the position in a
// chapter -- always goes through the API, per the project rule against storing anything that
// matters client-side.

(function () {
  "use strict";

  // ---------------------------------------------------------------- theme

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("vr-theme", theme);
    } catch (e) { /* private mode */ }
  }

  function currentTheme() {
    var explicit = document.documentElement.dataset.theme;
    if (explicit) return explicit;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function toggleTheme() {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  }

  // ----------------------------------------------------------- typography

  var FONT_MIN = 0.9;
  var FONT_MAX = 1.8;
  var FONT_STEP = 0.05;
  var FONT_DEFAULT = 1.15;

  function readFontSize() {
    var stored = parseFloat(localStorage.getItem("vr-font-size"));
    return isNaN(stored) ? FONT_DEFAULT : stored;
  }

  function setFontSize(size) {
    var clamped = Math.min(FONT_MAX, Math.max(FONT_MIN, Math.round(size * 100) / 100));
    document.documentElement.style.setProperty("--reader-font-size", clamped + "rem");
    try {
      localStorage.setItem("vr-font-size", String(clamped));
    } catch (e) { /* private mode */ }
  }

  function stepFontSize(direction) {
    try {
      setFontSize(readFontSize() + direction * FONT_STEP);
    } catch (e) {
      setFontSize(FONT_DEFAULT + direction * FONT_STEP);
    }
  }

  // ------------------------------------------------------- shortcuts help

  function shortcutsDialog() {
    return document.getElementById("shortcuts-dialog");
  }

  function toggleShortcuts(force) {
    var dialog = shortcutsDialog();
    if (!dialog) return;
    var show = typeof force === "boolean" ? force : dialog.hidden;
    dialog.hidden = !show;
  }

  // ------------------------------------------------------ reading progress

  function progressBar() {
    var bar = document.getElementById("reading-progress");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "reading-progress";
      document.body.appendChild(bar);
    }
    return bar;
  }

  function updateProgress() {
    var text = document.querySelector(".reader-text");
    var bar = progressBar();
    if (!text) {
      bar.style.width = "0";
      return;
    }
    var rect = text.getBoundingClientRect();
    var total = rect.height - window.innerHeight;
    var done = total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : 0;
    bar.style.width = done * 100 + "%";
  }

  // ------------------------------------------------- reading position I/O

  var POSITION_THROTTLE_MS = 3000;
  var readerState = null;

  function paragraphElements() {
    return readerState ? readerState.root.querySelectorAll(".reader-text p") : [];
  }

  function currentParagraphIndex() {
    var paragraphs = paragraphElements();
    var index = 0;
    for (var i = 0; i < paragraphs.length; i++) {
      if (paragraphs[i].getBoundingClientRect().top <= window.innerHeight / 2) index = i;
    }
    return index;
  }

  function savePosition(paraIndex) {
    if (!readerState) return;
    fetch("/api/position/" + encodeURIComponent(readerState.seriesKey), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: readerState.url, para_index: paraIndex }),
    }).catch(function () { /* position saving must never interrupt reading */ });
  }

  function restorePosition() {
    if (!readerState) return;
    var state = readerState;
    fetch("/api/position/" + encodeURIComponent(state.seriesKey))
      .then(function (resp) { return resp.ok ? resp.json() : null; })
      .then(function (data) {
        // Bail out if the reader was swapped out, or the user already started reading.
        if (!data || readerState !== state || state.userScrolled) return;
        // The position is stored per SERIES, so it may point at a different chapter of this
        // story. Only scroll when it belongs to the chapter actually on screen.
        if ((data.url || "") !== (state.url || "")) return;
        var index = data.para_index || 0;
        if (index <= 0) return;
        var paragraphs = paragraphElements();
        var target = paragraphs[Math.min(index, paragraphs.length - 1)];
        if (!target) return;
        target.scrollIntoView({ block: "start" });
        showPositionNote(index + 1);
      })
      .catch(function () { /* no saved position is a normal first read */ });
  }

  function showPositionNote(humanIndex) {
    var note = document.getElementById("position-restored");
    if (!note) return;
    note.textContent = "";
    var label = document.createElement("span");
    label.textContent = "Đã quay lại đoạn " + humanIndex + ".";
    var top = document.createElement("button");
    top.type = "button";
    top.textContent = "Về đầu chương";
    top.addEventListener("click", function () {
      window.scrollTo({ top: 0 });
      note.hidden = true;
    });
    note.appendChild(label);
    note.appendChild(top);
    note.hidden = false;
  }

  // ------------------------------------------------------------- reader

  function initReader() {
    var root = document.querySelector(".reader-root");
    if (!root) {
      readerState = null;
      progressBar().style.width = "0";
      return;
    }

    readerState = {
      root: root,
      seriesKey: root.dataset.seriesKey,
      url: root.dataset.url || "",
      chapterId: root.dataset.chapterId || "",
      userScrolled: false,
      initAt: Date.now(),
      lastSent: 0,
      pending: null,
    };

    updateProgress();
    restorePosition();
  }

  // Scrolls the page makes itself (reset-to-top after an HTMX swap, browser scroll restoration)
  // fire this handler too. Treating those as user activity would cancel position restore, so
  // only scrolls after the reader has settled count as the reader taking over.
  var SETTLE_MS = 600;

  function onScroll() {
    updateProgress();
    if (!readerState) return;
    if (Date.now() - readerState.initAt > SETTLE_MS) readerState.userScrolled = true;

    var paraIndex = currentParagraphIndex();
    var now = Date.now();
    var state = readerState;
    if (now - state.lastSent >= POSITION_THROTTLE_MS) {
      state.lastSent = now;
      savePosition(paraIndex);
    } else {
      clearTimeout(state.pending);
      state.pending = setTimeout(function () {
        state.lastSent = Date.now();
        savePosition(paraIndex);
      }, POSITION_THROTTLE_MS - (now - state.lastSent));
    }
  }

  // ------------------------------------------------------ feedback notes

  var lastSelectionInReader = "";

  function feedbackPanel() {
    return document.getElementById("feedback-panel");
  }

  function setValue(id, value) {
    var el = document.getElementById(id);
    if (el) el.value = value;
  }

  /** Fill the note form with whatever the reader is currently looking at. */
  function primeFeedbackContext() {
    var context = document.getElementById("feedback-context");
    var quoteBox = document.getElementById("feedback-quote");
    var result = document.getElementById("feedback-result");
    if (result) result.textContent = "";

    var quote = lastSelectionInReader;
    setValue("fb-quote", quote);
    if (quoteBox) {
      quoteBox.textContent = quote;
      quoteBox.hidden = !quote;
    }

    if (!readerState) {
      setValue("fb-chapter-id", "");
      setValue("fb-chapter-title", "");
      setValue("fb-url", "");
      setValue("fb-para-index", "");
      if (context) context.textContent = "Không gắn với chương nào.";
      return;
    }

    var title = readerState.root.dataset.chapterTitle || "";
    var paraIndex = currentParagraphIndex();
    setValue("fb-chapter-id", readerState.chapterId);
    setValue("fb-chapter-title", title);
    setValue("fb-url", readerState.url);
    setValue("fb-para-index", String(paraIndex));
    if (context) {
      context.textContent = (title || "Chương này") + " · đoạn " + (paraIndex + 1);
    }
  }

  function toggleFeedback(force) {
    var panel = feedbackPanel();
    if (!panel) return;
    var show = typeof force === "boolean" ? force : panel.hidden;
    if (show) primeFeedbackContext();
    panel.hidden = !show;
    if (show) {
      var message = document.getElementById("fb-message");
      if (message) message.focus();
    }
  }

  function initFeedback() {
    var openBtn = document.getElementById("feedback-btn");
    if (openBtn) openBtn.addEventListener("click", function () { toggleFeedback(); });

    var closeBtn = document.getElementById("feedback-close");
    if (closeBtn) closeBtn.addEventListener("click", function () { toggleFeedback(false); });

    // Clear the textarea once the note has been stored, so the next note starts clean.
    document.addEventListener("htmx:afterRequest", function (event) {
      if (!event.target || event.target.id !== "feedback-form") return;
      if (!event.detail || !event.detail.successful) return;
      var message = document.getElementById("fb-message");
      if (message) message.value = "";
      lastSelectionInReader = "";
    });
  }

  // ---------------------------------------------------------- quick add

  function closeQuickAdd() {
    var existing = document.getElementById("quick-add-popup");
    if (existing) existing.remove();
  }

  function buildQuickAddPopup(term, rect) {
    var popup = document.createElement("div");
    popup.id = "quick-add-popup";
    popup.className = "quick-add-popup";
    popup.style.left = Math.min(window.scrollX + rect.left, window.scrollX + window.innerWidth - 280) + "px";
    popup.style.top = window.scrollY + rect.bottom + 6 + "px";

    var label = document.createElement("div");
    label.className = "quick-add-term";
    label.textContent = "Thêm “" + term + "” vào từ điển:";
    popup.appendChild(label);

    var actions = document.createElement("div");
    actions.className = "quick-add-actions";
    popup.appendChild(actions);

    var body = document.createElement("div");
    popup.appendChild(body);

    [
      { policy: "keep", label: "KEEP", hint: "Bảo vệ, không bao giờ thay" },
      { policy: "replace", label: "REPLACE", hint: "Thay bằng một từ cố định" },
      { policy: "ask", label: "ASK", hint: "Hỏi LLM chọn trong các phương án" },
    ].forEach(function (option) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = option.label;
      btn.title = option.hint;
      btn.addEventListener("click", function () {
        renderPolicyForm(body, term, option);
      });
      actions.appendChild(btn);
    });

    document.body.appendChild(popup);
    return popup;
  }

  function renderPolicyForm(container, term, option) {
    container.textContent = "";

    var form = document.createElement("form");
    form.className = "quick-add-form";

    var hint = document.createElement("div");
    hint.className = "quick-add-hint";
    hint.textContent = option.hint;
    form.appendChild(hint);

    var input = null;
    if (option.policy !== "keep") {
      input = document.createElement("input");
      input.type = "text";
      input.placeholder =
        option.policy === "replace" ? "Thay bằng..." : "Các phương án, phân cách bằng dấu phẩy";
      if (option.policy === "ask") input.value = term + ", ";
      form.appendChild(input);
    }

    var status = document.createElement("div");
    status.className = "quick-add-status";

    var submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "primary";
    submit.textContent = "Thêm";
    form.appendChild(submit);
    form.appendChild(status);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var payload = { surface: term, policy: option.policy };

      if (option.policy === "replace") {
        var replacement = input.value.trim();
        if (!replacement) {
          status.className = "quick-add-status error";
          status.textContent = "Cần nhập từ thay thế.";
          return;
        }
        payload.replacement = replacement;
      } else if (option.policy === "ask") {
        payload.candidates = input.value
          .split(",")
          .map(function (s) { return s.trim(); })
          .filter(Boolean);
        if (payload.candidates.length < 2) {
          status.className = "quick-add-status error";
          status.textContent = "ASK cần ít nhất 2 phương án.";
          return;
        }
      }

      status.className = "quick-add-status";
      status.textContent = "Đang thêm...";
      submitQuickAdd(payload, status);
    });

    container.appendChild(form);
    if (input) input.focus();
  }

  function submitQuickAdd(payload, status) {
    fetch("/api/dictionary/quick-add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (resp) {
        if (resp.ok) return null;
        return resp.json().then(function (data) {
          throw new Error(data && data.error ? data.error.message : resp.statusText);
        });
      })
      .then(function () {
        status.textContent = "Đã thêm. Đang xử lý lại chương...";
        reprocessCurrentChapter(status);
      })
      .catch(function (err) {
        status.className = "quick-add-status error";
        status.textContent = "Lỗi: " + err.message;
      });
  }

  function reprocessCurrentChapter(status) {
    // The dictionary changed, so the rendered chapter is stale. Rebuild it from the stored raw
    // text -- no refetch of the source site.
    if (!readerState || !readerState.chapterId) {
      status.textContent = "Đã thêm. Đọc lại chương để thấy thay đổi.";
      return;
    }
    var container = document.getElementById("reader-container");
    if (!container || !window.htmx) {
      status.textContent = "Đã thêm. Tải lại trang để thấy thay đổi.";
      return;
    }
    window.htmx
      .ajax("POST", "/reader/" + readerState.chapterId + "/reprocess", {
        target: "#reader-container",
        swap: "innerHTML",
      })
      .then(function () { closeQuickAdd(); });
  }

  /** Vùng chữ đang được bôi đen, nếu nó nằm trong nội dung chương. */
  function selectionInReader() {
    var selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;

    var node = selection.anchorNode;
    var element = node && (node.nodeType === 1 ? node : node.parentElement);
    if (!element || !element.closest(".reader-text")) return null;

    var text = selection.toString().trim();
    return text ? { text: text, range: selection.getRangeAt(0) } : null;
  }

  var SELECTION_SETTLE_MS = 350;

  function initQuickAdd() {
    var timer = null;

    // Dùng selectionchange chứ KHÔNG dùng mouseup: trên điện thoại, bôi đen là nhấn giữ rồi kéo
    // hai tay cầm, lúc đó mouseup hoặc không bắn ra, hoặc bắn trước khi chọn xong nên popup
    // hiện với vùng chọn sai. selectionchange chạy đúng cho cả chuột lẫn cảm ứng; nó bắn rất
    // dày trong lúc kéo nên phải chờ vùng chọn ổn định rồi mới xử lý.
    document.addEventListener("selectionchange", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var picked = selectionInReader();
        if (!picked) return;

        // Nhớ lại dù dài hay ngắn: đoạn dài thì vô dụng cho từ điển nhưng lại đúng là thứ
        // muốn trích vào ghi chú về một chỗ thay từ chưa ổn.
        lastSelectionInReader = picked.text;
        closeQuickAdd();
        if (picked.text.length > 60) return;

        buildQuickAddPopup(picked.text, picked.range.getBoundingClientRect());
      }, SELECTION_SETTLE_MS);
    });

    // Chạm hoặc bấm ra ngoài thì đóng. pointerdown bắt được cả chuột lẫn ngón tay.
    document.addEventListener("pointerdown", function (event) {
      if (!event.target.closest("#quick-add-popup")) closeQuickAdd();
    });
  }

  // ---------------------------------------------------------- shortcuts

  function isTyping(target) {
    if (!target) return false;
    var tag = target.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
  }

  function clickIfPresent(selector) {
    var el = document.querySelector(selector);
    if (el) el.click();
  }

  function initShortcuts() {
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeQuickAdd();
        toggleShortcuts(false);
        toggleFeedback(false);
        return;
      }
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;

      switch (event.key) {
        case "n": clickIfPresent(".nav-next"); break;
        case "p": clickIfPresent(".nav-prev"); break;
        case "h": clickIfPresent(".toggle-highlight"); break;
        case "o": clickIfPresent(".toggle-original"); break;
        case "d": toggleTheme(); break;
        case "f": toggleFeedback(); break;
        case "+":
        case "=": stepFontSize(1); break;
        case "-": stepFontSize(-1); break;
        case "?": toggleShortcuts(); break;
        default: return;
      }
      event.preventDefault();
    });
  }

  function initChrome() {
    var themeBtn = document.getElementById("theme-btn");
    if (themeBtn) themeBtn.addEventListener("click", toggleTheme);

    var helpBtn = document.getElementById("shortcuts-btn");
    if (helpBtn) helpBtn.addEventListener("click", function () { toggleShortcuts(); });

    var closeBtn = document.getElementById("shortcuts-close");
    if (closeBtn) closeBtn.addEventListener("click", function () { toggleShortcuts(false); });

    var dialog = shortcutsDialog();
    if (dialog) {
      dialog.addEventListener("click", function (event) {
        if (event.target === dialog) toggleShortcuts(false);
      });
    }

    document.addEventListener("click", function (event) {
      var target = event.target.closest("#font-bigger, #font-smaller");
      if (!target) return;
      stepFontSize(target.id === "font-bigger" ? 1 : -1);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initChrome();
    initShortcuts();
    initQuickAdd();
    initFeedback();
    initReader();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", updateProgress, { passive: true });
  });

  document.addEventListener("htmx:afterSwap", function () {
    closeQuickAdd();
    // Land at the top of the new chapter first; initReader may then restore a saved position.
    window.scrollTo({ top: 0 });
    initReader();
  });
})();
