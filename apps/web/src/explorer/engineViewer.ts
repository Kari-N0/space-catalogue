// Engine viewer for Concept 002 (the engine-explorer page). THE LAZY BOUNDARY
// of that page: explorer/page.ts reaches this module ONLY via dynamic import()
// (CLAUDE.md viewer lazy boundary — no @babylonjs/* in a page entry).
//
// Loads one engine (GLB + JSON manifest exported from Blender) and handles the
// four view modes, hover and selection, and camera framing. No DOM work
// happens here: the page talks to it through the callbacks passed to the
// constructor (onHover, onSelect, onStatus).
//
// Ported 1:1 from the approved standalone demo (js/viewer.js). Rendering setup
// is deliberately its own — a plain WebGL2 Engine on the page canvas with the
// demo's tone mapping, exposure and light — and does NOT go through
// src/viewer/engine.ts: that bootstrap is tuned for the splat pages (hidden
// working canvas, engine views, DPR cap) and would change how this page looks.

import { Engine } from "@babylonjs/core/Engines/engine";
import { Constants } from "@babylonjs/core/Engines/constants";
import { ShaderStore } from "@babylonjs/core/Engines/shaderStore";
import { Scene } from "@babylonjs/core/scene";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { Color3, Color4 } from "@babylonjs/core/Maths/math.color";
import { Plane } from "@babylonjs/core/Maths/math.plane";
import { Space } from "@babylonjs/core/Maths/math.axis";
import { DirectionalLight } from "@babylonjs/core/Lights/directionalLight";
import { CubeTexture } from "@babylonjs/core/Materials/Textures/cubeTexture";
import { ImageProcessingConfiguration } from "@babylonjs/core/Materials/imageProcessingConfiguration";
import { Material } from "@babylonjs/core/Materials/material";
import { ShaderMaterial } from "@babylonjs/core/Materials/shaderMaterial";
import { TransformNode } from "@babylonjs/core/Meshes/transformNode";
import type { AbstractMesh } from "@babylonjs/core/Meshes/abstractMesh";
import { ImportMeshAsync, type ISceneLoaderAsyncResult } from "@babylonjs/core/Loading/sceneLoader";
import { PointerEventTypes, type PointerInfo } from "@babylonjs/core/Events/pointerEvents";
import type { IMouseEvent } from "@babylonjs/core/Events/deviceInputEvents";
import type { Nullable } from "@babylonjs/core/types";
// side-effect imports — each one installs something the tree-shaken build
// would otherwise lack (the demo's UMD bundle registered all of them):
// .glb loading needs BOTH in Babylon 9: the file-loader plugin registration
// (without it: "Unable to find a plugin to load .glb files") and the 2.0
// loader + its extensions. glTF 1.0 is deliberately left out.
import "@babylonjs/loaders/glTF/glTFFileLoader";
import "@babylonjs/loaders/glTF/2.0";
import "@babylonjs/core/Materials/Textures/Loaders/envTextureLoader"; // .env IBL
import "@babylonjs/core/Culling/ray"; // scene.pick / scene.multiPick
import "@babylonjs/core/Rendering/outlineRenderer"; // mesh.renderOutline
import type { EngineManifest, ManifestFlow, ManifestPart, ViewerCallbacks, ViewMode } from "./types";

const STAGGER = 0.35; // how much later the last part starts moving than the first
const smooth = (t: number): number => t * t * (3 - 2 * t);
const clamp01 = (t: number): number => Math.min(1, Math.max(0, t));

// The engine lies on its side: tanks on the left, exhaust to the right.
export const VIEWS: Record<ViewMode, { alpha: number; beta: number }> = {
  explore: { alpha: -Math.PI / 2 - 0.55, beta: 1.32 },
  explode: { alpha: -Math.PI / 2 - 0.38, beta: 1.26 },
  cutaway: { alpha: -Math.PI / 2, beta: Math.PI / 2 - 0.03 },
  flow: { alpha: -Math.PI / 2 - 0.3, beta: 1.36 },
};

