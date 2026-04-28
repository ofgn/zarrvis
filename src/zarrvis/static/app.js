import { COLORMAP_NAMES, COLORMAPS } from "/static/colormaps.js";

const params = new URLSearchParams(location.search);
const token = params.get("token") ?? "";

const state = {
    path: null,
    tree: null,
    array: null, // ArrayInfo of the currently selected array
    indices: [], // length ndim; null for plotted axes
    axes: [0, 1], // row, col axis indices
    cmap: "viridis",
    vmin: 0,
    vmax: 1,
    autoContrast: true,
    maxPx: 1024,
    abortController: null,
    coords: {}, // axis index → {dim, values} (null values if not found)
};

/* --------- API helpers --------- */

function apiURL(path, extra = {}) {
    const url = new URL(path, location.origin);
    url.searchParams.set("token", token);
    for (const [k, v] of Object.entries(extra)) {
        if (v === undefined || v === null) continue;
        url.searchParams.set(k, typeof v === "string" ? v : JSON.stringify(v));
    }
    return url;
}

async function fetchJson(path, extra = {}) {
    const resp = await fetch(apiURL(path, extra));
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({
            error: { code: "Error", message: resp.statusText },
        }));
        throw err?.error ?? { code: "Error", message: "request failed" };
    }
    return resp.json();
}

async function fetchFrame(path, extra, signal) {
    const resp = await fetch(apiURL(path, extra), { signal });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({
            error: { code: "Error", message: resp.statusText },
        }));
        throw err?.error ?? { code: "Error", message: "request failed" };
    }
    const buf = await resp.arrayBuffer();
    return decodeFrame(buf);
}

function decodeFrame(buf) {
    const dv = new DataView(buf);
    const headerLen = dv.getUint32(0, true);
    const headerBytes = new Uint8Array(buf, 4, headerLen);
    const header = JSON.parse(new TextDecoder().decode(headerBytes));
    const payloadOffset = 4 + headerLen;
    const payloadLen = header.rows * header.cols;
    let payload;
    if (payloadOffset % 4 === 0) {
        payload = new Float32Array(buf, payloadOffset, payloadLen);
    } else {
        // Unaligned frame (shouldn't happen with current server; be defensive).
        const copy = buf.slice(payloadOffset, payloadOffset + payloadLen * 4);
        payload = new Float32Array(copy);
    }
    return { header, data: payload };
}

/* --------- Colormap --------- */

function colormapRGBA(data, rows, cols, vmin, vmax, name) {
    const lut = COLORMAPS[name] ?? COLORMAPS["viridis"];
    const span = vmax > vmin ? vmax - vmin : 1.0;
    const out = new Uint8ClampedArray(rows * cols * 4);
    for (let i = 0; i < data.length; i++) {
        const v = data[i];
        let idx, alpha;
        if (Number.isFinite(v)) {
            let s = (v - vmin) / span;
            if (s < 0) s = 0;
            else if (s > 1) s = 1;
            idx = Math.round(s * 255);
            alpha = 255;
        } else {
            idx = 0;
            alpha = 0;
        }
        const j = i * 4;
        const k = idx * 3;
        out[j] = lut[k];
        out[j + 1] = lut[k + 1];
        out[j + 2] = lut[k + 2];
        out[j + 3] = alpha;
    }
    return out;
}

/* --------- DOM helpers --------- */

const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined) continue;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k.startsWith("on") && typeof v === "function")
            node.addEventListener(k.slice(2).toLowerCase(), v);
        else if (k === "html") node.innerHTML = v;
        else node.setAttribute(k, v);
    }
    for (const c of [].concat(children)) {
        if (c === null || c === undefined) continue;
        node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return node;
};

function setStatus(text, kind = "") {
    const s = document.getElementById("status");
    s.textContent = text ?? "";
    s.className = "status" + (kind ? " is-" + kind : "");
}

