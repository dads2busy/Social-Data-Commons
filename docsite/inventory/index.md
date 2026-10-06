---
hide:
  - navigation
  - toc
---

# Data inventory

Every measure published on the two dashboards, with the geographic levels and
years it is available for. The table is generated from the data the dashboards
actually serve, so it reflects the current state of the commons rather than a
hand-maintained list.

**Open source.** The data are open and publicly accessible. The code that
ingests each raw source and prepares each measure is committed alongside the
output files in the
[Social-Data-Commons repository](https://github.com/dads2busy/Social-Data-Commons),
together with metadata, provenance, and validation reports for every pipeline.

**Widely available.** Measures can be downloaded from either dashboard, read
directly from the repository as compressed CSV files, and cited by DOI from
versioned releases archived to Zenodo.

<div class="inventory" markdown="0">
  <div class="inventory-controls">
    <input id="inv-search" type="search" placeholder="Search measures…" aria-label="Search measures">
    <select id="inv-category" aria-label="Filter by category">
      <option value="">All categories</option>
    </select>
    <div class="inventory-sites" role="radiogroup" aria-label="Dashboard">
      <label><input type="radio" name="inv-site" value="" checked> Both</label>
      <label><input type="radio" name="inv-site" value="ncr"> NCR only</label>
      <label><input type="radio" name="inv-site" value="va"> Virginia only</label>
    </div>
    <span id="inv-count" class="inventory-count"></span>
  </div>
  <div class="inventory-scroll">
    <table id="inv-table" class="inventory-table">
      <thead></thead>
      <tbody></tbody>
    </table>
  </div>
  <p class="inventory-foot">
    A check mark means the measure has at least one year of data at that level; hover it for the years.
    <span class="inv-geo10">2010</span> marks measures also published on original 2010 census tract boundaries.
    Business climate measures broken out by industry are collapsed under their all-industry measure.
    Generated <span id="inv-generated"></span> by <code>tools/build_data_inventory.py</code>.
  </p>
</div>

<script>
(function () {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const span = (y) => (y[0] === y[1] ? String(y[0]) : y[0] + "–" + y[1]);

  fetch("inventory.json")
    .then((r) => r.json())
    .then(init)
    .catch((e) => { $("#inv-count").textContent = "Could not load inventory.json (" + e + ")"; });

  function init(data) {
    const sites = data.sites;
    const rows = data.rows;
    const byKey = new Map(rows.map((r) => [r.key, r]));
    const children = new Map();
    for (const r of rows) {
      if (r.group) {
        if (!children.has(r.group)) children.set(r.group, []);
        children.get(r.group).push(r);
      }
    }
    for (const list of children.values()) list.sort((a, b) => a.label.localeCompare(b.label));
    const parents = rows.filter((r) => !r.group);
    const expanded = new Set();

    $("#inv-generated").textContent = data.generated;
    const sel = $("#inv-category");
    for (const c of data.categories) {
      const o = document.createElement("option");
      o.value = c; o.textContent = c; sel.appendChild(o);
    }

    // Filters are mirrored in the URL (?search=…&category=…&site=…) so a view can be shared.
    const params = new URLSearchParams(location.search);
    $("#inv-search").value = params.get("search") || "";
    if (data.categories.includes(params.get("category"))) $("#inv-category").value = params.get("category");
    const siteParam = params.get("site") || "";
    const siteRadio = document.querySelector('input[name="inv-site"][value="' + siteParam + '"]');
    if (siteRadio) siteRadio.checked = true;

    function syncUrl(q, cat, site) {
      const p = new URLSearchParams();
      if (q) p.set("search", q);
      if (cat) p.set("category", cat);
      if (site) p.set("site", site);
      const qs = p.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    }

    function activeSites() {
      const v = document.querySelector('input[name="inv-site"]:checked').value;
      return v ? sites.filter((s) => s.key === v) : sites;
    }

    function renderHead(shown) {
      let h1 = '<tr><th rowspan="2">Category</th><th rowspan="2">Measure</th><th rowspan="2">Years</th>';
      let h2 = "<tr>";
      for (const s of shown) {
        h1 += '<th colspan="' + s.levels.length + '" class="inv-site">' + esc(s.label) + "</th>";
        for (const l of s.levels) h2 += '<th class="inv-level"><span>' + esc(l.label) + "</span></th>";
      }
      $("#inv-table thead").innerHTML = h1 + "</tr>" + h2 + "</tr>";
    }

    function matches(r, q, cat) {
      if (cat && r.category !== cat) return false;
      if (!q) return true;
      return (r.label + " " + r.key + " " + r.description + " " + r.category).toLowerCase().includes(q);
    }

    function hasData(r, shown) {
      return shown.some((s) => s.levels.some((l) => r.levels[l.key]));
    }

    function rowHtml(r, shown, cls, toggle) {
      let html = '<tr class="' + cls + '"><td class="inv-cat">' + esc(r.category) + '</td><td class="inv-measure">';
      if (toggle) html += toggle;
      html += '<span title="' + esc(r.key + (r.description ? " — " + r.description : "")) + '">' + esc(r.label) + "</span>";
      if (r.geo10) html += ' <span class="inv-geo10" title="Also available on original 2010 census tract boundaries">2010</span>';
      html += '</td><td class="inv-years">' + span(r.years) + "</td>";
      for (const s of shown) {
        for (const l of s.levels) {
          const y = r.levels[l.key];
          html += y ? '<td class="inv-check" title="' + esc(l.label + ": " + span(y)) + '">✓</td>' : '<td class="inv-check"></td>';
        }
      }
      return html + "</tr>";
    }

    function render() {
      const q = $("#inv-search").value.trim().toLowerCase();
      const cat = $("#inv-category").value;
      const shown = activeSites();
      syncUrl($("#inv-search").value.trim(), cat, document.querySelector('input[name="inv-site"]:checked').value);
      renderHead(shown);
      let html = "", shownCount = 0, total = 0;
      for (const p of parents) {
        const kids = (children.get(p.key) || []).filter((k) => hasData(k, shown));
        const parentVisible = hasData(p, shown) || kids.length > 0;
        if (!parentVisible) continue;
        total += 1 + kids.length;
        const kidMatches = kids.filter((k) => matches(k, q, cat));
        const parentMatch = matches(p, q, cat);
        if (!parentMatch && kidMatches.length === 0) continue;
        const open = expanded.has(p.key) || (q && kidMatches.length > 0 && !parentMatch);
        let toggle = "";
        if (kids.length) {
          toggle = '<button type="button" class="inv-toggle" data-key="' + esc(p.key) + '" aria-expanded="' + open + '">' +
            (open ? "▾" : "▸") + " by industry (" + kids.length + ")</button> ";
        }
        html += rowHtml(p, shown, "inv-parent", toggle);
        shownCount += 1;
        if (open) {
          const list = q || cat ? kidMatches : kids;
          for (const k of list) { html += rowHtml(k, shown, "inv-child", ""); shownCount += 1; }
        }
      }
      $("#inv-table tbody").innerHTML = html || '<tr><td colspan="99" class="inv-empty">No measures match.</td></tr>';
      $("#inv-count").textContent = "Showing " + shownCount + " of " + total + " measures";
    }

    $("#inv-table").addEventListener("click", (e) => {
      const b = e.target.closest(".inv-toggle");
      if (!b) return;
      const k = b.dataset.key;
      if (expanded.has(k)) expanded.delete(k); else expanded.add(k);
      render();
    });
    $("#inv-search").addEventListener("input", render);
    $("#inv-category").addEventListener("change", render);
    for (const r of document.querySelectorAll('input[name="inv-site"]')) r.addEventListener("change", render);
    render();
  }
})();
</script>