// Streamline shader. The flow meshes are thin tubes whose UVs carry the flow state (written by the
// Blender export):
//   uv.x  = travel time along the line in seconds, so a streak moves at the local flow speed
//   uv.y  = 1 - fade            (line ends fade out)
//   uv2.x = display speed / 3   (not used by the shader yet)
//   uv2.y = 1 - temperature     (0 = cold, 1 = hot; the glTF export flips V, hence "1 -")
ShaderStore.ShadersStore.c002FlowVertexShader = `
precision highp float;
attribute vec3 position;
attribute vec2 uv;
attribute vec2 uv2;
uniform mat4 worldViewProjection;
varying vec2 vUV;
varying vec2 vState;
void main() {
  vUV = uv;
  vState = uv2;
  gl_Position = worldViewProjection * vec4(position, 1.0);
}`;
ShaderStore.ShadersStore.c002FlowFragmentShader = `
precision highp float;
varying vec2 vUV;
varying vec2 vState;
uniform float time;
uniform float period;
uniform vec3 cold;
uniform vec3 hot;
void main() {
  float fade = clamp(1.0 - vUV.y, 0.0, 1.0);
  float temp = clamp(1.0 - vState.y, 0.0, 1.0);
  float ph = fract((vUV.x - time) / period);      // 0 at the tail of a streak, 1 at its head
  float streak = pow(ph, 5.0);
  vec3 col = mix(cold, hot, temp);
  float a = (0.13 + 0.87 * streak) * fade;        // the faint part is the streamline itself
  gl_FragColor = vec4(col * (0.55 + 1.1 * streak), a);
}`;

/** One inspectable part of the loaded engine. */
export interface EnginePart {
  id: string;
  def: ManifestPart;
  node: TransformNode;
  meshes: AbstractMesh[];
  rest: Vector3;
  /** explode offset in glTF axes (local) … */
  off: Vector3;
  /** … and in world space (set once the model is ready) */
  woff: Vector3;
  /** explode order, 0..1 */
  k: number;
  context: boolean;
  onAxis: boolean;
  cut: boolean;
  spin?: { axis: Vector3; rate: number };
  bmin: Vector3;
  bmax: Vector3;
  /** sits between the camera and the cut face */
  inFront: boolean;
}

interface CameraGoal {
  alpha: number;
  beta: number;
  radius: number;
  target: Vector3;
}

/** WebGL availability check (same test the demo ran before creating the viewer). */
export function isSupported(): boolean {
  return Engine.isSupported();
}

export class EngineViewer {
  readonly canvas: HTMLCanvasElement;
  readonly cb: ViewerCallbacks;
  mode: ViewMode = "explore";
  explodeAmount = 1;
  explodeCur = 0;
  explodeTarget = 0;
  parts: EnginePart[] = [];
  readonly byId = new Map<string, EnginePart>();
  manifest: EngineManifest | null = null;
  hoverId: string | null = null;
  selectedId: string | null = null;
  flowVariant: string | null = null;
  flowTime = 0;
  /** bounding-box diagonal of the loaded engine (m); 0 until a model is ready */
  diag = 0;

  readonly engine: Engine;
  readonly scene: Scene;
  readonly camera: ArcRotateCamera;
  readonly pivot: TransformNode;

  private readonly meshPart = new Map<number, EnginePart>();
  /** the material each part mesh loaded with (the look code swaps in cut/ghost copies) */
  private readonly matBase = new Map<number, Nullable<Material>>();
  private flows: { def: ManifestFlow; meshes: AbstractMesh[] }[] = [];
  private readonly flowMats = new Map<string, { mat: ShaderMaterial }>();
  private readonly cutMats = new Map<Material, Material>();
  private readonly ghostMats = new Map<Material, Material>();
  private assets: ISceneLoaderAsyncResult | null = null;
  private camGoal: CameraGoal | null = null;
  /** true once the loaded model's part bounds are known (framing needs them) */
  private framed = false;
  private readonly ro: ResizeObserver;
  private last: number;