function toast(title, message, hint, kind = "error") {
    const host = document.getElementById("toasts");
    const t = el("div", { class: `toast ${kind}` }, [
        el("div", { class: "t-title", text: title }),
        el("div", { class: "t-msg", text: message }),
        hint ? el("div", { class: "t-hint", text: hint }) : null,
    ]);
    host.appendChild(t);
    setTimeout(() => t.remove(), 6000);
}

/* --------- Tree --------- */

function renderTree(info, container, depth = 0) {
    if (info.kind === "array") {
        const usable = info.renderable && info.shape.length >= 2;
        const row = el("div", {
            class: "array" + (usable ? "" : " muted"),
            "data-path": info.path,
        }, [
            el("span", { class: "sigil", text: "⎘" }),
            el("span", { class: "node-name", text: info.name }),
            el("span", {
                class: "node-meta",
                text: `${info.shape.join("×")} ${info.dtype}`,
            }),
        ]);
        if (usable) {
            row.addEventListener("click", () => selectArray(info));
        } else if (info.unsupported_reason) {
            row.title = info.unsupported_reason;
        }
        container.appendChild(row);
        return;
    }
    const label = depth === 0 ? info.name : info.name;
    const grp = el("div", { class: "group" }, [
        el("span", { class: "sigil", text: "▸" }),
        el("span", { class: "node-name", text: label }),
        info.has_multiscales ? el("span", { class: "axis-badge", text: "pyramid" }) : null,
    ]);
    container.appendChild(grp);
    if (info.children && info.children.length) {
        const indent = el("div", { class: "indent" });
        container.appendChild(indent);
        for (const c of info.children) renderTree(c, indent, depth + 1);
    }
}

function flattenArrays(info, out = []) {
    if (info.kind === "array") {
        out.push(info);
    } else {
        for (const c of info.children ?? []) flattenArrays(c, out);
    }
    return out;
}

/* --------- Array selection & controls --------- */

function selectArray(info) {
    state.array = info;
    // default axes: last two
    const n = info.shape.length;
    state.axes = [n - 2, n - 1];
    state.indices = info.shape.map((_, i) =>
        i === state.axes[0] || i === state.axes[1] ? null : Math.floor(info.shape[i] / 2)
    );
    state.autoContrast = true;
    state.coords = {};

    // active highlight in tree
    document.querySelectorAll(".tree .array").forEach((n) => n.classList.remove("active"));
    document
        .querySelector(`.tree .array[data-path="${CSS.escape(info.path)}"]`)
        ?.classList.add("active");

    renderInfoStrip(info);
    renderControls(info);
    loadCoords(info);
    refreshPlot();
}

async function loadCoords(info) {
    if (!info.dims) return;
    const snapshot = info;
    const promises = info.dims.map(async (_, axis) => {
        try {
            const body = await fetchJson("/api/coords", {
                path: state.path,
                array: info.path,
                axis,
            });
            return [axis, body];
        } catch {
            return [axis, null];
        }
    });
    const results = await Promise.all(promises);
    if (state.array !== snapshot) return;
    for (const [axis, body] of results) {
        if (body) state.coords[axis] = body;
    }
    renderControls(info);
    drawPlot();
}

function coordLabel(axis, idx) {
    const c = state.coords[axis];
    if (!c || !c.values || c.values.length <= idx) return null;
    const v = c.values[idx];
    if (typeof v === "number") return fmt(v);
    return String(v);
}

function renderInfoStrip(info) {
    const strip = document.getElementById("info");
    const kv = (label, val) =>
        el("div", {}, [
            el("span", { class: "label", text: label }),
            el("span", { class: "val", text: val }),
        ]);
    strip.replaceChildren(
        kv("path", info.path),
        kv("shape", info.shape.join(" × ")),
        kv("dtype", info.dtype),
        kv("chunks", info.chunks ? info.chunks.join(" × ") : "—"),
        info.shards ? kv("shards", info.shards.join(" × ")) : null,
        info.dims ? kv("dims", info.dims.join(", ")) : null
    );
    if (info.unsupported_reason && info.renderable) {
        strip.appendChild(kv("note", info.unsupported_reason));
    }
}

