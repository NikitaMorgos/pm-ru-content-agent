// PM-RU Content Agent – Figma Plugin (main thread)
figma.showUI(__html__, { width: 440, height: 640, title: "PM-RU Content Agent" });

// ── Font cache ─────────────────────────────────────────────────────────────
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

// ── Node finding ───────────────────────────────────────────────────────────

// Strategy 1: structural path (index-based) – fast, breaks if structure differs
function getNodePath(root, target) {
  if (root.id === target.id) return [];
  if ("children" in root) {
    for (let i = 0; i < root.children.length; i++) {
      const sub = getNodePath(root.children[i], target);
      if (sub !== null) return [i, ...sub];
    }
  }
  return null;
}

function getNodeAtPath(root, path) {
  let node = root;
  for (const idx of path) {
    if (!("children" in node) || idx >= node.children.length) return null;
    node = node.children[idx];
  }
  return node;
}

// Strategy 2: name-based deep search – robust fallback
function findNodeByName(root, name) {
  if (root.name === name) return root;
  if ("children" in root) {
    for (const child of root.children) {
      const found = findNodeByName(child, name);
      if (found) return found;
    }
  }
  return null;
}

// Strategy 3: node ID suffix match – handles component copies
function findNodeByIdSuffix(root, originalId) {
  // In clones, node IDs are remapped but retain the same suffix pattern
  // e.g. original "4:2343" → clone "123:2343"
  const suffix = ':' + originalId.split(':')[1];
  function walk(n) {
    if (n.id && n.id.endsWith(suffix)) return n;
    if ("children" in n) {
      for (const child of n.children) {
        const r = walk(child);
        if (r) return r;
      }
    }
    return null;
  }
  return walk(root);
}

// Combined: try path → id-suffix → name
function findClonedNode(originalFrame, originalNode, clonedFrame) {
  // Strategy 1: path
  const path = getNodePath(originalFrame, originalNode);
  if (path !== null) {
    const byPath = getNodeAtPath(clonedFrame, path);
    if (byPath) return byPath;
  }
  // Strategy 2: id suffix (cloned nodes share the local part of id)
  const bySuffix = findNodeByIdSuffix(clonedFrame, originalNode.id);
  if (bySuffix) return bySuffix;
  // Strategy 3: name (last resort)
  if (originalNode.name) {
    const byName = findNodeByName(clonedFrame, originalNode.name);
    if (byName) return byName;
  }
  return null;
}

// ── Image replacement ──────────────────────────────────────────────────────

function findImageNodes(frame) {
  const results = [];
  function walk(n) {
    if ("fills" in n) {
      const imgFills = n.fills.filter(f => f.type === "IMAGE");
      if (imgFills.length > 0) results.push(n);
    }
    if ("children" in n) n.children.forEach(walk);
  }
  walk(frame);
  results.sort((a, b) => (b.width * b.height) - (a.width * a.height));
  return results;
}

async function replaceMainPhoto(frame, imageBytes) {
  const imgNodes = findImageNodes(frame);
  if (!imgNodes.length) return false;
  const target = imgNodes[0];
  const figmaImg = figma.createImage(new Uint8Array(imageBytes));
  const fills = JSON.parse(JSON.stringify(target.fills));
  const idx = fills.findIndex(f => f.type === "IMAGE");
  if (idx >= 0) {
    fills[idx] = { type: "IMAGE", scaleMode: "FILL", imageHash: figmaImg.hash };
    target.fills = fills;
    return true;
  }
  return false;
}

// Mark image node with visible "no photo" indicator
function markPhotoMissing(frame) {
  const imgNodes = findImageNodes(frame);
  if (!imgNodes.length) return;
  const target = imgNodes[0];
  // Red semi-transparent overlay
  target.fills = [{ type: "SOLID", color: { r: 1, g: 0.2, b: 0.2 }, opacity: 0.3 }];
}

async function exportWithTimeout(frame, scaleValue, timeoutMs) {
  const exportPromise = frame.exportAsync({
    format: "PNG",
    constraint: { type: "SCALE", value: scaleValue },
  });
  const timeoutPromise = new Promise((_, reject) => {
    setTimeout(() => reject(new Error(`export timeout (${timeoutMs}ms)`)), timeoutMs);
  });
  return Promise.race([exportPromise, timeoutPromise]);
}

// ── Results page ───────────────────────────────────────────────────────────