  constructor(canvas: HTMLCanvasElement, cb: ViewerCallbacks) {
    this.canvas = canvas;
    this.cb = cb;

    this.engine = new Engine(canvas, true, { stencil: true, antialias: true }, true);
    const scene = (this.scene = new Scene(this.engine));
    scene.clearColor = new Color4(0.047, 0.047, 0.055, 1);

    const cam = (this.camera = new ArcRotateCamera("cam", VIEWS.explore.alpha, VIEWS.explore.beta, 6, Vector3.Zero(), scene));
    cam.fov = 0.5;
    cam.minZ = 0.02;
    cam.maxZ = 200;
    cam.lowerRadiusLimit = 0.25;
    cam.upperRadiusLimit = 40;
    cam.wheelDeltaPercentage = 0.012;
    cam.panningSensibility = 900;
    cam.useNaturalPinchZoom = true;
    // Second argument false: the camera consumes the events it uses, so wheel-zoom does not also scroll the page.
    cam.attachControl(canvas, false);
    canvas.addEventListener("wheel", (e) => e.preventDefault(), { passive: false });

    scene.environmentTexture = CubeTexture.CreateFromPrefilteredData(cb.envUrl, scene);
    scene.environmentIntensity = 1.0;
    const ip = scene.imageProcessingConfiguration;
    ip.toneMappingEnabled = true;
    ip.toneMappingType = ImageProcessingConfiguration.TONEMAPPING_ACES;
    ip.exposure = 1.25;
    ip.contrast = 1.15;
    const key = new DirectionalLight("key", new Vector3(0.5, -1, 0.8), scene);
    key.intensity = 2.2;

    this.pivot = new TransformNode("pivot", scene);
    this.pivot.rotation.z = Math.PI / 2;

    scene.onPointerObservable.add((pi) => this.pointer(pi));
    canvas.addEventListener("pointerleave", () => this.setHover(null, null));
    this.ro = new ResizeObserver(() => this.engine.resize());
    this.ro.observe(canvas.parentElement ?? canvas);
    this.last = performance.now();
    this.engine.runRenderLoop(() => {
      this.tick();
      scene.render();
    });
  }

  // ------------------------------------------------------------------ loading
  async load(def: { model: string; manifest: string }): Promise<EngineManifest> {
    this.unload();
    this.cb.onStatus?.("Loading model…");
    const man = (this.manifest = (await (await fetch(def.manifest)).json()) as EngineManifest);
    const res = await ImportMeshAsync(def.model, this.scene);
    this.assets = res;
    const root = res.meshes[0];
    root.parent = this.pivot;
    const find = (name: string): TransformNode | undefined =>
      res.transformNodes.find((n) => n.name === name) || res.meshes.find((n) => n.name === name);
    const meshesOf = (node: TransformNode): AbstractMesh[] => {
      const list = node.getChildMeshes(false);
      if ("getTotalVertices" in node && (node as AbstractMesh).getTotalVertices() > 0) list.push(node as AbstractMesh);
      return list;
    };

    const maxOrder = Math.max(1, ...man.parts.map((p) => p.explode_order || 0));
    const outline = Color3.FromHexString(this.cb.highlight || "#60a5fa");
    for (const d of man.parts) {
      const node = find(d.node);
      if (!node) continue;
      const o = d.explode_offset || [0, 0, 0];
      const rest = node.position.clone();
      const onAxis = Math.abs(rest.x) < 0.02 && Math.abs(rest.z) < 0.02;
      const part: EnginePart = {
        id: d.node,
        def: d,
        node,
        meshes: meshesOf(node),
        rest,
        off: new Vector3(o[0], o[2], -o[1]), // Blender (x, y, z) -> glTF (x, z, -y)
        woff: Vector3.Zero(),
        k: (d.explode_order || 0) / maxOrder,
        context: d.role === "context",
        onAxis,
        // Parts on the thrust axis are sectioned in Cutaway. The manifest can override this per part.
        cut: d.cut !== undefined ? !!d.cut : onAxis,
        bmin: Vector3.Zero(),
        bmax: Vector3.Zero(),
        inFront: false,
      };
      if (d.spin) {
        const a = d.spin.axis || [0, 0, 1];
        part.spin = { axis: new Vector3(a[0], a[2], -a[1]).normalize(), rate: (d.spin.rev_per_s || 1) * 2 * Math.PI };
      }
      for (const m of part.meshes) {
        this.meshPart.set(m.uniqueId, part);
        m.isPickable = true;
        m.outlineColor = outline;
        m.outlineWidth = 0.004;
        if (m.material) {
          m.material.backFaceCulling = false;
          if ("twoSidedLighting" in m.material) (m.material as Material & { twoSidedLighting: boolean }).twoSidedLighting = true;
        }
        this.matBase.set(m.uniqueId, m.material);
      }
      this.parts.push(part);
      this.byId.set(part.id, part);
    }

    for (const f of man.flows || []) {
      const node = find(f.node);
      if (!node) continue;
      const meshes = meshesOf(node);
      const mat = this.flowMat(f.medium, f);
      for (const m of meshes) {
        m.material = mat;
        m.isPickable = false;
        m.alphaIndex = 10;
        m.setEnabled(false);
      }
      this.flows.push({ def: f, meshes });
    }

    await this.scene.whenReadyAsync();
    this.scene.render();
    for (const part of this.parts) {
      let mn = new Vector3(Infinity, Infinity, Infinity);
      let mx = new Vector3(-Infinity, -Infinity, -Infinity);
      for (const m of part.meshes) {
        m.computeWorldMatrix(true);
        const bb = m.getBoundingInfo().boundingBox;
        mn = Vector3.Minimize(mn, bb.minimumWorld);
        mx = Vector3.Maximize(mx, bb.maximumWorld);
      }
      part.bmin = mn;
      part.bmax = mx;
      const parent = part.node.parent;
      if (parent) part.woff = Vector3.TransformNormal(part.off, parent.getWorldMatrix());
      part.inFront = !part.cut && (mn.z + mx.z) / 2 < -0.1; // sits between the camera and the cut face
    }
    this.framed = true;
    // Engines range from 0.5 m to 4 m, so outline width and camera limits follow the engine's size.
    const all = this.boundsAt(0);
    this.diag = all.max.subtract(all.min).length();
    for (const p of this.parts) {
      p.inFront = !p.cut && (p.bmin.z + p.bmax.z) / 2 < -0.03 * this.diag;
      for (const m of p.meshes) m.outlineWidth = this.diag * 0.0012;
    }
    this.camera.lowerRadiusLimit = this.diag * 0.06;
    this.camera.minZ = Math.max(0.002, this.diag * 0.004);
    this.explodeCur = 0;
    this.setMode(this.mode, { instant: true });
    this.cb.onStatus?.("");
    return man;
  }

