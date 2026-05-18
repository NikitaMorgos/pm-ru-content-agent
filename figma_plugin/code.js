// PM-RU Content Agent – Figma Plugin (main thread)
// Thin executor: all business logic lives in plugin_ui.html served from Railway.
// This file should rarely (ideally never) need to be updated.
figma.showUI(__html__, { width: 440, height: 640, title: "PM-RU Content Agent" });

// ── Font loading ────────────────────────────────────────────────────────────
const _loadedFonts = new Set();

async function ensureFont(fontName) {
  if (fontName === figma.mixed) return;
  const key = `${fontName.family}::${fontName.style}`;
  if (!_loadedFonts.has(key)) {
    try { await figma.loadFontAsync(fontName); _loadedFonts.add(key); } catch(e) {}
  }
}

async function loadNodeFonts(node) {
  if (node.fontName !== figma.mixed) {
    await ensureFont(node.fontName);
  } else {
    for (let i = 0; i < node.characters.length; i++) {
      const fn = node.getRangeFontName(i, i + 1);
      if (fn !== figma.mixed) await ensureFont(fn);
    }
  }
}

async function preloadFonts(node) {
  if (node.type === "TEXT") await loadNodeFonts(node);
  if ("children" in node) {
    for (const child of node.children) await preloadFonts(child);
  }
}

// ── Structural node mapping ─────────────────────────────────────────────────
// Build a direct template-nodeId → clone-nodeId map.
// clone() in Figma always produces a perfect structural copy, so parallel
// traversal is 100% reliable — no search/fallback strategies needed.
function buildNodeMap(templateNode, cloneNode, map) {
  if (!map) map = {};
  map[templateNode.id] = cloneNode.id;
  if ("children" in templateNode && "children" in cloneNode) {
    const len = Math.min(templateNode.children.length, cloneNode.children.length);
    for (let i = 0; i < len; i++) {
      buildNodeMap(templateNode.children[i], cloneNode.children[i], map);
    }
  }
  return map;
}

// ── Image utilities ─────────────────────────────────────────────────────────
function findLargestImageNode(frame) {
  let target = null, maxArea = 0;
  function walk(n) {
    if ("fills" in n && Array.isArray(n.fills) && n.fills.some(f => f.type === "IMAGE")) {
      const area = (n.width || 0) * (n.height || 0);
      if (area > maxArea) { target = n; maxArea = area; }
    }
    if ("children" in n) n.children.forEach(walk);
  }
  walk(frame);
  return target;
}

// ── Results page ────────────────────────────────────────────────────────────
function getOrCreateResultsPage() {
  let page = figma.root.children.find(p => p.name === "🤖 Pipeline Results");
  if (!page) {
    page = figma.createPage();
    page.name = "🤖 Pipeline Results";
  }
  return page;
}

