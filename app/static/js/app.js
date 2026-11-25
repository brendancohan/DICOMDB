(function () {
  // Sync "Editor Initials" across all forms via localStorage
  const editorInput = document.getElementById("global-editor-label");
  if (editorInput) {
    const saved = localStorage.getItem("dicomdb_editor_label") || "";
    editorInput.value = saved;
    editorInput.addEventListener("input", () => {
      localStorage.setItem("dicomdb_editor_label", editorInput.value.trim());
    });
  }

  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    const label = localStorage.getItem("dicomdb_editor_label") || "";
    if (!label) return;
    let hidden = form.querySelector('input[name="editor_label"]');
    if (!hidden) {
      hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "editor_label";
      form.appendChild(hidden);
    }
    hidden.value = label;
  });

  // Column visibility toggles on inventory table
  const colToggles = document.querySelectorAll(".col-toggle");
  colToggles.forEach((cb) => {
    const colKey = cb.dataset.col;
    const savedState = localStorage.getItem("dicomdb_col_" + colKey);
    if (savedState !== null) {
      cb.checked = savedState === "1";
    }
    const applyVisibility = () => {
      document.querySelectorAll('[data-col-cell="' + colKey + '"]').forEach((el) => {
        el.style.display = cb.checked ? "" : "none";
      });
      localStorage.setItem("dicomdb_col_" + colKey, cb.checked ? "1" : "0");
    };
    applyVisibility();
    cb.addEventListener("change", applyVisibility);
  });
})();

async function runConnectivityTest(url, payload, resultElId) {
  const el = document.getElementById(resultElId);
  if (el) {
    el.textContent = "Testing...";
    el.className = "test-result muted";
  }
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (el) {
      el.textContent = data.message || (data.ok ? "OK" : "Failed");
      el.className = "test-result " + (data.ok ? "test-ok" : "test-fail");
    }
  } catch (err) {
    if (el) {
      el.textContent = "Request failed: " + err;
      el.className = "test-result test-fail";
    }
  }
}

function addAeRow() {
  const container = document.getElementById("ae-rows");
  const tpl = document.getElementById("ae-row-template");
  if (container && tpl) {
    container.appendChild(tpl.content.cloneNode(true));
  }
}

function addRouteRow() {
  const container = document.getElementById("route-rows");
  const tpl = document.getElementById("route-row-template");
  if (container && tpl) {
    container.appendChild(tpl.content.cloneNode(true));
  }
}