function renderControls(info) {
    const root = document.getElementById("controls");
    root.replaceChildren();
    const ndim = info.shape.length;

    // --- axis pickers
    const rowAxis = el(
        "select",
        {
            onchange: (e) => {
                const i = Number(e.target.value);
                setAxis(0, i);
            },
        },
        []
    );
    const colAxis = el(
        "select",
        {
            onchange: (e) => {
                const i = Number(e.target.value);
                setAxis(1, i);
            },
        },
        []
    );
    for (let i = 0; i < ndim; i++) {
        const label = info.dims ? info.dims[i] : `axis ${i}`;
        rowAxis.appendChild(
            el("option", { value: i, selected: i === state.axes[0] ? "" : null, text: `${label} (${i})` })
        );
        colAxis.appendChild(
            el("option", { value: i, selected: i === state.axes[1] ? "" : null, text: `${label} (${i})` })
        );
    }
    const axisRow = el("div", { class: "row" }, [
        el("div", { class: "group" }, [
            el("label", { text: "Row axis" }),
            rowAxis,
        ]),
        el("div", { class: "group" }, [
            el("label", { text: "Col axis" }),
            colAxis,
        ]),
        el("div", { class: "group" }, [
            el("label", { text: "Colormap" }),
            cmapSelect(),
        ]),
        el("div", { class: "group" }, [
            el("label", { text: "Max px" }),
            maxPxSelect(),
        ]),
    ]);
    root.appendChild(axisRow);

    // --- dim sliders
    for (let i = 0; i < ndim; i++) {
        if (i === state.axes[0] || i === state.axes[1]) continue;
        const dim = info.dims ? info.dims[i] : `axis ${i}`;
        const extent = info.shape[i];
        const renderLabel = () => {
            const idx = state.indices[i];
            const coord = coordLabel(i, idx);
            return coord ? `${coord}  ·  ${idx}/${extent - 1}` : `${idx} / ${extent - 1}`;
        };
        const coord = el("span", { class: "dim-coord", text: renderLabel() });
        const slider = el("input", {
            type: "range",
            min: 0,
            max: extent - 1,
            value: state.indices[i] ?? 0,
            oninput: (e) => {
                state.indices[i] = Number(e.target.value);
                coord.textContent = renderLabel();
                scheduleRefresh();
            },
        });
        root.appendChild(
            el("div", { class: "dim-slider" }, [
                el("span", { class: "dim-name", text: dim }),
                slider,
                coord,
            ])
        );
    }

    // --- contrast
    const vminSlider = el("input", {
        type: "range",
        id: "vmin-slider",
        min: 0,
        max: 1000,
        value: 0,
        oninput: (e) => {
            state.autoContrast = false;
            const f = Number(e.target.value) / 1000;
            state.vmin = state.rangeMin + f * (state.rangeMax - state.rangeMin);
            vminLabel.textContent = fmt(state.vmin);
            recolor();
        },
    });
    const vmaxSlider = el("input", {
        type: "range",
        id: "vmax-slider",
        min: 0,
        max: 1000,
        value: 1000,
        oninput: (e) => {
            state.autoContrast = false;
            const f = Number(e.target.value) / 1000;
            state.vmax = state.rangeMin + f * (state.rangeMax - state.rangeMin);
            vmaxLabel.textContent = fmt(state.vmax);
            recolor();
        },
    });
    const vminLabel = el("span", { class: "value", id: "vmin-label", text: "—" });
    const vmaxLabel = el("span", { class: "value", id: "vmax-label", text: "—" });
    const autoBtn = el("button", {
        text: "auto",
        onclick: () => {
            state.autoContrast = true;
            refreshPlot();
        },
    });
    const contrastBlock = el("div", { class: "row" }, [
        el("div", { class: "group wide" }, [
            el("label", { text: "vmin" }),
            vminSlider,
            vminLabel,
        ]),
        el("div", { class: "group wide" }, [
            el("label", { text: "vmax" }),
            vmaxSlider,
            vmaxLabel,
        ]),
        el("div", { class: "group" }, [autoBtn]),
    ]);
    root.appendChild(contrastBlock);
}