  private unload(): void {
    if (this.assets) this.assets.meshes[0].dispose(false, true);
    for (const m of [...this.cutMats.values(), ...this.ghostMats.values()]) m.dispose();
    this.cutMats.clear();
    this.ghostMats.clear();
    this.assets = null;
    this.framed = false;
    this.parts = [];
    this.byId.clear();
    this.meshPart.clear();
    this.matBase.clear();
    this.flows = [];
    this.hoverId = this.selectedId = null;
  }

  // ------------------------------------------------------------------ modes
  setMode(mode: ViewMode, { instant = false, frame = true }: { instant?: boolean; frame?: boolean } = {}): void {
    this.mode = mode;
    this.explodeTarget = mode === "explode" ? this.explodeAmount : 0;
    this.applyFlowVisibility();
    this.applyLook();
    if (frame) this.resetView(instant);
  }

  // Some engines have more than one operating mode. A stream tagged with a variant shows only in that mode.
  setFlowVariant(id: string | null): void {
    this.flowVariant = id || null;
    this.applyFlowVisibility();
  }

  private applyFlowVisibility(): void {
    for (const f of this.flows) {
      const on = this.mode === "flow" && (!f.def.variant || !this.flowVariant || f.def.variant === this.flowVariant);
      for (const m of f.meshes) m.setEnabled(on);
    }
  }

  setExplode(amount: number): void {
    this.explodeAmount = clamp01(amount);
    if (this.mode === "explode") this.explodeTarget = this.explodeAmount;
  }

  private cutMat(mat: Material): Material {
    let c = this.cutMats.get(mat);
    if (!c) {
      c = mat.clone(mat.name + "_cut") as Material;
      c.clipPlane = new Plane(0, 0, -1, 0); // removes the half facing the default camera
      this.cutMats.set(mat, c);
    }
    return c;
  }

  // glTF materials load as opaque, so a faded part needs a blended copy for mesh.visibility to show.
  private ghostMat(mat: Material): Material {
    let c = this.ghostMats.get(mat);
    if (!c) {
      c = mat.clone(mat.name + "_ghost") as Material;
      c.transparencyMode = Material.MATERIAL_ALPHABLEND;
      if (mat.clipPlane) c.clipPlane = mat.clipPlane;
      this.ghostMats.set(mat, c);
    }
    return c;
  }

