(function () {
  function getFuelText(fuelSelect) {
    // 1) Normal <option> text
    try {
      const opt = fuelSelect.options[fuelSelect.selectedIndex];
      const t = (opt && opt.text ? opt.text : "").trim();
      if (t) return t;
    } catch (e) {}

    // 2) Select2 rendered text (autocomplete_fields)
    const fieldWrap = fuelSelect.closest(".form-row, .field-fuel, td, div");
    if (fieldWrap) {
      const rendered = fieldWrap.querySelector(".select2-selection__rendered");
      const t2 = (rendered && rendered.textContent ? rendered.textContent : "").trim();
      if (t2) return t2;
    }

    // 3) Fallback: nothing
    return "";
  }

  function getFieldRowByInput(inline, inputNameSuffix) {
    // id$ ve name$ ile yakala (stacked/tabular fark etmez)
    const input =
      inline.querySelector(`input[name$="${inputNameSuffix}"]`) ||
      inline.querySelector(`input[id$="${inputNameSuffix}"]`);
    if (!input) return null;

    // StackedInline: .form-row
    const fr = input.closest(".form-row");
    if (fr) return fr;

    // TabularInline: td
    const td = input.closest("td");
    if (td) return td;

    // Son çare: bir üst div
    return input.parentElement || null;
  }

  function toggleInline(inline) {
    const fuelSelect = inline.querySelector('select[name$="-fuel"]');
    if (!fuelSelect) return;

    const text = getFuelText(fuelSelect);
    const upper = (text || "").toUpperCase();

    const isLng = upper.includes("LNG");
    const isCert = upper.includes("CERT");

    const ch4Wrap = getFieldRowByInput(inline, "-ch4_slip_pct");
    const n2oWrap = getFieldRowByInput(inline, "-n2o_factor");

    const ch4Input = inline.querySelector('input[name$="-ch4_slip_pct"]');
    const n2oInput = inline.querySelector('input[name$="-n2o_factor"]');

    // show/hide wrappers
    [ch4Wrap, n2oWrap].forEach((w) => {
      if (!w) return;
      w.style.display = isLng ? "" : "none";
    });

    // LNG değilse temizle
    if (!isLng) {
      if (ch4Input) { ch4Input.value = ""; ch4Input.disabled = false; }
      if (n2oInput) { n2oInput.value = ""; n2oInput.disabled = false; }
      return;
    }

    // LNG ise:
    if (!isCert) {
      // Otto/Diesel -> otomatik doldur + kilitle
      if (upper.includes("OTTO")) {
        if (ch4Input) ch4Input.value = "3.1";
        if (n2oInput) n2oInput.value = "0.00011";
      } else if (upper.includes("DIESEL")) {
        if (ch4Input) ch4Input.value = "0.2";
        if (n2oInput) n2oInput.value = "0.00011";
      }
      if (ch4Input) ch4Input.disabled = true;
      if (n2oInput) n2oInput.disabled = true;
    } else {
      // Certified -> kullanıcı girer
      if (ch4Input) { ch4Input.disabled = false; ch4Input.value = ""; }
      if (n2oInput) { n2oInput.disabled = false; n2oInput.value = ""; }
    }
  }

  function init() {
    // İlk yüklemede tüm inline’ları uygula
    document.querySelectorAll(".inline-related").forEach(toggleInline);

    // Normal change event (select)
    document.addEventListener("change", function (e) {
      if (e.target && e.target.matches('select[name$="-fuel"]')) {
        const inline = e.target.closest(".inline-related");
        if (inline) setTimeout(() => toggleInline(inline), 0);
      }
    });

    // Select2 event (autocomplete_fields) - Django admin jQuery ile
    if (window.django && window.django.jQuery) {
      const $ = window.django.jQuery;
      $(document).on("select2:select select2:clear", 'select[name$="-fuel"]', function () {
        const inline = this.closest(".inline-related");
        if (inline) setTimeout(() => toggleInline(inline), 0);
      });
    }

    // Yeni inline eklenince
    document.addEventListener("formset:added", function (e) {
      const inline = e.target;
      if (inline) setTimeout(() => toggleInline(inline), 0);
    });
  }

  window.addEventListener("load", init);
})();