function cmapSelect() {
    const s = el("select", {
        onchange: (e) => {
            state.cmap = e.target.value;
            recolor();
        },
    });
    for (const n of COLORMAP_NAMES) {
        s.appendChild(
            el("option", { value: n, selected: n === state.cmap ? "" : null, text: n })
        );
    }
    return s;
}

function maxPxSelect() {
    const s = el("select", {
        onchange: (e) => {
            state.maxPx = Number(e.target.value);
            refreshPlot();
        },
    });
    for (const n of [256, 512, 1024, 2048]) {
        s.appendChild(
            el("option", { value: n, selected: n === state.maxPx ? "" : null, text: n })
        );
    }
    return s;
}

function setAxis(which, axisIdx) {
    const other = state.axes[1 - which];
    if (axisIdx === other) {
        state.axes[1 - which] = state.axes[which];
    }
    state.axes[which] = axisIdx;
    // indices for plotted axes are null; others default to floor(extent/2)
    for (let i = 0; i < state.array.shape.length; i++) {
        if (i === state.axes[0] || i === state.axes[1]) {
            state.indices[i] = null;
        } else if (state.indices[i] === null) {
            state.indices[i] = Math.floor(state.array.shape[i] / 2);
        }
    }
    renderControls(state.array);
    refreshPlot();
}

/* --------- Plot --------- */

function fmt(v) {
    if (!Number.isFinite(v)) return String(v);
    if (Math.abs(v) >= 1e4 || (Math.abs(v) > 0 && Math.abs(v) < 1e-3)) return v.toExponential(2);
    return v.toPrecision(4).replace(/\.?0+$/, "");
}

let refreshTimer = null;
function scheduleRefresh() {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refreshPlot, 50);
}

async function refreshPlot() {
    if (!state.array || !state.path) return;
    if (state.abortController) state.abortController.abort();
    const controller = new AbortController();
    state.abortController = controller;

    setStatus("fetching slice…");
    try {
        const { header, data } = await fetchFrame(
            "/api/slice",
            {
                path: state.path,
                array: state.array.path,
                indices: state.indices,
                axes: state.axes,
                max_px: state.maxPx,
            },
            controller.signal
        );
        state.lastSlice = { header, data };
        state.rangeMin = header.vmin;
        state.rangeMax = header.vmax;
        writeUrlState();
        if (state.autoContrast) {
            // quick percentile-ish from the header range; the /api/stats call
            // refines this asynchronously without blocking the draw.
            state.vmin = header.vmin;
            state.vmax = header.vmax;
            updateContrastSliders();
            refineAutoContrast();
        }
        drawPlot();
        setStatus(
            `${header.rows}×${header.cols} · stride ${header.strides.join("×")}`,
            "ok"
        );
    } catch (exc) {
        if (exc?.name === "AbortError") return;
        const err = exc?.code ? exc : { code: "Error", message: String(exc?.message ?? exc) };
        toast(err.code, err.message, err.hint);
        setStatus(err.code, "error");
    }
}

async function refineAutoContrast() {
    const snapshotArray = state.array;
    try {
        const body = await fetchJson("/api/stats", {
            path: state.path,
            array: state.array.path,
            indices: state.indices,
            axes: state.axes,
            max_px: 512,
        });
        if (state.array !== snapshotArray || !state.autoContrast) return;
        state.vmin = body.stats.p02;
        state.vmax = body.stats.p98;
        updateContrastSliders();
        recolor();
    } catch {
        // non-fatal
    }
}