  private flowMat(medium: string, def: ManifestFlow): ShaderMaterial {
    const have = this.flowMats.get(medium);
    if (have) {
      have.mat.setFloat("period", def.period_s || 0.9);
      return have.mat;
    }
    const [cold, hot] = ((this.cb.flowColors || {})[medium] || ["#ffffff", "#ffffff"]).map((h) => Color3.FromHexString(h));
    const mat = new ShaderMaterial(
      "flow_" + medium,
      this.scene,
      { vertex: "c002Flow", fragment: "c002Flow" },
      { attributes: ["position", "uv", "uv2"], uniforms: ["worldViewProjection", "time", "period", "cold", "hot"], needAlphaBlending: true },
    );
    mat.setFloat("time", 0);
    mat.setFloat("period", def.period_s || 0.9);
    mat.setColor3("cold", cold);
    mat.setColor3("hot", hot);
    mat.backFaceCulling = false;
    mat.alphaMode = Constants.ALPHA_ADD; // additive, so crossing streaks glow
    mat.disableDepthWrite = true;
    this.flowMats.set(medium, { mat });
    return mat;
  }

  // ------------------------------------------------------------------ hover, selection
  hover(id: string | null): void {
    this.setHover(id && this.byId.has(id) ? id : null, null);
  }

  select(id: string | null, focus = true): void {
    this.selectedId = id && this.byId.has(id) ? id : null;
    this.applyLook();
    const part = this.selectedId ? this.byId.get(this.selectedId) : undefined;
    if (part && focus && this.framed) {
      const b = this.boundsAt(this.explodeTarget, part);
      const size = b.max.subtract(b.min).length();
      this.goto({ alpha: this.camera.alpha, beta: this.camera.beta, radius: Math.max((this.diag || 4) * 0.28, size * 3.1), target: b.min.add(b.max).scale(0.5) });
    }
    this.cb.onSelect?.(this.selectedId);
  }

  step(dir: number): void {
    if (!this.parts.length) return;
    const i = this.parts.findIndex((p) => p.id === this.selectedId);
    const n = this.parts.length;
    this.select(this.parts[i < 0 ? (dir > 0 ? 0 : n - 1) : (i + dir + n) % n].id);
  }

  private setHover(id: string | null, ev: IMouseEvent | null): void {
    const pos = ev ? { x: ev.offsetX, y: ev.offsetY } : null;
    if (id !== this.hoverId) {
      this.hoverId = id;
      this.applyLook();
    }
    this.cb.onHover?.(id, pos);
  }

  private applyLook(): void {
    const ghost = this.mode === "flow";
    for (const p of this.parts) {
      const sel = this.selectedId === p.id;
      const hov = this.hoverId === p.id;
      let v = 1;
      if (ghost) v = sel || hov ? 0.5 : 0.07;
      else if (this.selectedId && !sel) v = hov ? 0.6 : 0.16;
      else if (this.mode === "cutaway" && p.inFront && !sel) v = hov ? 0.5 : 0.08;
      const cut = this.mode === "cutaway" && p.cut;
      for (const m of p.meshes) {
        let mat = this.matBase.get(m.uniqueId) ?? null;
        if (mat && cut) mat = this.cutMat(mat);
        if (mat && v < 1) mat = this.ghostMat(mat);
        m.material = mat;
        m.visibility = v;
        m.renderOutline = hov || sel;
      }
    }
  }

  private pick(): EnginePart | null {
    const s = this.scene;
    const pred = (m: AbstractMesh): boolean => this.meshPart.has(m.uniqueId) && m.isEnabled();
    if (this.mode !== "cutaway") {
      const r = s.pick(s.pointerX, s.pointerY, pred);
      return (r && r.hit && r.pickedMesh ? this.meshPart.get(r.pickedMesh.uniqueId) : null) ?? null;
    }
    // In the cutaway the removed half is invisible but still pickable, so skip hits on it.
    const hits = s.multiPick(s.pointerX, s.pointerY, pred) || [];
    hits.sort((a, b) => a.distance - b.distance);
    for (const h of hits) {
      const p = h.pickedMesh ? this.meshPart.get(h.pickedMesh.uniqueId) : undefined;
      if (!p) continue;
      if (p.cut && h.pickedPoint && h.pickedPoint.z < 0) continue;
      return p;
    }
    return null;
  }

  private pointer(pi: PointerInfo): void {
    const T = PointerEventTypes;
    if (pi.type === T.POINTERDOWN || pi.type === T.POINTERWHEEL) this.camGoal = null;
    if (pi.type === T.POINTERMOVE) {
      if (pi.event.buttons) return;
      const p = this.pick();
      this.setHover(p ? p.id : null, pi.event);
    } else if (pi.type === T.POINTERTAP) {
      if (pi.event.button !== 0) return;
      const p = this.pick();
      this.select(p ? p.id : null);
    } else if (pi.type === T.POINTERDOUBLETAP) {
      this.select(null);
      this.resetView();
    }
  }

