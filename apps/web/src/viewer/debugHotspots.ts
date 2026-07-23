// Hotspot debug overlay, mounted only behind the ?debug=hotspots URL flag
// (permanent QA tool, Kari 2026-07-24). Renders a small magenta sphere IN the
// 3D scene at every hotspot anchor so anchor placement can be verified against
// the splat while orbiting — the checklist step for every new splat/pin drop:
//
//   spheres glued to their splat features while orbiting  -> anchors correct
//   spheres + DOM pins move together but sit off features -> anchor DATA wrong
//     (pins must be FOCUS-relative viewer coords, see content/concepts/README.md)
//   DOM pins detach from their spheres                    -> projection bug
//
// Spheres deliberately ignore splat occlusion (splats don't write depth), so
// an anchor buried under terrain shows through — that's a placement signal,
// not a rendering bug. Flat-color ShaderMaterial keeps this chunk tiny and
// adds nothing to the shared shader chunks (StandardMaterial would drag the
// default shader library into every hero load). GLSL-only, like the viewer's
// WebGL2 default engine.
import type { Scene } from "@babylonjs/core/scene";
import { CreateSphere } from "@babylonjs/core/Meshes/Builders/sphereBuilder";
import { ShaderMaterial } from "@babylonjs/core/Materials/shaderMaterial";
import { ShaderStore } from "@babylonjs/core/Engines/shaderStore";
import type { Hotspot } from "../catalogue/concept";

ShaderStore.ShadersStore["debugHotspotVertexShader"] = `
  precision highp float;
  attribute vec3 position;
  uniform mat4 worldViewProjection;
  void main(void) { gl_Position = worldViewProjection * vec4(position, 1.0); }
`;
ShaderStore.ShadersStore["debugHotspotFragmentShader"] = `
  precision highp float;
  void main(void) { gl_FragColor = vec4(1.0, 0.0, 1.0, 1.0); }
`;

export function mountHotspotDebug(scene: Scene, hotspots: Hotspot[], viewDistance: number): void {
  const mat = new ShaderMaterial("debug-hotspot-mat", scene, "debugHotspot", {
    attributes: ["position"],
    uniforms: ["worldViewProjection"],
  });
  mat.backFaceCulling = true;
  // fixed WORLD size scaled to the scene (~1.2% of the start orbit radius —
  // ~15 screen px at the opening framing): anchoring checks need the sphere
  // to stay locked to terrain scale, never to the screen
  const radius = Math.max(0.02, viewDistance * 0.012);
  for (const [i, h] of hotspots.entries()) {
    const sphere = CreateSphere(`debug-hotspot-${i}`, { diameter: radius * 2, segments: 8 }, scene);
    sphere.position.set(h.position_m[0], h.position_m[1], h.position_m[2]);
    sphere.material = mat;
    sphere.isPickable = false;
    // the splat is a full-screen alpha-blended pass drawn after opaques and
    // would paint straight over the spheres — a later rendering group keeps
    // the overlay on top (which is also what makes buried anchors visible)
    sphere.renderingGroupId = 1;
  }
  console.info(`[debug=hotspots] ${hotspots.length} anchor sphere(s), radius ${radius.toFixed(2)} m`);
}