function updateContrastSliders() {
    const vminLabel = document.getElementById("vmin-label");
    const vmaxLabel = document.getElementById("vmax-label");
    const vminSlider = document.getElementById("vmin-slider");
    const vmaxSlider = document.getElementById("vmax-slider");
    if (!vminLabel) return;
    const span = state.rangeMax - state.rangeMin || 1;
    vminSlider.value = Math.round(((state.vmin - state.rangeMin) / span) * 1000);
    vmaxSlider.value = Math.round(((state.vmax - state.rangeMin) / span) * 1000);
    vminLabel.textContent = fmt(state.vmin);
    vmaxLabel.textContent = fmt(state.vmax);
}

function drawPlot() {
    const slice = state.lastSlice;
    if (!slice) return;
    const { header, data } = slice;
    const rgba = colormapRGBA(data, header.rows, header.cols, state.vmin, state.vmax, state.cmap);
    const z = new Array(header.rows);
    for (let r = 0; r < header.rows; r++) {
        const row = new Array(header.cols);
        for (let c = 0; c < header.cols; c++) {
            const j = (r * header.cols + c) * 4;
            row[c] = [rgba[j], rgba[j + 1], rgba[j + 2], rgba[j + 3]];
        }
        z[r] = row;
    }
    const trace = {
        type: "image",
        z,
        colormodel: "rgba",
        hoverinfo: "x+y+text",
        text: buildHoverText(data, header.rows, header.cols),
    };
    const dimsLabel = (i) => (state.array.dims ? state.array.dims[i] : `axis ${i}`);
    const layout = {
        margin: { l: 72, r: 20, t: 18, b: 48 },
        paper_bgcolor: "#0b0d10",
        plot_bgcolor: "#0b0d10",
        xaxis: {
            title: { text: dimsLabel(state.axes[1]), font: { color: "#8a93a6" } },
            color: "#8a93a6",
            gridcolor: "#1a1f29",
            scaleanchor: "y",
            scaleratio: 1,
            automargin: true,
            autorange: true,
            ...axisTicks(state.axes[1], header.cols, header.strides[1]),
        },
        yaxis: {
            title: { text: dimsLabel(state.axes[0]), font: { color: "#8a93a6" } },
            color: "#8a93a6",
            gridcolor: "#1a1f29",
            autorange: "reversed",
            automargin: true,
            ...axisTicks(state.axes[0], header.rows, header.strides[0]),
        },
        font: { family: "Inter, sans-serif", color: "#e7ebf3", size: 11 },
    };
    Plotly.react(
        "plot",
        [trace],
        layout,
        { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["select2d", "lasso2d"] }
    );
}

function axisTicks(axis, nPixels, stride) {
    const coord = state.coords[axis];
    if (!coord || !coord.values) return {};
    const nTicks = Math.min(7, nPixels);
    const tickvals = [];
    const ticktext = [];
    for (let i = 0; i < nTicks; i++) {
        const pixel = Math.round((i * (nPixels - 1)) / (nTicks - 1));
        const realIdx = pixel * stride;
        if (realIdx >= coord.values.length) continue;
        tickvals.push(pixel);
        const v = coord.values[realIdx];
        ticktext.push(typeof v === "number" ? fmt(v) : String(v));
    }
    return { tickmode: "array", tickvals, ticktext };
}

function buildHoverText(data, rows, cols) {
    const stride = Math.max(1, Math.floor((rows * cols) / 40000));
    if (stride === 1) {
        const out = new Array(rows);
        for (let r = 0; r < rows; r++) {
            const row = new Array(cols);
            for (let c = 0; c < cols; c++) {
                row[c] = fmt(data[r * cols + c]);
            }
            out[r] = row;
        }
        return out;
    }
    return undefined;
}

function recolor() {
    drawPlot();
}