  // ------------------------------------------------------------------ explode + camera
  private stag(part: EnginePart, a: number): number {
    return smooth(clamp01(a * (1 + STAGGER) - STAGGER * part.k));
  }

  private applyExplode(a: number): void {
    for (const p of this.parts) {
      const t = this.stag(p, a);
      p.node.position.copyFrom(p.rest).addInPlace(p.off.scale(t));
    }
  }

  private boundsAt(a: number, only?: EnginePart): { min: Vector3; max: Vector3 } {
    let mn = new Vector3(Infinity, Infinity, Infinity);
    let mx = new Vector3(-Infinity, -Infinity, -Infinity);
    for (const p of only ? [only] : this.parts) {
      const d = p.woff.scale(this.stag(p, a));
      mn = Vector3.Minimize(mn, p.bmin.add(d));
      mx = Vector3.Maximize(mx, p.bmax.add(d));
    }
    return { min: mn, max: mx };
  }

  resetView(instant = false): void {
    // (framed: a mode change while a model is still loading has no bounds to frame yet — load() frames at its end)
    if (!this.parts.length || !this.framed) return;
    const view = VIEWS[this.mode] || VIEWS.explore;
    const b = this.boundsAt(this.explodeTarget);
    const c = b.min.add(b.max).scale(0.5);
    const s = b.max.subtract(b.min);
    const th = view.alpha + Math.PI / 2;
    const w = Math.abs(s.x * Math.cos(th)) + Math.abs(s.z * Math.sin(th));
    const depth = Math.abs(s.x * Math.sin(th)) + Math.abs(s.z * Math.cos(th));
    const h = s.y * Math.abs(Math.sin(view.beta)) + depth * Math.abs(Math.cos(view.beta));
    const aspect = this.engine.getRenderWidth() / Math.max(1, this.engine.getRenderHeight());
    const tf = Math.tan(this.camera.fov / 2);
    const radius = 1.1 * Math.max(h / 2 / tf, w / 2 / (tf * aspect)) + depth * 0.15;
    this.goto({ alpha: view.alpha, beta: view.beta, radius, target: c }, instant);
  }

  private goto(g: CameraGoal, instant = false): void {
    const c = this.camera;
    g.alpha += 2 * Math.PI * Math.round((c.alpha - g.alpha) / (2 * Math.PI));
    if (instant) {
      c.alpha = g.alpha;
      c.beta = g.beta;
      c.radius = g.radius;
      c.target.copyFrom(g.target);
      this.camGoal = null;
    } else {
      this.camGoal = g;
    }
  }

  setCamera(alpha: number, beta: number, radius: number): void {
    this.camGoal = null;
    this.camera.alpha = alpha;
    this.camera.beta = beta;
    this.camera.radius = radius;
  }

  getCamera(): number[] {
    return [this.camera.alpha, this.camera.beta, this.camera.radius].map((v) => Number(v.toFixed(3)));
  }

  private tick(): void {
    const now = performance.now();
    const dt = Math.min(0.05, (now - this.last) / 1000);
    this.last = now;
    const k = 1 - Math.exp(-dt * 6);

    const de = this.explodeTarget - this.explodeCur;
    if (de !== 0) {
      this.explodeCur = Math.abs(de) < 1e-4 ? this.explodeTarget : this.explodeCur + de * k;
      this.applyExplode(this.explodeCur);
    }

    const g = this.camGoal;
    if (g) {
      const c = this.camera;
      c.alpha += (g.alpha - c.alpha) * k;
      c.beta += (g.beta - c.beta) * k;
      c.radius += (g.radius - c.radius) * k;
      c.target.addInPlace(g.target.subtract(c.target).scale(k));
      if (Math.abs(g.radius - c.radius) < 1e-3 && Math.abs(g.alpha - c.alpha) < 1e-3 && Math.abs(g.beta - c.beta) < 1e-3) this.camGoal = null;
    }

    if (this.mode === "flow") {
      this.flowTime += dt;
      for (const f of this.flowMats.values()) f.mat.setFloat("time", this.flowTime);
      for (const p of this.parts) if (p.spin) p.node.rotate(p.spin.axis, p.spin.rate * dt, Space.LOCAL);
    }
  }

  dispose(): void {
    this.ro.disconnect();
    this.engine.stopRenderLoop();
    this.scene.dispose();
    this.engine.dispose();
  }
}
