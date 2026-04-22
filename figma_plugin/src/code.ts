// PM-RU Content Agent — Figma Render Plugin
// Polls the backend for pending fill jobs, updates Figma layers, exports PNG.
/// <reference types="@figma/plugin-typings" />

const POLL_INTERVAL_MS = 3000;
const PLUGIN_INSTANCE_ID = `plugin-${Date.now()}`;

// Backend base URL — set via plugin UI or bake in for the office machine
let BACKEND_URL = "http://localhost:8000/api/v1";


// ── Types (mirror backend schema) ────────────────────────────────────────────

interface FillJob {
  id: string;
  file_key: string;
  frame_id: string;
  slide_type: string;
  slide_index: number;
  text_fills: Record<string, string>;   // node_id → text value
  image_fills: Record<string, string>;  // node_id → image URL (future)
}


// ── Main plugin entry ─────────────────────────────────────────────────────────

figma.showUI(__html__, { width: 320, height: 240, title: "PM-RU Render" });

figma.ui.onmessage = (msg: { type: string; backendUrl?: string }) => {
  if (msg.type === "set-backend-url" && msg.backendUrl) {
    BACKEND_URL = msg.backendUrl.replace(/\/$/, "");
    figma.ui.postMessage({ type: "status", text: `Backend: ${BACKEND_URL}` });
  }
  if (msg.type === "start") {
    figma.ui.postMessage({ type: "status", text: "Polling for jobs…" });
    pollLoop();
  }
};


// ── Poll loop ─────────────────────────────────────────────────────────────────

async function pollLoop(): Promise<void> {
  while (true) {
    try {
      await processNextJob();
    } catch (err) {
      figma.ui.postMessage({ type: "error", text: String(err) });
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

async function processNextJob(): Promise<void> {
  const job = await claimJob();
  if (!job) return;

  figma.ui.postMessage({ type: "status", text: `Processing job ${job.id} (${job.slide_type})` });

  try {
    const pngBytes = await renderJob(job);
    await submitResult(job.id, pngBytes);
    figma.ui.postMessage({ type: "done", text: `✓ Job ${job.id} exported` });
  } catch (err) {
    const message = String(err);
    await reportError(job.id, message);
    figma.ui.postMessage({ type: "error", text: `✗ Job ${job.id}: ${message}` });
  }
}


// ── Figma rendering ───────────────────────────────────────────────────────────

async function renderJob(job: FillJob): Promise<Uint8Array> {
  // Locate the template frame by node id
  const templateNode = figma.getNodeById(job.frame_id);
  if (!templateNode || templateNode.type !== "FRAME") {
    throw new Error(`Frame ${job.frame_id} not found or not a FRAME`);
  }

  // Clone the frame so we never dirty the template
  const workFrame = templateNode.clone() as FrameNode;
  workFrame.name = `__render_${job.id}`;

  try {
    // Apply text fills
    await applyTextFills(workFrame, templateNode as FrameNode, job.text_fills);

    // Apply image fills (future: download image_url, create ImageHash, set as fill)
    // await applyImageFills(workFrame, templateNode as FrameNode, job.image_fills);

    // Export as PNG @2x
    const exportSettings: ExportSettingsImage = {
      format: "PNG",
      constraint: { type: "SCALE", value: 2 },
    };
    const pngBytes = await workFrame.exportAsync(exportSettings);
    return pngBytes;
  } finally {
    workFrame.remove();
  }
}

/**
 * Walk the cloned frame tree and apply text fills.
 *
 * Strategy: The clone preserves the same tree structure as the template.
 * We build an index of template node_id → position-path (array of child indices),
 * then navigate the clone using those same paths.
 */
async function applyTextFills(
  workFrame: FrameNode,
  templateFrame: FrameNode,
  textFills: Record<string, string>
): Promise<void> {
  // Build path map from template
  const pathMap: Record<string, number[]> = {};
  buildPathMap(templateFrame, [], pathMap);

  for (const [nodeId, text] of Object.entries(textFills)) {
    const path = pathMap[nodeId];
    if (!path) {
      console.warn(`[PM-RU] No path for node ${nodeId}, skipping`);
      continue;
    }

    const cloneNode = navigatePath(workFrame, path);
    if (!cloneNode || cloneNode.type !== "TEXT") {
      console.warn(`[PM-RU] Node at path for ${nodeId} is not TEXT`);
      continue;
    }

    // Load font before modifying text
    if (cloneNode.fontName !== figma.mixed) {
      await figma.loadFontAsync(cloneNode.fontName as FontName);
    } else {
      // Mixed fonts — load all unique fonts in the node
      const fonts = new Set<string>();
      for (let i = 0; i < cloneNode.characters.length; i++) {
        const fn = cloneNode.getRangeFontName(i, i + 1) as FontName;
        fonts.add(JSON.stringify(fn));
      }
      for (const f of fonts) {
        await figma.loadFontAsync(JSON.parse(f) as FontName);
      }
    }

    cloneNode.characters = text;
  }
}

function buildPathMap(
  node: SceneNode,
  currentPath: number[],
  result: Record<string, number[]>
): void {
  result[node.id] = currentPath;
  if ("children" in node) {
    node.children.forEach((child: SceneNode, index: number) => {
      buildPathMap(child, [...currentPath, index], result);
    });
  }
}

function navigatePath(root: FrameNode, path: number[]): SceneNode | null {
  let current: SceneNode = root;
  for (const index of path) {
    if (!("children" in current)) return null;
    const child: SceneNode | undefined = (current as FrameNode | GroupNode | ComponentNode).children[index];
    if (!child) return null;
    current = child;
  }
  return current;
}


// ── Backend communication ─────────────────────────────────────────────────────

async function claimJob(): Promise<FillJob | null> {
  const resp = await fetch(
    `${BACKEND_URL}/fill-jobs/pending?instance_id=${PLUGIN_INSTANCE_ID}`
  );
  if (!resp.ok) throw new Error(`Claim failed: ${resp.status}`);
  const body = await resp.json();
  return body ?? null;
}

async function submitResult(jobId: string, pngBytes: Uint8Array): Promise<void> {
  const resp = await fetch(`${BACKEND_URL}/fill-jobs/${jobId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "image/png" },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    body: pngBytes as any,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Submit failed ${resp.status}: ${text}`);
  }
}

async function reportError(jobId: string, message: string): Promise<void> {
  await fetch(`${BACKEND_URL}/fill-jobs/${jobId}/error`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}


// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