function getOrCreateResultsPage() {
  let page = figma.root.children.find(p => p.name === "🤖 Pipeline Results");
  if (!page) {
    page = figma.createPage();
    page.name = "🤖 Pipeline Results";
  }
  return page;
}

// ── Main handler ───────────────────────────────────────────────────────────

figma.ui.onmessage = async (msg) => {

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

  if (msg.type === "cleanup-job") {
    const page = getOrCreateResultsPage();
    const prefix = `${msg.jobId} / `;
    page.children
      .filter(n => typeof n.name === "string" && n.name.startsWith(prefix))
      .forEach(n => n.remove());
    figma.ui.postMessage({ type: "cleanup-job-done", jobId: msg.jobId });
    return;
  }

  // Navigate Figma viewport to Results page and zoom to fit all frames
  if (msg.type === "zoom-to-results") {
    const page = figma.root.children.find(p => p.name === "🤖 Pipeline Results");
    if (page) {
      await figma.setCurrentPageAsync(page);
      const prefix = msg.jobId ? `${msg.jobId} / ` : null;
      const frames = prefix
        ? page.children.filter(n => typeof n.name === "string" && n.name.startsWith(prefix))
        : [...page.children];
      if (frames.length > 0) {
        figma.viewport.scrollAndZoomIntoView(frames);
      }
    }
    figma.ui.postMessage({ type: "zoom-done", jobId: msg.jobId });
    return;
  }

  if (msg.type === "process-slide") {
    const { jobId, slideType, frameId, textValues, photoBytes } = msg;

    const templateFrame = figma.getNodeById(frameId);
    if (!templateFrame) {
      figma.ui.postMessage({ type: "slide-error", jobId, slideType,
        error: `Frame ${frameId} not found in Figma file` });
      return;
    }

    // Step 1: pre-load fonts
    figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "fonts" });
    await preloadFonts(templateFrame);

    // Step 2: clone frame to Results page
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

    // Step 3: fill text (with 3-strategy fallback + logging)
    figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "text" });
    let textSet = 0, textFailed = 0;
    for (const [nodeId, value] of Object.entries(textValues)) {
      if (!value) continue;
      const originalNode = figma.getNodeById(nodeId);
      if (!originalNode) {
        textFailed++;
        console.warn(`[text] node not found: ${nodeId}`);
        continue;
      }
      const clonedNode = findClonedNode(templateFrame, originalNode, workFrame);
      if (!clonedNode) {
        textFailed++;
        console.warn(`[text] cloned node not found for: ${nodeId} (${originalNode.name})`);
        continue;
      }
      if (clonedNode.type !== "TEXT") {
        textFailed++;
        console.warn(`[text] node is not TEXT: ${nodeId}`);
        continue;
      }
      try {
        await loadNodeFonts(clonedNode);
        clonedNode.characters = String(value);
        textSet++;
      } catch(e) {
        textFailed++;
        console.error(`[text] set failed for ${nodeId}:`, e);
      }
    }
    figma.ui.postMessage({
      type: "slide-progress", jobId, slideType,
      step: "text", detail: `${textSet} нодов заполнено, ${textFailed} пропущено`
    });

    // Step 4: replace photo
    if (photoBytes && photoBytes.length) {
      figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "photo" });
      await replaceMainPhoto(workFrame, photoBytes);
    } else {
      // Mark photo as missing with visible red tint
      markPhotoMissing(workFrame);
      figma.ui.postMessage({
        type: "slide-progress", jobId, slideType,
        step: "photo", detail: "⚠ фото не загружено — красная заливка"
      });
    }

    // Step 5: export
    figma.ui.postMessage({ type: "slide-progress", jobId, slideType, step: "export" });
    try {
      const heavySlide = slideType === "upholstery_material" || slideType === "legs_material";
      let bytes = await exportWithTimeout(workFrame, heavySlide ? 0.9 : 1, 120000);
      if (!bytes || bytes.length === 0) {
        bytes = await exportWithTimeout(workFrame, 0.75, 120000);
      }
      figma.ui.postMessage({ type: "slide-done", jobId, slideType,
        bytes: Array.from(bytes) });
    } catch(e) {
      figma.ui.postMessage({ type: "slide-error", jobId, slideType, error: String(e) });
    }
  }

  if (msg.type === "cleanup") {
    const page = figma.root.children.find(p => p.name === "🤖 Pipeline Results");
    if (page) { page.children.forEach(n => n.remove()); }
    figma.ui.postMessage({ type: "cleanup-done" });
  }

  if (msg.type === "close") figma.closePlugin();
};