// ── Message handler ─────────────────────────────────────────────────────────
figma.ui.onmessage = async (msg) => {

  // ── Slide order (for correct sequencing) ──────────────────────────────────
  if (msg.type === "get-slide-order") {
    const frameIds = Array.isArray(msg.frameIds) ? msg.frameIds : [];
    const order = frameIds
      .map(id => figma.getNodeById(id))
      .filter(Boolean)
      .map(n => ({ id: n.id, x: n.x || 0, y: n.y || 0 }))
      .sort((a, b) => (a.y - b.y) || (a.x - b.x))
      .map(({ id }) => id);
    figma.ui.postMessage({ type: "slide-order", jobId: msg.jobId, order });
    return;
  }

  // ── Cleanup job frames ────────────────────────────────────────────────────
  if (msg.type === "cleanup-job") {
    const page = getOrCreateResultsPage();
    const prefix = `${msg.jobId} / `;
    page.children
      .filter(n => typeof n.name === "string" && n.name.startsWith(prefix))
      .forEach(n => n.remove());
    figma.ui.postMessage({ type: "cleanup-job-done", jobId: msg.jobId });
    return;
  }

  // ── Zoom to results page ──────────────────────────────────────────────────
  if (msg.type === "zoom-to-results") {
    const page = figma.root.children.find(p => p.name === "🤖 Pipeline Results");
    if (page) {
      await figma.setCurrentPageAsync(page);
      const prefix = msg.jobId ? `${msg.jobId} / ` : null;
      const frames = prefix
        ? page.children.filter(n => typeof n.name === "string" && n.name.startsWith(prefix))
        : [...page.children];
      if (frames.length > 0) figma.viewport.scrollAndZoomIntoView(frames);
    }
    figma.ui.postMessage({ type: "zoom-done", jobId: msg.jobId });
    return;
  }

  // ── Process one slide ─────────────────────────────────────────────────────
  if (msg.type === "process-slide") {
    const { jobId, slideType, frameId, textValues, photoBytes } = msg;

    const templateFrame = figma.getNodeById(frameId);
    if (!templateFrame) {
      figma.ui.postMessage({ type: "slide-error", jobId, slideType,
        error: `Frame ${frameId} not found in this Figma file` });
      return;
    }

    // 1. Pre-load fonts
    figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "fonts" });
    await preloadFonts(templateFrame);

    // 2. Clone to Results page
    figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "clone" });
    const resultsPage = getOrCreateResultsPage();
    const workFrame = templateFrame.clone();
    workFrame.name = `${jobId} / ${slideType}`;
    const existing = resultsPage.children;
    workFrame.x = existing.length > 0
      ? existing[existing.length - 1].x + existing[existing.length - 1].width + 40
      : 0;
    workFrame.y = 0;
    resultsPage.appendChild(workFrame);

    // Build structural mapping: template node IDs → clone node IDs
    const nodeMap = buildNodeMap(templateFrame, workFrame);

    // 3. Fill text nodes
    figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "text" });
    let textSet = 0, textFailed = 0;
    for (const [templateNodeId, value] of Object.entries(textValues || {})) {
      if (!value) continue;
      const cloneNodeId = nodeMap[templateNodeId];
      if (!cloneNodeId) {
        textFailed++;
        console.warn(`[text] no mapping for template node: ${templateNodeId}`);
        continue;
      }
      const node = figma.getNodeById(cloneNodeId);
      if (!node || node.type !== "TEXT") { textFailed++; continue; }
      try {
        await loadNodeFonts(node);
        node.characters = String(value);
        textSet++;
      } catch(e) {
        textFailed++;
        console.error(`[text] set failed:`, e);
      }
    }
    figma.ui.postMessage({
      type: "slide-progress", jobId, slideType,
      step: "text", detail: `${textSet} нодов заполнено, ${textFailed} пропущено`
    });

    // 4. Replace / mark photo
    const imgTarget = findLargestImageNode(workFrame);
    if (photoBytes && photoBytes.length) {
      figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "photo" });
      if (imgTarget) {
        const figmaImg = figma.createImage(new Uint8Array(photoBytes));
        const fills = JSON.parse(JSON.stringify(imgTarget.fills));
        const idx = fills.findIndex(f => f.type === "IMAGE");
        if (idx >= 0) {
          fills[idx] = { type: "IMAGE", scaleMode: "FILL", imageHash: figmaImg.hash };
          imgTarget.fills = fills;
        }
      }
    } else {
      if (imgTarget) {
        imgTarget.fills = [{ type: "SOLID", color: { r: 1, g: 0.2, b: 0.2 }, opacity: 0.3 }];
      }
      figma.ui.postMessage({
        type: "slide-progress", jobId, slideType,
        step: "photo", detail: "⚠ фото не загружено — красная заливка"
      });
    }

    // 5. Export
    figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "export" });
    try {
      const heavySlide = slideType === "upholstery_material" || slideType === "legs_material";
      const scale = heavySlide ? 0.9 : 1;
      let bytes = await Promise.race([
        workFrame.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: scale } }),
        new Promise((_, reject) => setTimeout(() => reject(new Error("export timeout 120s")), 120000)),
      ]);
      if (!bytes || bytes.length === 0) {
        bytes = await Promise.race([
          workFrame.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: 0.75 } }),
          new Promise((_, reject) => setTimeout(() => reject(new Error("export timeout 120s")), 120000)),
        ]);
      }
      figma.ui.postMessage({ type: "slide-done", jobId, slideType, bytes: Array.from(bytes) });
    } catch(e) {
      figma.ui.postMessage({ type: "slide-error", jobId, slideType, error: String(e) });
    }
    return;
  }

  // ── Full cleanup ──────────────────────────────────────────────────────────
  if (msg.type === "cleanup") {
    const page = figma.root.children.find(p => p.name === "🤖 Pipeline Results");
    if (page) { page.children.forEach(n => n.remove()); }
    figma.ui.postMessage({ type: "cleanup-done" });
    return;
  }

  if (msg.type === "close") figma.closePlugin();
};