/* --------- Open a store --------- */

async function openPath(path) {
    state.path = path;
    setStatus("loading tree…");
    try {
        const body = await fetchJson("/api/tree", { path });
        state.tree = body.tree;
        state.path = body.path;
        const container = document.getElementById("tree");
        container.replaceChildren();
        renderTree(state.tree, container);
        setStatus("ok", "ok");
        const first = flattenArrays(state.tree).find(
            (a) => a.renderable && a.shape.length >= 2
        );
        if (first) selectArray(first);
    } catch (exc) {
        const err = exc?.code ? exc : { code: "Error", message: String(exc?.message ?? exc) };
        toast(err.code, err.message, err.hint);
        setStatus(err.code, "error");
    }
}

/* --------- Bootstrap --------- */

function writeUrlState() {
    if (!state.path || !state.array) return;
    const search = new URLSearchParams(location.search);
    search.set("token", token);
    search.set("path", state.path);
    search.set("array", state.array.path);
    search.set("axes", JSON.stringify(state.axes));
    search.set("indices", JSON.stringify(state.indices));
    search.set("cmap", state.cmap);
    search.set("maxPx", String(state.maxPx));
    if (!state.autoContrast) {
        search.set("vmin", String(state.vmin));
        search.set("vmax", String(state.vmax));
    } else {
        search.delete("vmin");
        search.delete("vmax");
    }
    history.replaceState(null, "", `${location.pathname}?${search.toString()}`);
}

function readUrlState() {
    const p = new URLSearchParams(location.search);
    return {
        path: p.get("path"),
        array: p.get("array"),
        axes: safeJSON(p.get("axes")),
        indices: safeJSON(p.get("indices")),
        cmap: p.get("cmap"),
        maxPx: p.get("maxPx") ? Number(p.get("maxPx")) : null,
        vmin: p.get("vmin") ? Number(p.get("vmin")) : null,
        vmax: p.get("vmax") ? Number(p.get("vmax")) : null,
    };
}

function safeJSON(raw) {
    if (!raw) return null;
    try {
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

async function boot() {
    document.getElementById("version").textContent = "loading…";
    try {
        const health = await fetchJson("/api/health");
        document.getElementById("version").textContent = `v${health.version}`;
        const input = document.getElementById("path");
        document.getElementById("open-btn").addEventListener("click", () => {
            if (input.value.trim()) openPath(input.value.trim());
        });
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && input.value.trim()) openPath(input.value.trim());
        });
        const urlState = readUrlState();
        const initialPath = urlState.path ?? health.initial_path;
        if (initialPath) {
            input.value = initialPath;
            await openPath(initialPath);
            applyUrlState(urlState);
        }
    } catch (exc) {
        setStatus("auth failed", "error");
        toast(
            "Unauthorized",
            "session token missing or invalid",
            "reload from the zarrvis CLI URL"
        );
    }
}

function applyUrlState(urlState) {
    if (!urlState.array || !state.tree) return;
    const match = flattenArrays(state.tree).find((a) => a.path === urlState.array);
    if (!match) return;
    if (match !== state.array) selectArray(match);
    if (Array.isArray(urlState.axes) && urlState.axes.length === 2) {
        state.axes = [Number(urlState.axes[0]), Number(urlState.axes[1])];
    }
    if (Array.isArray(urlState.indices) && urlState.indices.length === match.shape.length) {
        state.indices = urlState.indices.map((v) => (v === null ? null : Number(v)));
    }
    if (urlState.cmap && COLORMAP_NAMES.includes(urlState.cmap)) state.cmap = urlState.cmap;
    if (urlState.maxPx) state.maxPx = urlState.maxPx;
    if (urlState.vmin !== null && urlState.vmax !== null) {
        state.vmin = urlState.vmin;
        state.vmax = urlState.vmax;
        state.autoContrast = false;
    }
    renderControls(match);
    refreshPlot();
}

boot();
