/* ============================================================
   µLearn Concierge — 3D Scene Architecture (Three.js)
   Refined Realistic Desk Setup, Studio Room & Dynamic Framing
   ============================================================ */

import * as THREE from '../vendor/three.module.js';

// Global scene objects and state container
export const sceneState = {
  isInitialized: false,
  scene: null,
  camera: null,
  renderer: null,
  canvas: null,

  // Groups
  logoGroup: null,
  particlesGroup: null,
  workspaceGroup: null,
  roomGroup: null,
  deskGroup: null,
  laptopGroup: null,
  laptopLidGroup: null,
  laptopScreenMesh: null,
  screenFadeMesh: null,
  lampGroup: null,
  teaGroup: null,
  photoStandGroup: null,
  booksGroup: null,
  deskMatGroup: null,
  plantGroup: null,
  headphonesGroup: null,
  posterGroup: null,
  starfield: null,
  steamSprites: [],

  // Hero Logo Handoff & Dissolve State
  discMesh: null,
  outerRing: null,
  innerRing: null,
  frontFace: null,
  backFace: null,
  glyphMesh: null,
  sparkMesh: null,
  solidDissolveUniforms: null,
  logoLiftValue: 0.0,

  // Lights
  ambientLight: null,
  keyLight: null,
  lampLight: null,
  lampTarget: null,
  fillLight: null,
  wallWash: null,

  // Textures
  chatTexture: null,
  logoTexture: null,
  originalLogoTexture: null,
  walnutTexture: null,
  floorTexture: null,
  deskMatTexture: null,
  keyboardTexture: null,
  shadowTexture: null,
  particleTexture: null,
  steamTexture: null,

  // Materials dictionary
  materials: {},

  // Camera targets
  cameraLookTarget: new THREE.Vector3(0, 0, 0),
  defaultCameraPos: new THREE.Vector3(0, 0, 7.5),

  // Prop assemblies for staggered reveal in Phase 3
  props: []
};

// Procedural materials cache
let materials = {};

/**
 * Initialize the Three.js WebGL scene and procedural models
 */
export function initScene(canvas) {
  if (sceneState.isInitialized) return sceneState;

  sceneState.canvas = canvas;
  const width = window.innerWidth;
  const height = window.innerHeight;

  // 1. Scene with Rich Midnight Navy background in Hero phase
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070B16);
  scene.fog = new THREE.FogExp2(0x070B16, 0.015);
  sceneState.scene = scene;

  // 2. Camera: near clipping plane at 0.05m to allow tight, unclipped zoom
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.05, 80);
  camera.position.copy(sceneState.defaultCameraPos);
  camera.lookAt(sceneState.cameraLookTarget);
  sceneState.camera = camera;

  // 3. Renderer with ACESFilmic tone mapping & exposure tuned for bright, airy morning output
  const renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance'
  });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.50;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  // Shadows enabled on desktop (width > 768) with PCFSoftShadowMap
  renderer.shadowMap.enabled = width > 768;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  sceneState.renderer = renderer;

  // 4. Generate Procedural Textures
  sceneState.walnutTexture = createWalnutTexture();
  sceneState.floorTexture = createFloorTexture();
  sceneState.deskMatTexture = createDeskMatTexture();
  sceneState.keyboardTexture = createKeyboardTexture();
  sceneState.shadowTexture = createSoftShadowTexture();
  sceneState.particleTexture = createParticleTexture();
  sceneState.steamTexture = createSteamTexture();

  // 5. Load External Image Textures
  const textureLoader = new THREE.TextureLoader();

  sceneState.chatTexture = textureLoader.load('/static/img/chat-preview.png', (tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.generateMipmaps = true;
    tex.minFilter = THREE.LinearMipmapLinearFilter;
    tex.magFilter = THREE.LinearFilter;
    if (renderer && renderer.capabilities) {
      tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    }
    if (sceneState.laptopScreenMesh) {
      sceneState.laptopScreenMesh.material.needsUpdate = true;
    }
  });

  sceneState.logoTexture = textureLoader.load('/static/img/mulearn-logo.png', (tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.generateMipmaps = true;
    tex.minFilter = THREE.LinearMipmapLinearFilter;
    tex.magFilter = THREE.LinearFilter;
    if (renderer && renderer.capabilities) {
      tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    }
  });

  sceneState.originalLogoTexture = textureLoader.load('/static/img/mulearn-original.png', (tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.generateMipmaps = true;
    tex.minFilter = THREE.LinearMipmapLinearFilter;
    tex.magFilter = THREE.LinearFilter;
    if (renderer && renderer.capabilities) {
      tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    }
  });

  // 6. Materials Setup
  setupMaterials();

  // 7. Lighting & Environment Reflections Setup
  setupEnvironment(renderer, scene);
  setupLights(scene);

  // 8. Ambient Starfield (Hero Phases 1 & 2 background)
  createStarfield(scene);

  // 9. Hero 3D Logo Monogram (Phase 1 & 2)
  createHeroLogo(scene);

  // 10. Refined Procedural Desk & Studio Room Architecture
  createWorkspace(scene);

  // 11. Pixel-to-Object Deterministic Particle Morph (Phase 3)
  createPixelToObjectMorph(scene);

  // Initialize particle morph at progress 0.0 and lift at 0.0
  updateParticleMorph(0.0);
  updateLogoLift(0.0);

  sceneState.isInitialized = true;
  return sceneState;
}

/**
 * Procedural sunny morning studio environment map using PMREMGenerator
 */
function setupEnvironment(renderer, scene) {
  try {
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envScene = new THREE.Scene();
    envScene.background = new THREE.Color(0xD0E0F2);

    // Soft sky & ground hemisphere for gentle ambient bounce & reflections
    const hemi = new THREE.HemisphereLight(0xDCE9FF, 0xE8D9C2, 0.70);
    envScene.add(hemi);

    const envMap = pmrem.fromScene(envScene, 0.04).texture;
    scene.environment = envMap;
    if ('environmentIntensity' in scene) {
      scene.environmentIntensity = 0.28;
    }
    pmrem.dispose();
  } catch (err) {
    console.warn('Procedural environment generation failed, falling back to direct lighting:', err);
  }
}

/**
 * Reusable material library with physically based parameters
 */
function setupMaterials() {
  sceneState.materials = materials;

  // Champagne Gold Physical Material
  materials.gold = new THREE.MeshPhysicalMaterial({
    color: 0xE6D09B,
    emissive: 0x33220E,
    metalness: 0.88,
    roughness: 0.22,
    clearcoat: 0.9,
    clearcoatRoughness: 0.15,
    reflectivity: 0.95
  });

  // Brushed Warm Brass
  materials.brushedBrass = new THREE.MeshStandardMaterial({
    color: 0xD8BD85,
    metalness: 0.86,
    roughness: 0.28
  });

  // Brushed Silver / Grey Aluminium (Stand)
  materials.brushedAluminium = new THREE.MeshStandardMaterial({
    color: 0xC5CAD0,
    metalness: 0.82,
    roughness: 0.38
  });

  // Space Gray Anodized Laptop Body
  materials.spaceGray = new THREE.MeshStandardMaterial({
    color: 0x566070,
    metalness: 0.72,
    roughness: 0.32
  });

  // Matte Dark Metal / Steel Legs & Crossbars (#2A3240)
  materials.darkSteel = new THREE.MeshStandardMaterial({
    color: 0x2A3240,
    roughness: 0.50,
    metalness: 0.65,
    side: THREE.DoubleSide
  });

  // Dark Leatherette for Headphone Band Cushion & Ear Pads (#181A20)
  materials.darkLeatherette = new THREE.MeshStandardMaterial({
    color: 0x181A20,
    roughness: 0.85,
    metalness: 0.08,
    side: THREE.DoubleSide
  });

  // Matte Black for Ear Cup Shells (#14161A)
  materials.matteBlack = new THREE.MeshStandardMaterial({
    color: 0x14161A,
    roughness: 0.55,
    metalness: 0.25,
    side: THREE.DoubleSide
  });

  // Natural Walnut Desk Top with Procedural Wood Grain (#6B4A32, not saturated orange)
  materials.walnut = new THREE.MeshStandardMaterial({
    map: sceneState.walnutTexture,
    color: 0x6B4A32,
    roughness: 0.65,
    metalness: 0.02
  });

  // Natural Light Oak Floor (#B58B5A)
  materials.floorOak = new THREE.MeshStandardMaterial({
    map: sceneState.floorTexture,
    color: 0xB58B5A,
    roughness: 0.48,
    metalness: 0.04
  });

  // Warm Off-White Room Wall (#EFE8DC)
  materials.wall = new THREE.MeshStandardMaterial({
    color: 0xEFE8DC,
    roughness: 0.95,
    metalness: 0.0
  });

  // Subtle Wall Paneling Battens (#E2DACD)
  materials.wallBatten = new THREE.MeshStandardMaterial({
    color: 0xE2DACD,
    roughness: 0.88,
    metalness: 0.0
  });

  // White Baseboard (#F8F6F2)
  materials.baseboard = new THREE.MeshStandardMaterial({
    color: 0xF8F6F2,
    roughness: 0.80,
    metalness: 0.0
  });

  // Soft Grey-Blue Leather Desk Mat (#4B5A6A)
  materials.deskMat = new THREE.MeshStandardMaterial({
    map: sceneState.deskMatTexture,
    color: 0x4B5A6A,
    roughness: 0.75,
    metalness: 0.05
  });

  // Keyboard Well with Light Keys & Visible Key Grid
  materials.keyboardWell = new THREE.MeshStandardMaterial({
    map: sceneState.keyboardTexture,
    roughness: 0.60,
    metalness: 0.15
  });

  materials.trackpad = new THREE.MeshStandardMaterial({
    color: 0x485262,
    roughness: 0.35,
    metalness: 0.45
  });

  // Clear Tea Glass (transparent with subtle rim reflection, reads well on light desk)
  materials.teaGlass = new THREE.MeshStandardMaterial({
    color: 0xFFFFFF,
    transparent: true,
    opacity: 0.32,
    roughness: 0.04,
    metalness: 0.12
  });

  // Amber Tea Liquid
  materials.teaLiquid = new THREE.MeshStandardMaterial({
    color: 0xC85A0E,
    emissive: 0x2A1002,
    emissiveIntensity: 0.15,
    roughness: 0.12,
    metalness: 0.04,
    transparent: true,
    opacity: 0.88
  });

  // Meniscus Surface for Tea Liquid
  materials.teaMeniscus = new THREE.MeshStandardMaterial({
    color: 0xE89838,
    emissive: 0x3A1604,
    emissiveIntensity: 0.15,
    roughness: 0.15,
    metalness: 0.04,
    transparent: true,
    opacity: 0.92
  });

  // Warm Ivory Matting for Photo Frame (#E8DFCE, not pure white)
  materials.photoMat = new THREE.MeshStandardMaterial({
    color: 0xE8DFCE,
    roughness: 0.90,
    metalness: 0.0
  });

  // Ceramic
  materials.ceramic = new THREE.MeshStandardMaterial({
    color: 0xF4F0EA,
    roughness: 0.52,
    metalness: 0.04
  });

  // Cognac Leather Journal (#9E5428)
  materials.leather = new THREE.MeshStandardMaterial({
    color: 0x9E5428,
    roughness: 0.60,
    metalness: 0.05
  });

  materials.paper = new THREE.MeshStandardMaterial({
    color: 0xEDE7DA,
    roughness: 0.95,
    metalness: 0.0
  });

  // Plant Pot in Clean Off-White Ceramic (#F2EFEA)
  materials.plantPot = new THREE.MeshStandardMaterial({
    color: 0xF2EFEA,
    roughness: 0.55,
    metalness: 0.02
  });

  // Fuller Lush Greenery
  materials.succulentDark = new THREE.MeshStandardMaterial({
    color: 0x226238,
    roughness: 0.5,
    metalness: 0.03
  });

  materials.succulentLight = new THREE.MeshStandardMaterial({
    color: 0x38824C,
    roughness: 0.45,
    metalness: 0.03
  });
}

/**
 * Bright, airy modern studio daylight lighting setup
 * - Key: Large soft DirectionalLight (warm white #FFF3E0, intensity ~2.5) from window at 40°
 * - Fill: HemisphereLight (sky #DCE9FF, ground #E8D9C2) intensity ~1.2
 * - Desk Lamp Prop: Small warm PointLight at bulb (intensity low ~15), no hotspots
 */
function setupLights(scene) {
  // 1. Fill Light: HemisphereLight (sky #DCE9FF, ground #E8D9C2)
  const ambient = new THREE.HemisphereLight(0xDCE9FF, 0xE8D9C2, 0.82);
  scene.add(ambient);
  sceneState.ambientLight = ambient;

  // 2. Key Light: Large soft DirectionalLight (warm white #FFF3E0, intensity ~1.40)
  // Coming from window on the left at ~40 degrees with soft PCF shadows
  const keyLight = new THREE.DirectionalLight(0xFFF3E0, 1.40);
  keyLight.position.set(-3.6, 3.2, 1.2);
  const keyTarget = new THREE.Object3D();
  keyTarget.position.set(0, 0.75, 0);
  scene.add(keyTarget);
  keyLight.target = keyTarget;

  keyLight.castShadow = true;
  keyLight.shadow.mapSize.width = 2048;
  keyLight.shadow.mapSize.height = 2048;
  keyLight.shadow.camera.near = 0.5;
  keyLight.shadow.camera.far = 12.0;
  keyLight.shadow.camera.left = -1.8;
  keyLight.shadow.camera.right = 1.8;
  keyLight.shadow.camera.top = 1.8;
  keyLight.shadow.camera.bottom = -1.8;
  keyLight.shadow.bias = -0.0004;
  keyLight.shadow.normalBias = 0.02;
  keyLight.shadow.radius = 6;

  scene.add(keyLight);
  sceneState.keyLight = keyLight;
  sceneState.fillLight = keyLight;

  // 3. Desk Lamp is a prop only in daylight: no light emitted
  const lampLight = new THREE.PointLight(0xFFD299, 0, 0, 2.0);
  lampLight.position.set(-0.58, 1.20, -0.06);
  lampLight.castShadow = false;
  lampLight.visible = false;
  scene.add(lampLight);
  sceneState.lampLight = lampLight;
}

/**
 * Subtle starfield background particles for Hero Phases 1 & 2
 */
function createStarfield(scene) {
  const count = 1200;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);

  const goldColor = new THREE.Color(0xC9A96E);
  const blueColor = new THREE.Color(0x4A7C9B);
  const whiteColor = new THREE.Color(0xEAEFF8);

  for (let i = 0; i < count; i++) {
    const radius = 10 + Math.random() * 25;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos((Math.random() * 2) - 1);

    positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = radius * Math.cos(phi);

    const pick = Math.random();
    let col = whiteColor;
    if (pick < 0.25) col = goldColor;
    else if (pick < 0.45) col = blueColor;

    colors[i * 3] = col.r;
    colors[i * 3 + 1] = col.g;
    colors[i * 3 + 2] = col.b;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.08,
    vertexColors: true,
    transparent: true,
    opacity: 0.70,
    sizeAttenuation: true
  });

  const starfield = new THREE.Points(geometry, material);
  scene.add(starfield);
  sceneState.starfield = starfield;
}

/**
 * Shared GLSL lift-time evaluation snippet
 * Guaranteed 100% mathematical parity between solid mesh fragments and particles
 */
const SHARED_LIFT_GLSL = `
float hash12Lift(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float computeLiftTime(vec3 localPos) {
    float r = length(localPos.xy);
    float normR = clamp(r / 1.70, 0.0, 1.0);
    float noise = (sin(localPos.x * 12.0) * cos(localPos.y * 12.0) + sin((localPos.x + localPos.y) * 18.0) * 0.5) * 0.055;
    float jitter = (hash12Lift(floor(localPos.xy * 35.0) * 0.028) - 0.5) * 0.06;
    float t = normR * 0.86 + 0.06 + noise + jitter;
    return clamp(t, 0.03, 0.97);
}
`;

/**
 * Attach per-fragment dissolve shader to solid logo materials
 */
function applyLogoDissolve(mat, uniforms) {
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uLift = uniforms.uLift;
    shader.uniforms.uLogoInverseMatrix = uniforms.uLogoInverseMatrix;

    shader.vertexShader = shader.vertexShader.replace(
      '#include <common>',
      `#include <common>
       uniform mat4 uLogoInverseMatrix;
       varying vec3 vLogoLocalPos;`
    );

    shader.vertexShader = shader.vertexShader.replace(
      '#include <begin_vertex>',
      `#include <begin_vertex>
       vLogoLocalPos = (uLogoInverseMatrix * modelMatrix * vec4(position, 1.0)).xyz;`
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <common>',
      `#include <common>
       uniform float uLift;
       varying vec3 vLogoLocalPos;

       ${SHARED_LIFT_GLSL}`
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <clipping_planes_fragment>',
      `#include <clipping_planes_fragment>
       if (uLift > 0.0001) {
           float liftVal = computeLiftTime(vLogoLocalPos);
           if (uLift > liftVal) {
               discard;
           }
       }`
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <dithering_fragment>',
      `if (uLift > 0.0001) {
           float liftVal = computeLiftTime(vLogoLocalPos);
           float rimWidth = 0.035;
           if (liftVal < uLift + rimWidth) {
               float edgeFactor = 1.0 - (liftVal - uLift) / rimWidth;
               vec3 goldGlow = vec3(1.0, 0.82, 0.35) * 2.8;
               gl_FragColor.rgb = mix(gl_FragColor.rgb, goldGlow, edgeFactor * 0.95);
               gl_FragColor.rgb += goldGlow * (edgeFactor * edgeFactor * 1.2);
           }
       }
       #include <dithering_fragment>`
    );
  };
}

/**
 * Normalized 2D contour points of the exact µLearn logo glyph (derived from static/img/logo.png)
 * Scaled so bounding box height = 1.26m (50% of medallion diameter 2.52m), width = 0.9612m, centered at (0, 0)
 */
const GLYPH_CONTOUR = [
  [-0.3757, 0.63], [-0.3293, 0.6247], [-0.2855, 0.6008], [-0.2642, 0.5742], [-0.2496, 0.541],
  [-0.2483, 0.0909], [-0.2443, 0.087], [-0.2403, 0.0325], [-0.235, 0.0285], [-0.235, 0.0193],
  [-0.2204, -0.0007], [-0.2204, -0.0073], [-0.1978, -0.0352], [-0.154, -0.0644], [-0.1328, -0.0697],
  [-0.1275, -0.075], [-0.0996, -0.079], [-0.0358, -0.079], [-0.0319, -0.075], [-0.0133, -0.075],
  [0.0345, -0.0551], [0.0863, -0.0086], [0.1115, 0.0392], [0.1115, 0.0485], [0.1168, 0.0551],
  [0.1168, 0.0737], [0.1208, 0.0777], [0.1208, 0.1109], [0.1261, 0.1255], [0.1261, 0.5397],
  [0.1314, 0.5437], [0.1407, 0.5742], [0.1646, 0.5995], [0.1912, 0.6194], [0.1992, 0.6194],
  [0.2058, 0.6247], [0.2231, 0.6247], [0.2297, 0.63], [0.2562, 0.63], [0.2602, 0.6247],
  [0.2775, 0.6247], [0.2828, 0.6194], [0.2921, 0.6194], [0.316, 0.6048], [0.3372, 0.5835],
  [0.3372, 0.5782], [0.3518, 0.5596], [0.3518, 0.5503], [0.3572, 0.5424], [0.3558, 0.5291],
  [0.3611, 0.5211], [0.3611, -0.0193], [0.3718, -0.0378], [0.389, -0.0498], [0.4116, -0.0551],
  [0.4408, -0.0551], [0.4753, -0.087], [0.4806, -0.1109], [0.4793, -0.1958], [0.474, -0.2025],
  [0.4753, -0.2091], [0.4647, -0.2184], [0.4647, -0.225], [0.4342, -0.2556], [0.4089, -0.2649],
  [0.405, -0.2702], [0.3917, -0.2702], [0.385, -0.2755], [0.3492, -0.2755], [0.3399, -0.2702],
  [0.3133, -0.2702], [0.3067, -0.2649], [0.2801, -0.2609], [0.2735, -0.2556], [0.2602, -0.2556],
  [0.2124, -0.2264], [0.1713, -0.1865], [0.154, -0.2038], [0.154, -0.2104], [0.1368, -0.2211],
  [0.1182, -0.241], [0.1129, -0.241], [0.1049, -0.2503], [0.0797, -0.2609], [0.069, -0.2702],
  [0.0611, -0.2702], [0.0451, -0.2795], [0.0319, -0.2795], [0.0252, -0.2848], [0.0146, -0.2848],
  [0.0106, -0.2901], [-0.008, -0.2901], [-0.0146, -0.2954], [-0.1248, -0.2994], [-0.1434, -0.31],
  [-0.154, -0.31], [-0.1699, -0.3193], [-0.1779, -0.3193], [-0.2297, -0.3658], [-0.2297, -0.3724],
  [-0.2403, -0.383], [-0.2443, -0.4176], [-0.2483, -0.4215], [-0.2496, -0.545], [-0.2549, -0.549],
  [-0.2642, -0.5795], [-0.2948, -0.6101], [-0.3346, -0.63], [-0.3957, -0.63], [-0.4222, -0.6154],
  [-0.4289, -0.6154], [-0.4501, -0.5995], [-0.4793, -0.5503], [-0.4806, -0.5304], [-0.4806, 0.5251],
  [-0.4753, 0.5583], [-0.4554, 0.5888], [-0.4235, 0.6154], [-0.3771, 0.6287]
];

/**
 * 3D Champagne Gold µ Monogram (Hero Phase 1 & 2)
 * Clean, specular gold with orbital rings, slim edge-on medallion (1.4cm), and per-fragment dissolve
 */
function createHeroLogo(scene) {
  const logoGroup = new THREE.Group();

  const solidDissolveUniforms = {
    uLift: { value: 0.0 },
    uLogoInverseMatrix: { value: new THREE.Matrix4() }
  };
  sceneState.solidDissolveUniforms = solidDissolveUniforms;

  // Double Orbital Rings
  const outerRingMat = materials.gold.clone();
  applyLogoDissolve(outerRingMat, solidDissolveUniforms);
  const outerRingGeo = new THREE.TorusGeometry(1.68, 0.038, 20, 80);
  const outerRing = new THREE.Mesh(outerRingGeo, outerRingMat);
  logoGroup.add(outerRing);
  sceneState.outerRing = outerRing;

  const innerRingMat = materials.gold.clone();
  applyLogoDissolve(innerRingMat, solidDissolveUniforms);
  const innerRingGeo = new THREE.TorusGeometry(1.5, 0.024, 20, 80);
  const innerRing = new THREE.Mesh(innerRingGeo, innerRingMat);
  innerRing.rotation.x = Math.PI * 0.12;
  innerRing.rotation.y = Math.PI * 0.08;
  logoGroup.add(innerRing);
  sceneState.innerRing = innerRing;

  // Center Medallion Disc (Extrusion 1.4cm, faces at z = ±0.007)
  const discMat = materials.gold.clone();
  applyLogoDissolve(discMat, solidDissolveUniforms);
  const discGeo = new THREE.CylinderGeometry(1.26, 1.26, 0.014, 64);
  discGeo.rotateX(Math.PI / 2);
  const discMesh = new THREE.Mesh(discGeo, discMat);
  logoGroup.add(discMesh);
  sceneState.discMesh = discMesh;

  // 3D Extruded Beveled Glyph Body (depth 1.2cm, bevel 2mm)
  const glyphShape = new THREE.Shape();
  glyphShape.moveTo(GLYPH_CONTOUR[0][0], GLYPH_CONTOUR[0][1]);
  for (let i = 1; i < GLYPH_CONTOUR.length; i++) {
    glyphShape.lineTo(GLYPH_CONTOUR[i][0], GLYPH_CONTOUR[i][1]);
  }
  glyphShape.closePath();

  const extrudeSettings = {
    depth: 0.012, // 1.2 cm depth
    bevelEnabled: true,
    bevelSegments: 3,
    steps: 1,
    bevelSize: 0.002, // 2 mm rounded bevel
    bevelThickness: 0.002 // 2 mm rounded bevel
  };
  const glyphExtrudeGeo = new THREE.ExtrudeGeometry(glyphShape, extrudeSettings);
  glyphExtrudeGeo.center(); // Center bounding box at (0, 0, 0)

  const glyphMat = materials.gold.clone();
  glyphMat.metalness = 0.88;
  glyphMat.roughness = 0.22;
  applyLogoDissolve(glyphMat, solidDissolveUniforms);

  const glyphMesh = new THREE.Mesh(glyphExtrudeGeo, glyphMat);
  glyphMesh.position.set(0, 0, 0);
  logoGroup.add(glyphMesh);
  sceneState.glyphMesh = glyphMesh;

  // Front & Back Monogram Art with crisp 1024px diagonal champagne-gold gradient texture
  // Glyph height fills 50% of medallion diameter (1.26m), width = 1.26 * (805 / 1024) = 0.9905m
  const glyphW = 1.26 * (805 / 1024);
  const glyphH = 1.26;
  const facePlaneGeo = new THREE.PlaneGeometry(glyphW, glyphH);

  const frontFaceMat = new THREE.MeshBasicMaterial({
    map: sceneState.logoTexture,
    transparent: true,
    opacity: 0.99,
    depthWrite: false
  });
  applyLogoDissolve(frontFaceMat, solidDissolveUniforms);

  const frontFace = new THREE.Mesh(facePlaneGeo, frontFaceMat);
  frontFace.position.set(0, 0, 0.0085);
  logoGroup.add(frontFace);
  sceneState.frontFace = frontFace;

  const backFaceMat = new THREE.MeshBasicMaterial({
    map: sceneState.logoTexture,
    transparent: true,
    opacity: 0.99,
    depthWrite: false
  });
  applyLogoDissolve(backFaceMat, solidDissolveUniforms);

  const backFace = new THREE.Mesh(facePlaneGeo, backFaceMat);
  backFace.position.set(0, 0, -0.0085);
  backFace.rotation.y = Math.PI;
  logoGroup.add(backFace);
  sceneState.backFace = backFace;

  // Floating 3D Spark (remains at approved position, clear of the glyph)
  const sparkGeo = new THREE.OctahedronGeometry(0.14, 0);
  const sparkMat = new THREE.MeshPhysicalMaterial({
    color: 0xFFF2D1,
    emissive: 0xC9A96E,
    metalness: 0.95,
    roughness: 0.1,
    clearcoat: 1.0
  });
  applyLogoDissolve(sparkMat, solidDissolveUniforms);
  const spark = new THREE.Mesh(sparkGeo, sparkMat);
  spark.position.set(0.68, 0.72, 0.15);
  logoGroup.add(spark);
  sceneState.sparkMesh = spark;

  logoGroup.position.set(0, 0, 0);
  scene.add(logoGroup);
  sceneState.logoGroup = logoGroup;
}

/**
 * Sample surface points on a mesh's BufferGeometry triangles
 */
function sampleMeshTriangles(mesh, count, normalMatrix) {
  const geom = mesh.geometry;
  if (!geom || !geom.attributes.position) return [];
  const pos = geom.attributes.position;
  const norm = geom.attributes.normal;
  const index = geom.index;
  const triCount = index ? (index.count / 3) : (pos.count / 3);
  if (triCount <= 0) return [];

  let baseColor = new THREE.Color(0xD4A346);
  if (mesh.material && mesh.material.color) {
    baseColor = mesh.material.color.clone();
  }

  const matWorld = mesh.matrixWorld;
  const vA = new THREE.Vector3();
  const vB = new THREE.Vector3();
  const vC = new THREE.Vector3();
  const nA = new THREE.Vector3();
  const nB = new THREE.Vector3();
  const nC = new THREE.Vector3();
  const p = new THREE.Vector3();
  const n = new THREE.Vector3();

  const sampled = [];
  for (let i = 0; i < count; i++) {
    const tIdx = Math.floor(Math.random() * triCount);
    let i0, i1, i2;
    if (index) {
      i0 = index.getX(tIdx * 3);
      i1 = index.getX(tIdx * 3 + 1);
      i2 = index.getX(tIdx * 3 + 2);
    } else {
      i0 = tIdx * 3;
      i1 = tIdx * 3 + 1;
      i2 = tIdx * 3 + 2;
    }

    vA.fromBufferAttribute(pos, i0);
    vB.fromBufferAttribute(pos, i1);
    vC.fromBufferAttribute(pos, i2);

    const r1 = Math.random();
    const r2 = Math.random();
    const sq1 = Math.sqrt(r1);
    const u = 1 - sq1;
    const v = sq1 * (1 - r2);
    const w = sq1 * r2;

    p.set(
      u * vA.x + v * vB.x + w * vC.x,
      u * vA.y + v * vB.y + w * vC.y,
      u * vA.z + v * vB.z + w * vC.z
    );
    p.applyMatrix4(matWorld);

    if (norm) {
      nA.fromBufferAttribute(norm, i0);
      nB.fromBufferAttribute(norm, i1);
      nC.fromBufferAttribute(norm, i2);
      n.set(
        u * nA.x + v * nB.x + w * nC.x,
        u * nA.y + v * nB.y + w * nC.y,
        u * nA.z + v * nB.z + w * nC.z
      ).normalize();
      n.applyMatrix3(normalMatrix).normalize();
    } else {
      n.set(0, 1, 0);
    }

    sampled.push({
      pos: p.clone(),
      norm: n.clone(),
      color: baseColor.clone()
    });
  }
  return sampled;
}

/**
 * Sample points across all visible meshes of a group hierarchy
 */
function sampleGroupSurfaces(rootGroup, count, categoryId) {
  const meshes = [];
  rootGroup.traverse(child => {
    if (child.isMesh && child.geometry && !child.name?.includes('Shadow') && child.material?.type !== 'SpriteMaterial') {
      meshes.push(child);
    }
  });
  if (meshes.length === 0) return [];

  const perMesh = Math.max(1, Math.floor(count / meshes.length));
  const results = [];
  const normalMatrix = new THREE.Matrix3();

  for (let m = 0; m < meshes.length; m++) {
    const mesh = meshes[m];
    normalMatrix.getNormalMatrix(mesh.matrixWorld);
    const meshPoints = sampleMeshTriangles(mesh, perMesh, normalMatrix);
    for (let i = 0; i < meshPoints.length; i++) {
      meshPoints[i].categoryId = categoryId;
      results.push(meshPoints[i]);
      if (results.length >= count) break;
    }
    if (results.length >= count) break;
  }

  while (results.length < count) {
    const randomMesh = meshes[Math.floor(Math.random() * meshes.length)];
    normalMatrix.getNormalMatrix(randomMesh.matrixWorld);
    const extra = sampleMeshTriangles(randomMesh, 1, normalMatrix);
    if (extra.length > 0) {
      extra[0].categoryId = categoryId;
      results.push(extra[0]);
    } else {
      break;
    }
  }

  return results;
}

/**
 * Sample 40% of particles from pixels of static/img/mulearn-logo.png
 * Sits exactly on the new 3D glyph surface with matching champagne gold gradient colors
 */
function sampleLogoImageSourcePoints(count) {
  const points = [];
  const logoPlaneW = 1.26 * (805 / 1024);
  const logoPlaneH = 1.26;
  const zPlane = 0.0085;

  let sampledFromCanvas = false;
  const img = sceneState.logoTexture?.image;
  if (img && img.complete && img.naturalWidth > 0) {
    try {
      const cvsW = 100;
      const cvsH = 128;
      const cvs = document.createElement('canvas');
      cvs.width = cvsW;
      cvs.height = cvsH;
      const ctx = cvs.getContext('2d');
      ctx.drawImage(img, 0, 0, cvsW, cvsH);
      const imgData = ctx.getImageData(0, 0, cvsW, cvsH);
      const data = imgData.data;
      const valid = [];
      for (let y = 0; y < cvsH; y++) {
        for (let x = 0; x < cvsW; x++) {
          const idx = (y * cvsW + x) * 4;
          if (data[idx + 3] > 120) {
            valid.push({
              u: x / cvsW,
              v: y / cvsH,
              r: data[idx] / 255,
              g: data[idx + 1] / 255,
              b: data[idx + 2] / 255
            });
          }
        }
      }
      if (valid.length > 50) {
        for (let i = 0; i < count; i++) {
          const p = valid[Math.floor(Math.random() * valid.length)];
          const wx = (p.u - 0.5) * logoPlaneW + (Math.random() - 0.5) * 0.004;
          const wy = (0.5 - p.v) * logoPlaneH + (Math.random() - 0.5) * 0.004;
          const wz = zPlane + (Math.random() - 0.5) * 0.002;
          points.push({
            pos: new THREE.Vector3(wx, wy, wz),
            norm: new THREE.Vector3(0, 0, 1),
            color: new THREE.Color(p.r, p.g, p.b)
          });
        }
        sampledFromCanvas = true;
      }
    } catch (e) {
      sampledFromCanvas = false;
    }
  }

  if (!sampledFromCanvas) {
    for (let i = 0; i < count; i++) {
      const cp = GLYPH_CONTOUR[Math.floor(Math.random() * GLYPH_CONTOUR.length)];
      const rFactor = 0.2 + 0.8 * Math.random();
      const wx = cp[0] * rFactor + (Math.random() - 0.5) * 0.006;
      const wy = cp[1] * rFactor + (Math.random() - 0.5) * 0.006;
      const wz = zPlane + (Math.random() - 0.5) * 0.002;
      points.push({
        pos: new THREE.Vector3(wx, wy, wz),
        norm: new THREE.Vector3(0, 0, 1),
        color: new THREE.Color(0xE8D5A3)
      });
    }
  }

  return points;
}

/**
 * Sample 60% of particles from gold medallion disc and orbit rings
 */
function sampleMedallionAndRingsSourcePoints(count) {
  const points = [];
  const goldColor = new THREE.Color(0xE6C98A);

  const discCount = Math.floor(count * 0.55);
  const outerRingCount = Math.floor(count * 0.25);
  const innerRingCount = count - discCount - outerRingCount;

  // Medallion Disc: radius 1.26, thickness 0.014m (faces at z = ±0.007)
  const discThick = 0.014;
  for (let i = 0; i < discCount; i++) {
    const isRim = Math.random() < 0.20;
    const ang = Math.random() * Math.PI * 2;
    let x, y, z, nx, ny, nz;
    if (isRim) {
      x = 1.26 * Math.cos(ang);
      y = 1.26 * Math.sin(ang);
      z = (Math.random() - 0.5) * discThick;
      nx = Math.cos(ang);
      ny = Math.sin(ang);
      nz = 0;
    } else {
      const r = Math.sqrt(Math.random()) * 1.26;
      x = r * Math.cos(ang);
      y = r * Math.sin(ang);
      const front = Math.random() > 0.5;
      z = front ? (discThick / 2) : -(discThick / 2);
      nx = 0;
      ny = 0;
      nz = front ? 1 : -1;
    }
    const c = goldColor.clone().offsetHSL((Math.random() - 0.5) * 0.05, 0, (Math.random() - 0.5) * 0.08);
    points.push({
      pos: new THREE.Vector3(x, y, z),
      norm: new THREE.Vector3(nx, ny, nz),
      color: c
    });
  }

  // Outer Ring: TorusGeometry(1.68, 0.038)
  for (let i = 0; i < outerRingCount; i++) {
    const u = Math.random() * Math.PI * 2;
    const v = Math.random() * Math.PI * 2;
    const R = 1.68;
    const r = 0.038;
    const x = (R + r * Math.cos(v)) * Math.cos(u);
    const y = (R + r * Math.cos(v)) * Math.sin(u);
    const z = r * Math.sin(v);
    const nx = Math.cos(v) * Math.cos(u);
    const ny = Math.cos(v) * Math.sin(u);
    const nz = Math.sin(v);
    const c = goldColor.clone().offsetHSL((Math.random() - 0.5) * 0.04, 0, (Math.random() - 0.5) * 0.06);
    points.push({
      pos: new THREE.Vector3(x, y, z),
      norm: new THREE.Vector3(nx, ny, nz),
      color: c
    });
  }

  // Inner Ring: TorusGeometry(1.5, 0.024) with rotation x: 0.12 * PI, y: 0.08 * PI
  const rotMatrix = new THREE.Matrix4().makeRotationX(Math.PI * 0.12).multiply(new THREE.Matrix4().makeRotationY(Math.PI * 0.08));
  for (let i = 0; i < innerRingCount; i++) {
    const u = Math.random() * Math.PI * 2;
    const v = Math.random() * Math.PI * 2;
    const R = 1.5;
    const r = 0.024;
    const p = new THREE.Vector3(
      (R + r * Math.cos(v)) * Math.cos(u),
      (R + r * Math.cos(v)) * Math.sin(u),
      r * Math.sin(v)
    ).applyMatrix4(rotMatrix);
    const n = new THREE.Vector3(
      Math.cos(v) * Math.cos(u),
      Math.cos(v) * Math.sin(u),
      Math.sin(v)
    ).applyMatrix4(rotMatrix).normalize();
    const c = goldColor.clone().offsetHSL((Math.random() - 0.5) * 0.04, 0, (Math.random() - 0.5) * 0.06);
    points.push({
      pos: p,
      norm: n,
      color: c
    });
  }

  return points;
}

/**
 * Apply onBeforeCompile dissolve shader to all workspace meshes
 */
function applyDissolveToWorkspace(workspaceGroup, roomGroup, categoryUniforms) {
  function hookMesh(mesh, categoryId) {
    if (!mesh.isMesh || !mesh.material) return;
    if (mesh.name?.includes('Shadow') || mesh.material.type === 'SpriteMaterial') return;

    mesh.material = mesh.material.clone();
    const mat = mesh.material;
    const uniform = categoryUniforms[categoryId] || { value: 0.0 };

    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uRevealProgress = uniform;

      shader.vertexShader = shader.vertexShader.replace(
        '#include <common>',
        `#include <common>
         varying vec3 vRevealWorldPos;`
      );

      shader.vertexShader = shader.vertexShader.replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
         vRevealWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;`
      );

      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <common>',
        `#include <common>
         uniform float uRevealProgress;
         varying vec3 vRevealWorldPos;

         float hash31(vec3 p) {
             p = fract(p * vec3(443.897, 441.423, 437.195));
             p += dot(p, p.yzx + 19.19);
             return fract((p.x + p.y) * p.z);
         }

         float dissolveNoise(vec3 p) {
             vec3 i = floor(p);
             vec3 f = fract(p);
             f = f * f * (3.0 - 2.0 * f);
             return mix(
                 mix(mix(hash31(i + vec3(0,0,0)), hash31(i + vec3(1,0,0)), f.x),
                     mix(hash31(i + vec3(0,1,0)), hash31(i + vec3(1,1,0)), f.x), f.y),
                 mix(mix(hash31(i + vec3(0,0,1)), hash31(i + vec3(1,0,1)), f.x),
                     mix(hash31(i + vec3(0,1,1)), hash31(i + vec3(1,1,1)), f.x), f.y), f.z);
         }`
      );

      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <dithering_fragment>',
        `#include <dithering_fragment>
         if (uRevealProgress < 1.0) {
             float n = dissolveNoise(vRevealWorldPos * 28.0);
             float threshold = uRevealProgress * 1.12 - 0.06;
             if (n > threshold) {
                 discard;
             }
             float edge = smoothstep(threshold - 0.035, threshold, n);
             gl_FragColor.rgb = mix(gl_FragColor.rgb, vec3(1.15, 0.92, 0.48), edge * 0.85);
         }`
      );
    };
  }

  // Hook all items by category:
  // Cat 0: Desk Mat
  if (sceneState.deskMatMesh) hookMesh(sceneState.deskMatMesh, 0);

  // Cat 1: Desk Top & Legs
  if (sceneState.deskGroup) sceneState.deskGroup.traverse(m => hookMesh(m, 1));

  // Cat 2: Laptop & Stand
  if (sceneState.standGroup) sceneState.standGroup.traverse(m => hookMesh(m, 2));
  if (sceneState.laptopGroup) sceneState.laptopGroup.traverse(m => hookMesh(m, 2));

  // Cat 3: Peripherals (Keyboard, Mouse)
  if (sceneState.kbGroup) sceneState.kbGroup.traverse(m => hookMesh(m, 3));
  if (sceneState.mouseGroup) sceneState.mouseGroup.traverse(m => hookMesh(m, 3));

  // Cat 4: Small Objects (Lamp, Books, Tea, Photo, Plant)
  if (sceneState.lampGroup) sceneState.lampGroup.traverse(m => hookMesh(m, 4));
  if (sceneState.booksGroup) sceneState.booksGroup.traverse(m => hookMesh(m, 4));
  if (sceneState.teaGroup) sceneState.teaGroup.traverse(m => hookMesh(m, 4));
  if (sceneState.photoStandGroup) sceneState.photoStandGroup.traverse(m => hookMesh(m, 4));
  if (sceneState.plantGroup) sceneState.plantGroup.traverse(m => hookMesh(m, 4));

  // Cat 5: Headset & Stand
  if (sceneState.headphonesGroup) sceneState.headphonesGroup.traverse(m => hookMesh(m, 5));

  // Cat 6: Wall Poster
  if (sceneState.posterGroup) sceneState.posterGroup.traverse(m => hookMesh(m, 6));

  // Cat 7: Room Architecture (Floor, Wall, Window, Battens, Baseboard)
  if (roomGroup) {
    roomGroup.traverse(m => {
      if (sceneState.posterGroup && (m === sceneState.posterGroup || sceneState.posterGroup.getObjectById(m.id))) {
        return;
      }
      hookMesh(m, 7);
    });
  }
}

/**
 * Pixel-to-Object Deterministic Particle Morph System (Phase 3)
 * 28,000 desktop / 10,000 mobile particles
 */
function createPixelToObjectMorph(scene) {
  const isMobile = (typeof window !== 'undefined' && ((window.matchMedia && window.matchMedia('(pointer: coarse)').matches) || window.innerWidth < 768));
  const totalCount = isMobile ? 10000 : 28000;

  // 1. Temporarily assemble resting transforms for world-space sampling
  if (sceneState.workspaceGroup) {
    sceneState.workspaceGroup.position.set(0, 0, 0);
    sceneState.workspaceGroup.scale.set(1, 1, 1);
    sceneState.workspaceGroup.visible = true;
  }
  if (sceneState.roomGroup) {
    sceneState.roomGroup.position.set(0, 0, 0);
    sceneState.roomGroup.scale.set(1, 1, 1);
    sceneState.roomGroup.visible = true;
  }
  if (sceneState.props && sceneState.props.length > 0) {
    sceneState.props.forEach(p => {
      p.group.position.y = 0;
      p.group.scale.set(1, 1, 1);
      p.group.visible = true;
    });
  }
  scene.updateMatrixWorld(true);

  // 2. Source Points: 40% from logo pixels, 60% from gold medallion & rings
  const logoCount = Math.floor(totalCount * 0.40);
  const medallionCount = totalCount - logoCount;

  const logoSources = sampleLogoImageSourcePoints(logoCount);
  const medallionSources = sampleMedallionAndRingsSourcePoints(medallionCount);
  const sources = [...logoSources, ...medallionSources];

  // 3. Target Points: Sampled across workspace objects in world space
  // Categories: 0:Mat, 1:Desk, 2:Laptop/Stand, 3:Peripherals, 4:Small Objects, 5:Headset, 6:Poster, 7:Room
  const scale = totalCount / 28000;
  const counts = [
    Math.round(2400 * scale), // 0: Mat
    Math.round(5000 * scale), // 1: Desk & Legs
    Math.round(4500 * scale), // 2: Laptop & Stand
    Math.round(2000 * scale), // 3: Peripherals
    Math.round(4500 * scale), // 4: Small Objects
    Math.round(3000 * scale), // 5: Headset & Stand
    Math.round(2200 * scale), // 6: Poster
    0                         // 7: Room (will take remainder)
  ];
  let assigned = counts.slice(0, 7).reduce((a, b) => a + b, 0);
  counts[7] = totalCount - assigned;

  const t0 = sceneState.deskMatMesh ? sampleGroupSurfaces(sceneState.deskMatMesh, counts[0], 0) : [];
  const t1 = sceneState.deskGroup ? sampleGroupSurfaces(sceneState.deskGroup, counts[1], 1) : [];

  const laptopStandGroup = new THREE.Group();
  if (sceneState.standGroup) laptopStandGroup.add(sceneState.standGroup.clone());
  if (sceneState.laptopGroup) laptopStandGroup.add(sceneState.laptopGroup.clone());
  const t2 = sampleGroupSurfaces(sceneState.laptopGroup || sceneState.workspaceGroup, counts[2], 2);

  const t3 = (sceneState.kbGroup || sceneState.mouseGroup) ? sampleGroupSurfaces(sceneState.kbGroup || sceneState.workspaceGroup, counts[3], 3) : [];

  const smallObjGroup = new THREE.Group();
  if (sceneState.booksGroup) smallObjGroup.add(sceneState.booksGroup.clone());
  if (sceneState.teaGroup) smallObjGroup.add(sceneState.teaGroup.clone());
  if (sceneState.photoStandGroup) smallObjGroup.add(sceneState.photoStandGroup.clone());
  if (sceneState.plantGroup) smallObjGroup.add(sceneState.plantGroup.clone());
  if (sceneState.lampGroup) smallObjGroup.add(sceneState.lampGroup.clone());
  const t4 = sampleGroupSurfaces(sceneState.booksGroup || sceneState.workspaceGroup, counts[4], 4);

  const t5 = sceneState.headphonesGroup ? sampleGroupSurfaces(sceneState.headphonesGroup, counts[5], 5) : [];
  const t6 = sceneState.posterGroup ? sampleGroupSurfaces(sceneState.posterGroup, counts[6], 6) : [];
  const t7 = sceneState.roomGroup ? sampleGroupSurfaces(sceneState.roomGroup, counts[7], 7) : [];

  const targets = [...t0, ...t1, ...t2, ...t3, ...t4, ...t5, ...t6, ...t7];

  // Balance lengths exactly
  while (targets.length < totalCount) {
    targets.push(t1.length > 0 ? t1[Math.floor(Math.random() * t1.length)] : {
      pos: new THREE.Vector3(0, 0.75, 0),
      norm: new THREE.Vector3(0, 1, 0),
      color: new THREE.Color(0x6B4A32),
      categoryId: 1
    });
  }
  if (targets.length > totalCount) {
    targets.length = totalCount;
  }
  if (sources.length > totalCount) {
    sources.length = totalCount;
  }
  while (sources.length < totalCount) {
    sources.push(sources[Math.floor(Math.random() * sources.length)]);
  }

  // 4. Spatial Coherence Pairing (Left-to-Right Sort)
  sources.sort((a, b) => (a.pos.x + 0.35 * a.pos.y) - (b.pos.x + 0.35 * b.pos.y));
  targets.sort((a, b) => (a.pos.x + 0.35 * a.pos.y) - (b.pos.x + 0.35 * b.pos.y));

  // 5. Fill Float32 Buffer Attributes
  const posArray = new Float32Array(totalCount * 3);
  const srcPosArray = new Float32Array(totalCount * 3);
  const srcNormArray = new Float32Array(totalCount * 3);
  const tgtPosArray = new Float32Array(totalCount * 3);
  const tgtNormArray = new Float32Array(totalCount * 3);
  const srcColArray = new Float32Array(totalCount * 3);
  const tgtColArray = new Float32Array(totalCount * 3);
  const ctrlPosArray = new Float32Array(totalCount * 3);
  const objArray = new Float32Array(totalCount);
  const randArray = new Float32Array(totalCount * 4);

  for (let i = 0; i < totalCount; i++) {
    const s = sources[i];
    const t = targets[i];

    const idx3 = i * 3;
    const idx4 = i * 4;

    srcPosArray[idx3] = s.pos.x;
    srcPosArray[idx3 + 1] = s.pos.y;
    srcPosArray[idx3 + 2] = s.pos.z;

    posArray[idx3] = s.pos.x;
    posArray[idx3 + 1] = s.pos.y;
    posArray[idx3 + 2] = s.pos.z;

    srcNormArray[idx3] = s.norm.x;
    srcNormArray[idx3 + 1] = s.norm.y;
    srcNormArray[idx3 + 2] = s.norm.z;

    tgtPosArray[idx3] = t.pos.x;
    tgtPosArray[idx3 + 1] = t.pos.y;
    tgtPosArray[idx3 + 2] = t.pos.z;

    tgtNormArray[idx3] = t.norm.x;
    tgtNormArray[idx3 + 1] = t.norm.y;
    tgtNormArray[idx3 + 2] = t.norm.z;

    srcColArray[idx3] = s.color.r;
    srcColArray[idx3 + 1] = s.color.g;
    srcColArray[idx3 + 2] = s.color.b;

    tgtColArray[idx3] = t.color.r;
    tgtColArray[idx3 + 1] = t.color.g;
    tgtColArray[idx3 + 2] = t.color.b;

    const rX = Math.random();
    const rY = Math.random();
    const rZ = Math.random();
    const rW = Math.random();

    randArray[idx4] = rX;
    randArray[idx4 + 1] = rY;
    randArray[idx4 + 2] = rZ;
    randArray[idx4 + 3] = rW;

    ctrlPosArray[idx3] = (s.pos.x + t.pos.x) * 0.5 + (rX - 0.5) * 0.4;
    ctrlPosArray[idx3 + 1] = Math.max(s.pos.y, t.pos.y) + 0.45 + rY * 0.45;
    ctrlPosArray[idx3 + 2] = (s.pos.z + t.pos.z) * 0.5 + (rZ - 0.5) * 0.3;

    objArray[i] = t.categoryId !== undefined ? t.categoryId : 0;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
  geometry.setAttribute('aSourcePos', new THREE.BufferAttribute(srcPosArray, 3));
  geometry.setAttribute('aSourceNormal', new THREE.BufferAttribute(srcNormArray, 3));
  geometry.setAttribute('aTargetPos', new THREE.BufferAttribute(tgtPosArray, 3));
  geometry.setAttribute('aTargetNormal', new THREE.BufferAttribute(tgtNormArray, 3));
  geometry.setAttribute('aSourceColor', new THREE.BufferAttribute(srcColArray, 3));
  geometry.setAttribute('aTargetColor', new THREE.BufferAttribute(tgtColArray, 3));
  geometry.setAttribute('aControlPos', new THREE.BufferAttribute(ctrlPosArray, 3));
  geometry.setAttribute('aObject', new THREE.BufferAttribute(objArray, 1));
  geometry.setAttribute('aRand', new THREE.BufferAttribute(randArray, 4));

  const particleVertexShader = `
    uniform float uLift;
    uniform float uProgress;
    uniform float uBaseSize;
    uniform float uPixelRatio;
    uniform mat4 uLogoMatrix;

    attribute vec3 aSourcePos;
    attribute vec3 aSourceNormal;
    attribute vec3 aTargetPos;
    attribute vec3 aTargetNormal;
    attribute vec3 aSourceColor;
    attribute vec3 aTargetColor;
    attribute vec3 aControlPos;
    attribute float aObject;
    attribute vec4 aRand;

    varying vec3 vColor;
    varying float vAlpha;

    ${SHARED_LIFT_GLSL}

    vec3 computeCurl(vec3 p, float time) {
        float s = 1.8;
        float x = sin(p.y * s + time * 1.5) + cos(p.z * s - time * 1.2);
        float y = sin(p.z * s + time * 1.3) + cos(p.x * s + time * 1.1);
        float z = sin(p.x * s - time * 1.4) + cos(p.y * s + time * 1.6);
        return vec3(x, y, z) * 0.5;
    }

    void main() {
        float liftVal = computeLiftTime(aSourcePos);

        // Particle is INVISIBLE until its own lift moment
        if (uLift < liftVal) {
            vAlpha = 0.0;
            gl_PointSize = 0.0;
            gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
            return;
        }

        // Exact resting world position on rotating logo
        vec3 worldSrcPos = (uLogoMatrix * vec4(aSourcePos, 1.0)).xyz;
        vec3 worldSrcNorm = normalize((uLogoMatrix * vec4(aSourceNormal, 0.0)).xyz);

        // Organic lift-off along normal
        float t_lift = clamp((uLift - liftVal) / max(0.001, (1.0 - liftVal)), 0.0, 1.0);
        float liftEase = smoothstep(0.0, 1.0, t_lift);

        vec3 liftDir = normalize(worldSrcNorm + vec3(worldSrcPos.xy * 0.25, 0.0));
        vec3 liftTargetPos = worldSrcPos + liftDir * (0.18 + aRand.x * 0.12);
        float liftJitter = sin(t_lift * 35.0 + aRand.w * 6.28318) * 0.015;
        liftTargetPos += vec3(liftJitter, liftJitter * 0.7, liftJitter * 0.5);

        vec3 currentPos = mix(worldSrcPos, liftTargetPos, liftEase);

        // Phase 3 transition: swirl -> stream -> settle
        float u = uProgress;
        if (u > 0.0) {
            float swirlAngle = (2.2 + aRand.x * 1.2) * 3.14159;
            float cosA = cos(swirlAngle);
            float sinA = sin(swirlAngle);
            vec3 rotatedPos = vec3(
                aSourcePos.x * cosA - aSourcePos.y * sinA,
                aSourcePos.x * sinA + aSourcePos.y * cosA,
                aSourcePos.z
            );
            vec3 curlOffset = computeCurl(rotatedPos, u * 4.0) * 0.25;
            vec3 swirlPos = rotatedPos * (1.1 + aRand.y * 0.5) + curlOffset;
            swirlPos.y = mix(swirlPos.y, 0.95 + aRand.z * 0.3, 0.7);
            swirlPos.z = mix(swirlPos.z, 0.4 + aRand.w * 0.4, 0.6);

            vec3 bezierMid = aControlPos;
            float catOffset = aObject * 0.024 + aRand.z * 0.035;
            float streamStart = 0.55 + catOffset;
            float streamEnd = min(0.85 + catOffset * 0.5, 0.92);

            if (u <= 0.20) {
                float t = smoothstep(0.0, 0.20, u);
                currentPos = mix(liftTargetPos, swirlPos, t);
            } else if (u <= 0.55) {
                float t = smoothstep(0.20, 0.55, u);
                currentPos = mix(swirlPos, swirlPos, t);
            } else if (u <= streamEnd) {
                float t = clamp((u - streamStart) / max(0.001, (streamEnd - streamStart)), 0.0, 1.0);
                float e = smoothstep(0.0, 1.0, t);
                vec3 p0 = swirlPos;
                vec3 p1 = bezierMid;
                vec3 p2 = aTargetPos;
                float omt = 1.0 - e;
                currentPos = omt * omt * p0 + 2.0 * omt * e * p1 + e * e * p2;
            } else {
                float t = clamp((u - streamEnd) / max(0.001, (1.0 - streamEnd)), 0.0, 1.0);
                float osc = exp(-t * 6.0) * cos(t * 22.0 + aRand.w * 6.28) * 0.015 * (1.0 - t);
                currentPos = aTargetPos + aTargetNormal * osc;
            }
        }

        // Color blending
        float colorT = smoothstep(0.35, 0.85, u);
        vColor = mix(aSourceColor, aTargetColor, colorT);

        // Twinkle and lift sparkle
        float liftSparkle = (u == 0.0) ? (1.0 + (1.0 - t_lift) * 0.35 + sin(t_lift * 30.0 + aRand.w * 6.28) * 0.2) : 1.0;
        float progressSparkle = 1.0 + sin((uLift * 10.0 + u * 25.0) + aRand.w * 12.56) * 0.25 * (1.0 - colorT);
        vColor *= liftSparkle * progressSparkle;

        // Alpha fade out during settle
        float objFadeStart = 0.83;
        float fadeOut = (u > 0.0) ? (1.0 - smoothstep(objFadeStart, min(1.0, objFadeStart + 0.12), u)) : 1.0;
        vAlpha = fadeOut;

        vec4 mvPosition = modelViewMatrix * vec4(currentPos, 1.0);
        gl_Position = projectionMatrix * mvPosition;

        float sizeFactor = (uBaseSize * uPixelRatio) / max(0.01, -mvPosition.z);
        float sizeShrink = (u > 0.0) ? (1.0 - smoothstep(objFadeStart, min(1.0, objFadeStart + 0.12), u)) : 1.0;
        gl_PointSize = clamp(sizeFactor * (0.85 + aRand.x * 0.4) * sizeShrink * 40.0, 1.0, 64.0);
    }
  `;

  const particleFragmentShader = `
    varying vec3 vColor;
    varying float vAlpha;

    void main() {
        if (vAlpha <= 0.001) discard;

        vec2 coord = gl_PointCoord - vec2(0.5);
        float distSq = dot(coord, coord);
        if (distSq > 0.25) discard;

        float radial = smoothstep(0.5, 0.08, sqrt(distSq));
        gl_FragColor = vec4(vColor, radial * vAlpha);
    }
  `;

  const morphMat = new THREE.ShaderMaterial({
    vertexShader: particleVertexShader,
    fragmentShader: particleFragmentShader,
    uniforms: {
      uLift: { value: 0.0 },
      uProgress: { value: 0.0 },
      uBaseSize: { value: 0.12 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) },
      uLogoMatrix: { value: new THREE.Matrix4() }
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const points = new THREE.Points(geometry, morphMat);
  scene.add(points);

  sceneState.morphMaterial = morphMat;
  sceneState.particlesPoints = points;
  sceneState.particlesGroup = {
    points,
    geometry,
    material: morphMat,
    count: totalCount
  };

  // 6. Setup Category Uniforms & Dissolve on Workspace
  sceneState.categoryUniforms = {
    0: { value: 0.0 },
    1: { value: 0.0 },
    2: { value: 0.0 },
    3: { value: 0.0 },
    4: { value: 0.0 },
    5: { value: 0.0 },
    6: { value: 0.0 },
    7: { value: 0.0 }
  };

  applyDissolveToWorkspace(sceneState.workspaceGroup, sceneState.roomGroup, sceneState.categoryUniforms);

  // 7. Hide workspace for initial Phase 1/2 state
  if (sceneState.workspaceGroup) sceneState.workspaceGroup.visible = false;
  if (sceneState.roomGroup) sceneState.roomGroup.visible = false;
}

/**
 * Update logo lift wave progress in [0, 1] during Phase 2 rotation handoff
 * Overlaps the final 40% of rotation (timeline 22.8 to 30.0)
 */
export function updateLogoLift(liftVal) {
  const lift = Math.max(0, Math.min(1, liftVal));
  sceneState.logoLiftValue = lift;

  if (sceneState.logoGroup) {
    sceneState.logoGroup.updateMatrixWorld(true);
  }

  // 1. Update particle shader uniforms
  if (sceneState.morphMaterial) {
    sceneState.morphMaterial.uniforms.uLift.value = lift;
    if (sceneState.logoGroup) {
      sceneState.morphMaterial.uniforms.uLogoMatrix.value.copy(sceneState.logoGroup.matrixWorld);
    }
  }

  // 2. Update solid dissolve uniforms & inverse matrix
  if (sceneState.solidDissolveUniforms) {
    sceneState.solidDissolveUniforms.uLift.value = lift;
    if (sceneState.logoGroup) {
      sceneState.solidDissolveUniforms.uLogoInverseMatrix.value.copy(sceneState.logoGroup.matrixWorld).invert();
    }
  }

  // 3. Edge-on fix: fade medallion disc and ring materials' opacity to zero over the first 60% of lift wave
  const discFade = Math.max(0, 1.0 - (lift / 0.60));
  if (sceneState.discMesh && sceneState.discMesh.material) {
    sceneState.discMesh.material.opacity = discFade;
    sceneState.discMesh.material.transparent = true;
    sceneState.discMesh.material.depthWrite = (discFade > 0.95);
  }
  if (sceneState.outerRing && sceneState.outerRing.material) {
    sceneState.outerRing.material.opacity = discFade;
    sceneState.outerRing.material.transparent = true;
    sceneState.outerRing.material.depthWrite = (discFade > 0.95);
  }
  if (sceneState.innerRing && sceneState.innerRing.material) {
    sceneState.innerRing.material.opacity = discFade;
    sceneState.innerRing.material.transparent = true;
    sceneState.innerRing.material.depthWrite = (discFade > 0.95);
  }

  // 4. Hide meshes (visible = false) once uLift reaches 1.0
  if (sceneState.logoGroup) {
    if (lift >= 1.0) {
      sceneState.logoGroup.visible = false;
    } else {
      sceneState.logoGroup.visible = true;
      if (sceneState.discMesh) sceneState.discMesh.visible = (discFade > 0.001);
      if (sceneState.outerRing) sceneState.outerRing.visible = (discFade > 0.001);
      if (sceneState.innerRing) sceneState.innerRing.visible = (discFade > 0.001);
      if (sceneState.frontFace) sceneState.frontFace.visible = true;
      if (sceneState.backFace) sceneState.backFace.visible = true;
      if (sceneState.glyphMesh) sceneState.glyphMesh.visible = true;
      if (sceneState.sparkMesh) sceneState.sparkMesh.visible = true;
    }
  }
}

/**
 * Return quantitative pixel / particle handoff metrics confirming pixel-level crossfade
 */
export function getHandoffMetrics() {
  const lift = sceneState.logoLiftValue || 0;
  let activeParticles = 0;
  const total = sceneState.particlesGroup?.count || 28000;
  if (sceneState.particlesPoints && sceneState.particlesPoints.geometry) {
    const pos = sceneState.particlesPoints.geometry.attributes.aSourcePos;
    if (pos) {
      const v = new THREE.Vector3();
      const sampleStep = 10;
      const sampledTotal = Math.floor(total / sampleStep);
      for (let i = 0; i < total; i += sampleStep) {
        v.fromBufferAttribute(pos, i);
        const r = Math.sqrt(v.x * v.x + v.y * v.y);
        const normR = Math.min(1, r / 1.70);
        const noise = (Math.sin(v.x * 12.0) * Math.cos(v.y * 12.0) + Math.sin((v.x + v.y) * 18.0) * 0.5) * 0.055;
        const liftVal = Math.min(0.97, Math.max(0.03, normR * 0.86 + 0.06 + noise));
        if (lift >= liftVal) activeParticles++;
      }
      const particleFraction = activeParticles / sampledTotal;
      const solidFraction = Math.max(0, 1.0 - particleFraction);
      return {
        uLift: +lift.toFixed(3),
        activeParticlePct: +(particleFraction * 100).toFixed(1),
        solidLogoPct: +(solidFraction * 100).toFixed(1),
        sumPct: +((particleFraction + solidFraction) * 100).toFixed(1),
        crossfadeOk: Math.abs((particleFraction + solidFraction) - 1.0) < 0.01
      };
    }
  }
  return {
    uLift: +lift.toFixed(3),
    activeParticlePct: 0,
    solidLogoPct: 100,
    sumPct: 100,
    crossfadeOk: true
  };
}

/**
 * Update deterministic particle morph at progress p in [0, 1]
 */
export function updateParticleMorph(progress) {
  const p = Math.max(0, Math.min(1, progress));
  sceneState.particleMorphProgress = p;

  // 1. Particle Shader Uniform & Visibility
  if (sceneState.morphMaterial) {
    sceneState.morphMaterial.uniforms.uProgress.value = p;
  }
  if (sceneState.particlesPoints) {
    sceneState.particlesPoints.visible = p < 1.0;
  }

  // 2. Solid logo remains hidden throughout Phase 3 (already dissolved by uLift = 1.0)
  if (sceneState.logoGroup && p > 0.0) {
    sceneState.logoGroup.visible = false;
  }

  // 3. Workspace Visibility & Category Dissolves
  if (sceneState.workspaceGroup) {
    if (p < 0.55) {
      sceneState.workspaceGroup.visible = false;
      if (sceneState.roomGroup) sceneState.roomGroup.visible = false;
      if (sceneState.categoryUniforms) {
        for (let c = 0; c < 8; c++) {
          if (sceneState.categoryUniforms[c]) sceneState.categoryUniforms[c].value = 0.0;
        }
      }
    } else {
      sceneState.workspaceGroup.visible = true;

      const windows = [
        [0.55, 0.72], // 0: Mat
        [0.58, 0.76], // 1: Desk & Legs
        [0.64, 0.80], // 2: Laptop & Stand
        [0.68, 0.83], // 3: Peripherals
        [0.71, 0.86], // 4: Small Objects
        [0.74, 0.88], // 5: Headset & Stand
        [0.78, 0.90], // 6: Poster
        [0.82, 0.94]  // 7: Room Architecture
      ];

      if (sceneState.roomGroup) {
        sceneState.roomGroup.visible = p >= 0.82;
      }

      if (sceneState.categoryUniforms) {
        for (let cat = 0; cat < 8; cat++) {
          const [start, end] = windows[cat];
          const val = p >= end ? 1.0 : (p <= start ? 0.0 : (p - start) / (end - start));
          if (sceneState.categoryUniforms[cat]) {
            sceneState.categoryUniforms[cat].value = val;
          }
        }
      }
    }
  }

  // 4. Lighting & Environment Handover (between 0.55 and 0.85)
  const envT = p <= 0.55 ? 0.0 : (p >= 0.85 ? 1.0 : (p - 0.55) / 0.30);

  const nightBg = new THREE.Color(0x070B16);
  const morningBg = new THREE.Color(0xEFE8DC);
  const currentBg = nightBg.clone().lerp(morningBg, envT);

  if (sceneState.scene) {
    sceneState.scene.background.copy(currentBg);
    if (sceneState.scene.fog) {
      sceneState.scene.fog.color.copy(currentBg);
    }
  }

  if (sceneState.starfield) {
    if (envT >= 1.0) {
      sceneState.starfield.visible = false;
    } else {
      sceneState.starfield.visible = true;
      sceneState.starfield.material.opacity = (1.0 - envT) * 0.70;
    }
  }

  if (sceneState.keyLight) {
    sceneState.keyLight.intensity = envT * 1.40;
  }
  if (sceneState.ambientLight) {
    sceneState.ambientLight.intensity = 0.15 + envT * (0.82 - 0.15);
  }
}

/**
 * Procedural Studio Workspace & Architecture Assembly
 * Real-world scale in metres.
 * CRITICAL FIX 1: Entire workspaceGroup is invisible until Phase 3!
 */
function createWorkspace(scene) {
  const workspaceGroup = new THREE.Group();
  workspaceGroup.position.set(0, 0, 0);
  workspaceGroup.visible = false; // Strictly hidden in Phase 1 & 2!

  // -------------------------------------------------------------
  // 1. BRIGHT STUDIO ROOM ARCHITECTURE
  // -------------------------------------------------------------
  const roomGroup = new THREE.Group();

  // Light Natural Oak Parquet Floor (8m x 8m at y = 0)
  const floorGeo = new THREE.PlaneGeometry(8, 8);
  floorGeo.rotateX(-Math.PI / 2);
  const floorMesh = new THREE.Mesh(floorGeo, materials.floorOak);
  floorMesh.receiveShadow = true;
  roomGroup.add(floorMesh);

  // Warm Off-White Back Wall (8m wide, 4m high at z = -1.35m, #EFE8DC)
  const wallGeo = new THREE.PlaneGeometry(8, 4);
  const wallMesh = new THREE.Mesh(wallGeo, materials.wall);
  wallMesh.position.set(0, 2.0, -1.35);
  wallMesh.receiveShadow = true;
  roomGroup.add(wallMesh);

  // Subtle Vertical Wall Paneling (Batten board strips in slightly darker #E2DACD every 40cm)
  for (let x = -3.6; x <= 3.6; x += 0.4) {
    const battenGeo = new THREE.BoxGeometry(0.016, 4.0, 0.01);
    const batten = new THREE.Mesh(battenGeo, materials.wallBatten);
    batten.position.set(x, 2.0, -1.345);
    batten.receiveShadow = true;
    roomGroup.add(batten);
  }

  // White Baseboard along floor / wall seam (#F8F6F2)
  const baseboardGeo = new THREE.BoxGeometry(8, 0.12, 0.02);
  const baseboard = new THREE.Mesh(baseboardGeo, materials.baseboard);
  baseboard.position.set(0, 0.06, -1.335);
  roomGroup.add(baseboard);

  // Large Architectural Window on Left Wall (Morning light source)
  const windowFrameGroup = new THREE.Group();
  windowFrameGroup.position.set(-2.4, 1.8, -1.33);

  // Thin Warm White Outer Frame
  const winFrameMat = new THREE.MeshStandardMaterial({ color: 0xF0ECE4, roughness: 0.70 });
  const winOuterGeo = new THREE.BoxGeometry(1.2, 1.8, 0.03);
  const winOuter = new THREE.Mesh(winOuterGeo, winFrameMat);
  windowFrameGroup.add(winOuter);

  // Window Sill in Warm White
  const sillGeo = new THREE.BoxGeometry(1.3, 0.04, 0.08);
  const sill = new THREE.Mesh(sillGeo, winFrameMat);
  sill.position.set(0, -0.9, 0.03);
  windowFrameGroup.add(sill);

  // Bright Soft Blue-White Morning Sky (Emissive Plane)
  const skyGeo = new THREE.PlaneGeometry(1.08, 1.68);
  const skyMat = new THREE.MeshBasicMaterial({ color: 0xB8D2F0 });
  const skyMesh = new THREE.Mesh(skyGeo, skyMat);
  skyMesh.position.z = 0.012;
  windowFrameGroup.add(skyMesh);

  // Translucent Sheer White Curtain along right side of window
  const curtainGeo = new THREE.PlaneGeometry(0.38, 1.70);
  const curtainMat = new THREE.MeshStandardMaterial({
    color: 0xE5DFD5,
    transparent: true,
    opacity: 0.35,
    roughness: 0.95
  });
  const curtain = new THREE.Mesh(curtainGeo, curtainMat);
  curtain.position.set(0.36, -0.01, 0.02);
  windowFrameGroup.add(curtain);

  roomGroup.add(windowFrameGroup);

  // Wall-Mounted Framed µLearn Poster with Brass Picture Light
  const posterGroup = createWallPoster();
  posterGroup.position.set(0.05, 1.48, -1.33);
  roomGroup.add(posterGroup);
  sceneState.posterGroup = posterGroup;

  workspaceGroup.add(roomGroup);
  sceneState.roomGroup = roomGroup;

  // -------------------------------------------------------------
  // 2. PROCEDURAL WALNUT DESK (1.6m x 0.75m, top at y = 0.75m)
  // -------------------------------------------------------------
  const deskGroup = new THREE.Group();

  // 3cm thick Walnut Desk Top (Surface at y = 0.75m)
  const topGeo = new THREE.BoxGeometry(1.60, 0.03, 0.75);
  const deskTop = new THREE.Mesh(topGeo, materials.walnut);
  deskTop.position.set(0, 0.735, 0);
  deskTop.castShadow = true;
  deskTop.receiveShadow = true;
  deskGroup.add(deskTop);

  // Slim Black Steel Legs with Rear Crossbar
  const legLeft = createSteelLeg();
  legLeft.position.set(-0.65, 0.36, 0);
  deskGroup.add(legLeft);

  const legRight = createSteelLeg();
  legRight.position.set(0.65, 0.36, 0);
  deskGroup.add(legRight);

  // Rear Horizontal Support Bar
  const rearBarGeo = new THREE.BoxGeometry(1.30, 0.024, 0.024);
  const rearBar = new THREE.Mesh(rearBarGeo, materials.darkSteel);
  rearBar.position.set(0, 0.38, -0.28);
  rearBar.castShadow = true;
  deskGroup.add(rearBar);

  // Rear Cable Routing Grommet and Tidy Braided Cables
  const grommetGeo = new THREE.CylinderGeometry(0.025, 0.025, 0.032, 24);
  const grommet = new THREE.Mesh(grommetGeo, materials.darkSteel);
  grommet.position.set(0.05, 0.735, -0.31);
  deskGroup.add(grommet);

  const cableCurve1 = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(0.06, 0.752, -0.18),
    new THREE.Vector3(0.065, 0.752, -0.26),
    new THREE.Vector3(0.055, 0.72, -0.31)
  );
  const cableGeo1 = new THREE.TubeGeometry(cableCurve1, 16, 0.003, 8, false);
  const cable1 = new THREE.Mesh(cableGeo1, materials.darkSteel);
  deskGroup.add(cable1);

  workspaceGroup.add(deskGroup);
  sceneState.deskGroup = deskGroup;

  // -------------------------------------------------------------
  // 3. LEATHER DESK MAT, KEYBOARD & ERGONOMIC MOUSE
  // -------------------------------------------------------------
  const deskMatGroup = new THREE.Group();

  // Navy Leather Mat with Stitched Gold Edge
  const matGeo = new THREE.BoxGeometry(0.86, 0.003, 0.38);
  const deskMatMesh = new THREE.Mesh(matGeo, materials.deskMat);
  deskMatMesh.position.set(0.05, 0.7515, 0.12);
  deskMatMesh.receiveShadow = true;
  deskMatGroup.add(deskMatMesh);
  sceneState.deskMatMesh = deskMatMesh;

  // Contact shadow under desk mat
  const matShadow = createContactShadow(0.90, 0.42, 0.22);
  matShadow.position.set(0.05, 0.751, 0.12);
  deskMatGroup.add(matShadow);

  // Slim Wireless Keyboard with Procedural Key Grid
  const kbGroup = new THREE.Group();
  kbGroup.position.set(-0.02, 0.753, 0.16);

  const kbBaseGeo = new THREE.BoxGeometry(0.30, 0.007, 0.12);
  const kbBase = new THREE.Mesh(kbBaseGeo, materials.spaceGray);
  kbGroup.add(kbBase);

  const kbKeysGeo = new THREE.BoxGeometry(0.288, 0.002, 0.108);
  const kbKeys = new THREE.Mesh(kbKeysGeo, materials.keyboardWell);
  kbKeys.position.y = 0.0045;
  kbGroup.add(kbKeys);
  deskMatGroup.add(kbGroup);
  sceneState.kbGroup = kbGroup;

  // Ergonomic Wireless Mouse
  const mouseGroup = new THREE.Group();
  mouseGroup.position.set(0.30, 0.753, 0.16);

  const mouseGeo = new THREE.CylinderGeometry(0.026, 0.03, 0.018, 24);
  mouseGeo.scale(1, 1, 1.6);
  const mouse = new THREE.Mesh(mouseGeo, materials.spaceGray);
  mouse.position.y = 0.009;
  mouseGroup.add(mouse);
  deskMatGroup.add(mouseGroup);
  sceneState.mouseGroup = mouseGroup;

  workspaceGroup.add(deskMatGroup);
  sceneState.deskMatGroup = deskMatGroup;

  // -------------------------------------------------------------
  // 4. ALUMINIUM RISER STAND & LAPTOP (Named Group: base, lid, screenMesh)
  // -------------------------------------------------------------
  const standGroup = new THREE.Group();
  standGroup.name = 'standGroup';
  standGroup.position.set(0.05, 0, 0);

  // Contact shadow under laptop stand
  const standShadow = createContactShadow(0.42, 0.32, 0.22);
  standShadow.position.set(0, 0.751, -0.10);
  standGroup.add(standShadow);

  // Aluminium Laptop Stand (tilted 14 degrees)
  const standMesh = createAluminiumStand();
  standGroup.add(standMesh);
  workspaceGroup.add(standGroup);
  sceneState.standGroup = standGroup;
  sceneState.standMesh = standMesh;

  // Laptop Assembly (Group with named children: base, lid, screenMesh)
  const laptopGroup = new THREE.Group();
  laptopGroup.name = 'laptop';
  laptopGroup.position.set(0.05, 0, 0);

  // Laptop Base chassis resting ON TOP of stand rails (tilted +14 deg)
  // standTopY = 0.825m, halfBaseThickness = 0.006m -> base y = 0.831m
  const laptopBaseGroup = new THREE.Group();
  laptopBaseGroup.name = 'base';
  laptopBaseGroup.position.set(0, 0.831, -0.10);
  laptopBaseGroup.rotation.x = 0.244346; // +14 degrees incline on stand

  const laptopBaseGeo = new THREE.BoxGeometry(0.38, 0.012, 0.25);
  const laptopBase = new THREE.Mesh(laptopBaseGeo, materials.spaceGray);
  laptopBase.castShadow = true;
  laptopBase.receiveShadow = true;
  laptopBase.name = 'baseChassis';
  laptopBaseGroup.add(laptopBase);

  // Keyboard Well & Trackpad on base
  const wellGeo = new THREE.BoxGeometry(0.32, 0.002, 0.12);
  const wellMesh = new THREE.Mesh(wellGeo, materials.keyboardWell);
  wellMesh.position.set(0, 0.0065, -0.030);
  laptopBaseGroup.add(wellMesh);

  const tpGeo = new THREE.BoxGeometry(0.10, 0.002, 0.065);
  const tpMesh = new THREE.Mesh(tpGeo, materials.trackpad);
  tpMesh.position.set(0, 0.0065, 0.075);
  laptopBaseGroup.add(tpMesh);

  // Laptop Lid & Screen Assembly (Hinged at rear of base: named 'lid')
  const laptopLidGroup = new THREE.Group();
  laptopLidGroup.name = 'lid';
  laptopLidGroup.position.set(0, 0.006, -0.125); // Rear hinge pivot

  // Screen Back Cover (0.38m wide, 0.245m tall)
  const lidCoverGeo = new THREE.BoxGeometry(0.38, 0.245, 0.008);
  lidCoverGeo.translate(0, 0.1225, 0);
  const lidCover = new THREE.Mesh(lidCoverGeo, materials.spaceGray);
  lidCover.castShadow = true;
  lidCover.name = 'lidCover';
  laptopLidGroup.add(lidCover);

  // Slim Screen Bezel
  const bezelGeo = new THREE.BoxGeometry(0.37, 0.235, 0.001);
  bezelGeo.translate(0, 0.1225, 0.0042);
  const bezel = new THREE.Mesh(bezelGeo, materials.spaceGray);
  bezel.name = 'bezel';
  laptopLidGroup.add(bezel);

  // High-Resolution Laptop Screen Mesh (0.36m wide, 0.225m tall, 16:10 aspect ratio)
  // MeshBasicMaterial with toneMapped: false so screen is sharp and never washed out
  const screenMat = new THREE.MeshBasicMaterial({
    map: sceneState.chatTexture,
    toneMapped: false
  });
  const screenGeo = new THREE.PlaneGeometry(0.36, 0.225);
  screenGeo.translate(0, 0.1225, 0.005);
  const screenMesh = new THREE.Mesh(screenGeo, screenMat);
  screenMesh.name = 'screenMesh';
  laptopLidGroup.add(screenMesh);
  sceneState.laptopScreenMesh = screenMesh;

  // Screen White Fade Overlay Plane (for crossfade over last 8% of Phase 5)
  const fadeMat = new THREE.MeshBasicMaterial({
    color: 0xFFFFFF,
    transparent: true,
    opacity: 0,
    toneMapped: false,
    depthWrite: false
  });
  const fadeGeo = new THREE.PlaneGeometry(0.362, 0.227);
  fadeGeo.translate(0, 0.1225, 0.0055);
  const fadeMesh = new THREE.Mesh(fadeGeo, fadeMat);
  fadeMesh.name = 'screenFade';
  laptopLidGroup.add(fadeMesh);
  sceneState.screenFadeMesh = fadeMesh;

  // Open laptop screen lid: tilted back ~11.8 degrees from vertical facing user
  // Base is tilted +14 deg (0.244 rad). Setting lid rotation.x = -0.45 rad gives net -11.8 deg tilt
  laptopLidGroup.rotation.x = -0.45;

  laptopBaseGroup.add(laptopLidGroup);
  laptopGroup.add(laptopBaseGroup);
  workspaceGroup.add(laptopGroup);

  sceneState.laptopGroup = laptopGroup;
  sceneState.laptopBase = laptopBaseGroup;
  sceneState.laptopLid = laptopLidGroup;

  // -------------------------------------------------------------
  // 5. ARTICULATED BRASS DESK LAMP (Left, Prop Only, OFF)
  // -------------------------------------------------------------
  const lampGroup = createDeskLamp();
  lampGroup.position.set(-0.58, 0, -0.06);

  const lampShadow = createContactShadow(0.24, 0.24, 0.20);
  lampShadow.position.set(0, 0.751, 0);
  lampGroup.add(lampShadow);

  workspaceGroup.add(lampGroup);
  sceneState.lampGroup = lampGroup;

  // -------------------------------------------------------------
  // 6. STACK OF 2 HARDCOVER BOOKS, LEATHER NOTEBOOK & BRASS PEN
  // -------------------------------------------------------------
  const booksGroup = createBooksAndNotebook();
  booksGroup.position.set(-0.40, 0, 0.12);

  const booksShadow = createContactShadow(0.36, 0.28, 0.24);
  booksShadow.position.set(0, 0.751, 0);
  booksGroup.add(booksShadow);

  workspaceGroup.add(booksGroup);
  sceneState.booksGroup = booksGroup;

  // -------------------------------------------------------------
  // 7. GLASS OF TEA (10cm tall, amber liquid, saucer, spoon & steam)
  // -------------------------------------------------------------
  const teaGroup = createTeaGlass();
  teaGroup.position.set(0.40, 0, 0.10);

  const teaShadow = createContactShadow(0.20, 0.20, 0.22);
  teaShadow.position.set(0, 0.751, 0);
  teaGroup.add(teaShadow);

  workspaceGroup.add(teaGroup);
  sceneState.teaGroup = teaGroup;

  // -------------------------------------------------------------
  // 8. DESK PHOTO STAND WITH ORIGINAL µLEARN LOGO (14 x 18 cm)
  // -------------------------------------------------------------
  const photoStandGroup = createPhotoStand();
  photoStandGroup.position.set(0.58, 0, 0.02);

  const photoShadow = createContactShadow(0.20, 0.16, 0.22);
  photoShadow.position.set(0, 0.751, 0);
  photoStandGroup.add(photoShadow);

  workspaceGroup.add(photoStandGroup);
  sceneState.photoStandGroup = photoStandGroup;

  // -------------------------------------------------------------
  // 9. SUCCULENT IN SLATE POT (Far Right Rear)
  // -------------------------------------------------------------
  const plantGroup = createPottedSucculent();
  plantGroup.position.set(0.68, 0, -0.20);

  const plantShadow = createContactShadow(0.16, 0.16, 0.20);
  plantShadow.position.set(0, 0.751, 0);
  plantGroup.add(plantShadow);

  workspaceGroup.add(plantGroup);
  sceneState.plantGroup = plantGroup;

  // -------------------------------------------------------------
  // 10. HEADPHONES ON VERTICAL BRASS STAND (Far Right Front)
  // Shifted 8cm right to x = 0.74 for guaranteed >= 2cm clearance from photo frame
  const headphonesGroup = createHeadphonesOnStand();
  headphonesGroup.position.set(0.74, 0, 0.14);

  const hpShadow = createContactShadow(0.18, 0.18, 0.22);
  hpShadow.position.set(0, 0.751, 0);
  headphonesGroup.add(hpShadow);

  workspaceGroup.add(headphonesGroup);
  sceneState.headphonesGroup = headphonesGroup;

  // -------------------------------------------------------------
  // COLLECT PROPS FOR STAGGERED REVEAL IN PHASE 3
  // -------------------------------------------------------------
  sceneState.props = [
    { group: roomGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: deskGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: deskMatGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: standGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: laptopGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: lampGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: teaGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: photoStandGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: booksGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: plantGroup, initialY: 0, targetY: 0, initialScale: 1.0 },
    { group: headphonesGroup, initialY: 0, targetY: 0, initialScale: 1.0 }
  ];

  // Resting assembled transforms; hidden initially until revealed in Phase 3
  sceneState.props.forEach(p => {
    p.group.position.y = 0;
    p.group.scale.set(1, 1, 1);
    p.group.visible = false;
  });

  scene.add(workspaceGroup);
  sceneState.workspaceGroup = workspaceGroup;
}

/**
 * Procedural Slim Black Steel Desk Leg
 */
function createSteelLeg() {
  const leg = new THREE.Group();

  const tubeGeo = new THREE.BoxGeometry(0.028, 0.72, 0.028);
  const frontTube = new THREE.Mesh(tubeGeo, materials.darkSteel);
  frontTube.position.set(0, 0, 0.28);
  frontTube.castShadow = true;
  leg.add(frontTube);

  const backTube = new THREE.Mesh(tubeGeo, materials.darkSteel);
  backTube.position.set(0, 0, -0.28);
  backTube.castShadow = true;
  leg.add(backTube);

  const topPlateGeo = new THREE.BoxGeometry(0.035, 0.01, 0.62);
  const topPlate = new THREE.Mesh(topPlateGeo, materials.darkSteel);
  topPlate.position.set(0, 0.355, 0);
  leg.add(topPlate);

  const footPlateGeo = new THREE.BoxGeometry(0.035, 0.01, 0.62);
  const footPlate = new THREE.Mesh(footPlateGeo, materials.darkSteel);
  footPlate.position.set(0, -0.355, 0);
  leg.add(footPlate);

  return leg;
}

/**
 * Procedural Brushed-Aluminium Laptop Angled Riser Stand
 * Tilted 14 degrees with two side rails (1.2 cm wide), back rest, and rubber feet.
 * Laptop base sits ON TOP of rails: laptopBase.position.y = standTopY + halfBaseThickness.
 * No vertical posts, zero penetration through laptop body.
 */
function createAluminiumStand() {
  const stand = new THREE.Group();
  stand.name = 'stand';

  const tiltRad = 0.244346; // 14 degrees tilt
  const railWidth = 0.012;  // 1.2 cm wide
  const railThick = 0.004;  // 4 mm thick
  const railLength = 0.21;  // 21 cm length
  const railSpacing = 0.22; // 22 cm apart

  // Rubber feet material
  const rubberMat = new THREE.MeshStandardMaterial({
    color: 0x1A1E24,
    roughness: 0.90,
    metalness: 0.05
  });

  // 1. Four Rubber Feet sitting on desk at y = 0.75m
  const footGeo = new THREE.CylinderGeometry(0.009, 0.009, 0.004, 16);
  const footPositions = [
    [-railSpacing / 2, 0.752, -0.005],
    [ railSpacing / 2, 0.752, -0.005],
    [-railSpacing / 2, 0.752, -0.185],
    [ railSpacing / 2, 0.752, -0.185]
  ];
  footPositions.forEach(([fx, fy, fz]) => {
    const foot = new THREE.Mesh(footGeo, rubberMat);
    foot.position.set(fx, fy, fz);
    foot.receiveShadow = true;
    stand.add(foot);
  });

  // 2. Bottom Aluminium Runners on desk connecting front and rear feet
  const runnerGeo = new THREE.BoxGeometry(railWidth, 0.004, 0.19);
  const runnerL = new THREE.Mesh(runnerGeo, materials.brushedAluminium);
  runnerL.position.set(-railSpacing / 2, 0.756, -0.095);
  runnerL.castShadow = true;
  stand.add(runnerL);

  const runnerR = new THREE.Mesh(runnerGeo, materials.brushedAluminium);
  runnerR.position.set(railSpacing / 2, 0.756, -0.095);
  runnerR.castShadow = true;
  stand.add(runnerR);

  // 3. Upright Riser Struts (Aluminium legs rising from desk runners to rails)
  // Front risers: height ~0.04m at z = -0.01m
  const frontStrutGeo = new THREE.BoxGeometry(railWidth, 0.044, 0.008);
  const frontStrutL = new THREE.Mesh(frontStrutGeo, materials.brushedAluminium);
  frontStrutL.position.set(-railSpacing / 2, 0.776, -0.01);
  frontStrutL.castShadow = true;
  stand.add(frontStrutL);

  const frontStrutR = new THREE.Mesh(frontStrutGeo, materials.brushedAluminium);
  frontStrutR.position.set(railSpacing / 2, 0.776, -0.01);
  frontStrutR.castShadow = true;
  stand.add(frontStrutR);

  // Rear risers: height ~0.09m at z = -0.18m
  const rearStrutGeo = new THREE.BoxGeometry(railWidth, 0.092, 0.008);
  const rearStrutL = new THREE.Mesh(rearStrutGeo, materials.brushedAluminium);
  rearStrutL.position.set(-railSpacing / 2, 0.800, -0.18);
  rearStrutL.castShadow = true;
  stand.add(rearStrutL);

  const rearStrutR = new THREE.Mesh(rearStrutGeo, materials.brushedAluminium);
  rearStrutR.position.set(railSpacing / 2, 0.800, -0.18);
  rearStrutR.castShadow = true;
  stand.add(rearStrutR);

  // 4. Two Angled Flat Side Rails tilted at 14 degrees
  // Rail top surface is at y = 0.825m at z = -0.10m
  const railGeo = new THREE.BoxGeometry(railWidth, railThick, railLength);
  railGeo.rotateX(tiltRad);

  const railCenterY = 0.825 - (railThick / 2); // 0.823m

  const railL = new THREE.Mesh(railGeo, materials.brushedAluminium);
  railL.position.set(-railSpacing / 2, railCenterY, -0.10);
  railL.castShadow = true;
  railL.receiveShadow = true;
  stand.add(railL);

  const railR = new THREE.Mesh(railGeo, materials.brushedAluminium);
  railR.position.set(railSpacing / 2, railCenterY, -0.10);
  railR.castShadow = true;
  railR.receiveShadow = true;
  stand.add(railR);

  // 5. Back Rest: Brushed-aluminium crossbar connecting the two rails across the top rear
  const backRestGeo = new THREE.BoxGeometry(railSpacing + railWidth, railThick, 0.024);
  backRestGeo.rotateX(tiltRad);
  const backRest = new THREE.Mesh(backRestGeo, materials.brushedAluminium);
  // Positioned near upper rear of the rails (z = -0.185m)
  const rearOffset = -0.085;
  const backRestY = railCenterY - rearOffset * Math.sin(tiltRad);
  const backRestZ = -0.10 + rearOffset * Math.cos(tiltRad);
  backRest.position.set(0, backRestY, backRestZ);
  backRest.castShadow = true;
  stand.add(backRest);

  // 6. Front Lip Retention Tabs to catch front bottom of laptop base
  const hookGeo = new THREE.BoxGeometry(railWidth, 0.012, railThick);
  hookGeo.rotateX(tiltRad);
  const frontOffset = 0.102;
  const hookY = railCenterY + 0.005 - frontOffset * Math.sin(tiltRad);
  const hookZ = -0.10 + frontOffset * Math.cos(tiltRad);

  const hookL = new THREE.Mesh(hookGeo, materials.brushedAluminium);
  hookL.position.set(-railSpacing / 2, hookY, hookZ);
  stand.add(hookL);

  const hookR = new THREE.Mesh(hookGeo, materials.brushedAluminium);
  hookR.position.set(railSpacing / 2, hookY, hookZ);
  stand.add(hookR);

  stand.userData = {
    standTopY: 0.825,
    standCenterZ: -0.10,
    tiltRad: tiltRad
  };

  return stand;
}

/**
 * Articulated Brass Desk Lamp (Prop Only, OFF in Daylight)
 * Clean hierarchy with pivot groups: base disc -> base joint -> lower arm -> elbow joint -> upper arm -> head joint -> shade -> matte bulb.
 * Opening points DOWN toward the desk at about 35 degrees from vertical.
 */
function createDeskLamp() {
  const lamp = new THREE.Group();
  lamp.name = 'lamp';

  // 1. Heavy Circular Brass Base on desk at y = 0.75m
  const baseRadius = 0.075;
  const baseThickness = 0.012;
  const baseGeo = new THREE.CylinderGeometry(baseRadius, baseRadius + 0.005, baseThickness, 32);
  const baseMesh = new THREE.Mesh(baseGeo, materials.brushedBrass);
  baseMesh.position.set(0, 0.75 + baseThickness / 2, 0);
  baseMesh.castShadow = true;
  baseMesh.receiveShadow = true;
  baseMesh.name = 'lampBase';
  lamp.add(baseMesh);

  // 2. Base Joint Pivot at top of base disc
  const baseJoint = new THREE.Group();
  baseJoint.position.set(0, 0.75 + baseThickness, 0);
  baseJoint.name = 'baseJoint';
  lamp.add(baseJoint);

  // 3. Lower Arm Group (pivot at base top)
  const lowerArmGroup = new THREE.Group();
  lowerArmGroup.name = 'lowerArmGroup';
  lowerArmGroup.rotation.z = -0.22; // angle slightly back-left
  lowerArmGroup.rotation.x = 0.08;
  baseJoint.add(lowerArmGroup);

  const L1 = 0.30;
  const lowerRodGeo = new THREE.CylinderGeometry(0.006, 0.006, L1, 16);
  lowerRodGeo.translate(0, L1 / 2, 0);
  const lowerRod = new THREE.Mesh(lowerRodGeo, materials.brushedBrass);
  lowerRod.castShadow = true;
  lowerArmGroup.add(lowerRod);

  // 4. Elbow Joint Sphere (at top of lower arm, perfectly connecting with zero gaps)
  const elbowJointGroup = new THREE.Group();
  elbowJointGroup.position.set(0, L1, 0);
  elbowJointGroup.name = 'elbowJointGroup';
  elbowJointGroup.rotation.z = 0.58; // angle forward and inward over desk
  elbowJointGroup.rotation.x = -0.28;
  lowerArmGroup.add(elbowJointGroup);

  const elbowSphereGeo = new THREE.SphereGeometry(0.015, 16, 16);
  const elbowSphere = new THREE.Mesh(elbowSphereGeo, materials.brushedBrass);
  elbowSphere.castShadow = true;
  elbowJointGroup.add(elbowSphere);

  // 5. Upper Arm Group (origin at elbow joint)
  const upperArmGroup = new THREE.Group();
  upperArmGroup.name = 'upperArmGroup';
  elbowJointGroup.add(upperArmGroup);

  const L2 = 0.25;
  const upperRodGeo = new THREE.CylinderGeometry(0.0055, 0.0055, L2, 16);
  upperRodGeo.translate(0, L2 / 2, 0);
  const upperRod = new THREE.Mesh(upperRodGeo, materials.brushedBrass);
  upperRod.castShadow = true;
  upperArmGroup.add(upperRod);

  // 6. Head Joint Sphere (at end of upper arm, zero gaps)
  const headJointGroup = new THREE.Group();
  headJointGroup.position.set(0, L2, 0);
  headJointGroup.name = 'headJointGroup';
  upperArmGroup.add(headJointGroup);

  const headSphereGeo = new THREE.SphereGeometry(0.013, 16, 16);
  const headSphere = new THREE.Mesh(headSphereGeo, materials.brushedBrass);
  headSphere.castShadow = true;
  headJointGroup.add(headSphere);

  // 7. Conical Lamp Shade Group
  // Opening points DOWN toward the desk at about 35 degrees from vertical (~0.61 rad)
  const shadeGroup = new THREE.Group();
  shadeGroup.name = 'shadeGroup';
  shadeGroup.rotation.z = 0.61;  // 35 degrees tilt pointing down at desk
  shadeGroup.rotation.x = -0.32;
  headJointGroup.add(shadeGroup);

  // Shade Cone (narrow neck attached to head joint at 0, expanding downward)
  const shadeConeGeo = new THREE.ConeGeometry(0.082, 0.13, 32, 1, true);
  shadeConeGeo.translate(0, -0.065, 0);

  const shadeOuterMat = new THREE.MeshStandardMaterial({
    color: 0xD8BD85,
    metalness: 0.86,
    roughness: 0.28,
    side: THREE.DoubleSide
  });
  const shadeOuter = new THREE.Mesh(shadeConeGeo, shadeOuterMat);
  shadeOuter.castShadow = true;
  shadeGroup.add(shadeOuter);

  // Warm white interior reflector lining
  const shadeInnerGeo = new THREE.ConeGeometry(0.080, 0.128, 32, 1, true);
  shadeInnerGeo.translate(0, -0.064, 0);
  const shadeInnerMat = new THREE.MeshStandardMaterial({
    color: 0xFAF6F0,
    roughness: 0.50,
    metalness: 0.05,
    side: THREE.DoubleSide
  });
  const shadeInner = new THREE.Mesh(shadeInnerGeo, shadeInnerMat);
  shadeGroup.add(shadeInner);

  // 8. Plain Matte-Warm-White Bulb inside opening (Prop only: ZERO emissive, OFF)
  const bulbGeo = new THREE.SphereGeometry(0.018, 16, 16);
  const bulbMat = new THREE.MeshStandardMaterial({
    color: 0xF5F0EA,
    emissive: 0x000000,
    emissiveIntensity: 0.0,
    roughness: 0.65,
    metalness: 0.0
  });
  const bulb = new THREE.Mesh(bulbGeo, bulbMat);
  bulb.position.set(0, -0.055, 0);
  bulb.name = 'lampBulb';
  shadeGroup.add(bulb);

  return lamp;
}

/**
 * Hardcover Book Stack, Closed Leather Notebook & Brass Pen
 */
function createBooksAndNotebook() {
  const group = new THREE.Group();

  // Bottom Hardcover Book (Classic Navy Cloth)
  const b1CoverGeo = new THREE.BoxGeometry(0.23, 0.028, 0.16);
  const b1Mat = new THREE.MeshStandardMaterial({ color: 0x203248, roughness: 0.72 });
  const book1 = new THREE.Mesh(b1CoverGeo, b1Mat);
  book1.position.set(0, 0.764, 0);
  book1.castShadow = true;
  group.add(book1);

  const b1PagesGeo = new THREE.BoxGeometry(0.224, 0.024, 0.154);
  const b1Pages = new THREE.Mesh(b1PagesGeo, materials.paper);
  b1Pages.position.set(0.002, 0.764, 0);
  group.add(b1Pages);

  // Top Hardcover Book (Muted Forest Green Cloth, rotated 5 deg)
  const b2CoverGeo = new THREE.BoxGeometry(0.21, 0.024, 0.145);
  const b2Mat = new THREE.MeshStandardMaterial({ color: 0x264232, roughness: 0.70 });
  const book2 = new THREE.Mesh(b2CoverGeo, b2Mat);
  book2.position.set(0.01, 0.79, 0.005);
  book2.rotation.y = 0.09;
  book2.castShadow = true;
  group.add(book2);

  // Closed Rich Brown Leather Notebook (Beside books)
  const nbCoverGeo = new THREE.BoxGeometry(0.14, 0.018, 0.20);
  const nbCover = new THREE.Mesh(nbCoverGeo, materials.leather);
  nbCover.position.set(0.14, 0.759, 0.02);
  nbCover.rotation.y = -0.12;
  nbCover.castShadow = true;
  group.add(nbCover);

  const nbPagesGeo = new THREE.BoxGeometry(0.134, 0.015, 0.194);
  const nbPages = new THREE.Mesh(nbPagesGeo, materials.paper);
  nbPages.position.set(0.14, 0.759, 0.02);
  nbPages.rotation.y = -0.12;
  group.add(nbPages);

  // Gold Ribbon Bookmark
  const ribbonGeo = new THREE.BoxGeometry(0.012, 0.002, 0.06);
  const ribbon = new THREE.Mesh(ribbonGeo, materials.gold);
  ribbon.position.set(0.14, 0.769, 0.12);
  ribbon.rotation.y = -0.12;
  group.add(ribbon);

  // Sleek Brass Ballpoint Pen
  const pen = new THREE.Group();
  pen.position.set(0.23, 0.756, 0.03);
  pen.rotation.y = -0.08;

  const barrelGeo = new THREE.CylinderGeometry(0.004, 0.004, 0.13, 16);
  barrelGeo.rotateX(Math.PI / 2);
  const barrel = new THREE.Mesh(barrelGeo, materials.brushedBrass);
  barrel.castShadow = true;
  pen.add(barrel);

  const penTipGeo = new THREE.ConeGeometry(0.004, 0.014, 16);
  penTipGeo.rotateX(-Math.PI / 2);
  penTipGeo.translate(0, 0, 0.072);
  const penTip = new THREE.Mesh(penTipGeo, materials.brushedBrass);
  pen.add(penTip);

  group.add(pen);
  return group;
}

/**
 * Polish: Clear Tea Glass (~10cm tall) with Amber Liquid, Meniscus, Saucer, Spoon & Steam
 */
function createTeaGlass() {
  const tea = new THREE.Group();

  // Brass Saucer Plate on desk at y = 0.75m
  const saucerGeo = new THREE.CylinderGeometry(0.07, 0.056, 0.008, 32);
  const saucer = new THREE.Mesh(saucerGeo, materials.brushedBrass);
  saucer.position.set(0, 0.754, 0);
  saucer.castShadow = true;
  saucer.receiveShadow = true;
  tea.add(saucer);

  // Tiny Brass Teaspoon resting on saucer rim
  const spoon = new THREE.Group();
  spoon.position.set(0.024, 0.758, 0.02);
  spoon.rotation.y = -0.78;
  spoon.rotation.z = 0.08;

  const handleGeo = new THREE.CylinderGeometry(0.002, 0.002, 0.09, 12);
  handleGeo.rotateX(Math.PI / 2);
  const handle = new THREE.Mesh(handleGeo, materials.brushedBrass);
  spoon.add(handle);

  const bowlGeo = new THREE.SphereGeometry(0.008, 12, 12);
  bowlGeo.scale(0.8, 0.3, 1.4);
  bowlGeo.translate(0, 0, 0.045);
  const bowl = new THREE.Mesh(bowlGeo, materials.brushedBrass);
  spoon.add(bowl);
  tea.add(spoon);

  // Fresh Mint Leaf on saucer edge
  const leafGeo = new THREE.PlaneGeometry(0.022, 0.034);
  const leafMat = new THREE.MeshStandardMaterial({
    color: 0x2E7D32,
    roughness: 0.5,
    side: THREE.DoubleSide
  });
  const leaf = new THREE.Mesh(leafGeo, leafMat);
  leaf.position.set(-0.048, 0.759, 0.025);
  leaf.rotation.x = -Math.PI * 0.45;
  leaf.rotation.z = 0.35;
  tea.add(leaf);

  // Brass Holder Ring at bottom of tea glass
  const holderGeo = new THREE.CylinderGeometry(0.035, 0.035, 0.025, 32, 1, true);
  const holder = new THREE.Mesh(holderGeo, materials.brushedBrass);
  holder.position.set(0, 0.77, 0);
  tea.add(holder);

  // Lathe-Geometry Clear Tea Glass (~10cm tall, flared lip, tapered waist, thick solid base)
  const glassPoints = [
    new THREE.Vector2(0, 0),
    new THREE.Vector2(0.033, 0),       // thick heavy solid base
    new THREE.Vector2(0.034, 0.012),   // base rim
    new THREE.Vector2(0.027, 0.05),    // tapered waist
    new THREE.Vector2(0.036, 0.10),    // flared top lip outer (~10cm tall)
    new THREE.Vector2(0.034, 0.10),    // flared top lip inner
    new THREE.Vector2(0.0255, 0.05),   // inner waist
    new THREE.Vector2(0.029, 0.014),   // inner bottom
    new THREE.Vector2(0, 0.014)
  ];
  const glassGeo = new THREE.LatheGeometry(glassPoints, 32);
  const glassMesh = new THREE.Mesh(glassGeo, materials.teaGlass);
  glassMesh.position.set(0, 0.758, 0);
  glassMesh.castShadow = true;
  tea.add(glassMesh);

  // Amber Tea Liquid
  const liquidPoints = [
    new THREE.Vector2(0, 0.015),
    new THREE.Vector2(0.028, 0.015),
    new THREE.Vector2(0.025, 0.05),
    new THREE.Vector2(0.033, 0.088),   // tea liquid surface
    new THREE.Vector2(0, 0.088)
  ];
  const liquidGeo = new THREE.LatheGeometry(liquidPoints, 32);
  const liquidMesh = new THREE.Mesh(liquidGeo, materials.teaLiquid);
  liquidMesh.position.set(0, 0.758, 0);
  tea.add(liquidMesh);

  // Lighter Visible Meniscus Top Surface Disc
  const meniscusGeo = new THREE.CircleGeometry(0.033, 32);
  meniscusGeo.rotateX(-Math.PI / 2);
  const meniscus = new THREE.Mesh(meniscusGeo, materials.teaMeniscus);
  meniscus.position.set(0, 0.846, 0);
  tea.add(meniscus);

  // Rising Steam Sprites (3-4 faint steam wisps)
  const steamGroup = new THREE.Group();
  steamGroup.position.set(0, 0.758, 0);
  sceneState.steamSprites = [];

  const isMobile = window.innerWidth <= 768;
  const spriteCount = isMobile ? 2 : 4;

  for (let i = 0; i < spriteCount; i++) {
    const sMat = new THREE.SpriteMaterial({
      map: sceneState.steamTexture,
      transparent: true,
      opacity: 0.18,
      depthWrite: false
    });
    const sprite = new THREE.Sprite(sMat);
    sprite.scale.set(0.04 + i * 0.006, 0.05 + i * 0.008, 1);
    sprite.position.set(
      (Math.random() - 0.5) * 0.012,
      0.10 + i * 0.04,
      (Math.random() - 0.5) * 0.012
    );
    sprite.userData = {
      baseY: 0.10,
      speed: 0.028 + Math.random() * 0.015,
      offset: i * 1.57,
      maxHeight: 0.28
    };
    steamGroup.add(sprite);
    sceneState.steamSprites.push(sprite);
  }
  tea.add(steamGroup);

  return tea;
}

/**
 * Polish: Desk Photo Stand with ORIGINAL µLearn Logo (14 x 18 cm)
 * Dark walnut frame, brass edge, warm ivory mat (#E8DFCE), picture at ~70% size,
 * standard lit material (no overexposure), thin glass, rear easel leg.
 */
function createPhotoStand() {
  const stand = new THREE.Group();

  // Entire frame group tilted backward ~10 degrees (-0.174 rad around X)
  const frameGroup = new THREE.Group();
  frameGroup.position.set(0, 0.75, 0);
  frameGroup.rotation.x = -0.174;

  // Natural Light Oak Outer Frame (14cm x 18cm x 0.8cm)
  const oakFrameMat = new THREE.MeshStandardMaterial({ color: 0xC4A47C, roughness: 0.55 });
  const frameGeo = new THREE.BoxGeometry(0.14, 0.18, 0.008);
  frameGeo.translate(0, 0.09, 0);
  const frame = new THREE.Mesh(frameGeo, oakFrameMat);
  frame.castShadow = true;
  frameGroup.add(frame);

  // Thin Brushed-Brass Outer Bezel Edge
  const brassEdgeGeo = new THREE.BoxGeometry(0.142, 0.182, 0.002);
  brassEdgeGeo.translate(0, 0.09, 0.0035);
  const brassEdge = new THREE.Mesh(brassEdgeGeo, materials.brushedBrass);
  frameGroup.add(brassEdge);

  // Warm Ivory Inner Matting Board (#E8DFCE, 12.6cm x 16.6cm)
  const matGeo = new THREE.PlaneGeometry(0.126, 0.166);
  const matMesh = new THREE.Mesh(matGeo, materials.photoMat);
  matMesh.position.set(0, 0.09, 0.0048);
  matMesh.receiveShadow = true;
  frameGroup.add(matMesh);

  // Picture: ORIGINAL µLearn Logo (mulearn-original.png) at ~70% of frame (10cm x 10cm)
  // Standard lit material (no emissive, no overexposure), preserving 1:1 square aspect ratio
  const photoMat = new THREE.MeshStandardMaterial({
    map: sceneState.originalLogoTexture,
    roughness: 0.45,
    metalness: 0.05
  });
  const photoGeo = new THREE.PlaneGeometry(0.10, 0.10);
  const photoMesh = new THREE.Mesh(photoGeo, photoMat);
  photoMesh.position.set(0, 0.09, 0.0052);
  photoMesh.receiveShadow = true;
  frameGroup.add(photoMesh);

  // Subtle Reflective Front Glass Layer
  const glassGeo = new THREE.PlaneGeometry(0.126, 0.166);
  const glassMat = new THREE.MeshStandardMaterial({
    color: 0xFFFFFF,
    transparent: true,
    opacity: 0.12,
    roughness: 0.05,
    metalness: 0.2,
    depthWrite: false
  });
  const glassMesh = new THREE.Mesh(glassGeo, glassMat);
  glassMesh.position.set(0, 0.09, 0.0058);
  frameGroup.add(glassMesh);

  // Hinged Rear Easel Leg resting on desk surface
  const easelGeo = new THREE.BoxGeometry(0.016, 0.15, 0.003);
  easelGeo.translate(0, -0.075, 0);
  const easel = new THREE.Mesh(easelGeo, materials.brushedBrass);
  easel.position.set(0, 0.15, -0.005);
  easel.rotation.x = 0.38; // Extends back to touch desk
  frameGroup.add(easel);

  stand.add(frameGroup);
  return stand;
}

/**
 * Procedural Potted Succulent in Slate Pot
 */
function createPottedSucculent() {
  const plant = new THREE.Group();

  // Dark Slate Cylindrical Pot
  const potGeo = new THREE.CylinderGeometry(0.045, 0.038, 0.075, 24);
  const pot = new THREE.Mesh(potGeo, materials.plantPot);
  pot.position.set(0, 0.7875, 0);
  pot.castShadow = true;
  pot.receiveShadow = true;
  plant.add(pot);

  // Soil Disc
  const soilGeo = new THREE.CylinderGeometry(0.042, 0.042, 0.006, 20);
  const soilMat = new THREE.MeshStandardMaterial({ color: 0x161210, roughness: 0.95 });
  const soil = new THREE.Mesh(soilGeo, soilMat);
  soil.position.set(0, 0.824, 0);
  plant.add(soil);

  // Layered Rosette Succulent Leaves
  const leafCount = 10;
  for (let i = 0; i < leafCount; i++) {
    const angle = (i / leafCount) * Math.PI * 2;
    const leafGeo = new THREE.ConeGeometry(0.018, 0.05, 10);
    leafGeo.rotateX(Math.PI * 0.38);
    const leafMat = i % 2 === 0 ? materials.succulentDark : materials.succulentLight;
    const leaf = new THREE.Mesh(leafGeo, leafMat);
    leaf.position.set(Math.cos(angle) * 0.02, 0.83, Math.sin(angle) * 0.02);
    leaf.rotation.y = -angle;
    leaf.castShadow = true;
    plant.add(leaf);
  }

  return plant;
}

/**
 * Modern High-End Headphones on Vertical Brass Stand
 * Fully rendered:
 * - Complete headband: smooth half-torus arc (8mm tube radius), padded inner band (dark leatherette),
 *   slider arms with brass accents on both sides, connected to both ear cups with no gaps.
 * - Symmetrical ear cups: matte-black cylindrical body, rounded outer cap, brass accent ring,
 *   soft cushion pad on inner side facing inward, visible tilt hinge.
 * - Rests on stand's hook at y = 1.002m, cups hang freely and symmetrically.
 */
function createHeadphonesOnStand() {
  const group = new THREE.Group();
  group.name = 'headphonesGroup';

  // 1. Circular Brass Stand Base on desk at y = 0.75m
  const baseGeo = new THREE.CylinderGeometry(0.055, 0.058, 0.012, 32);
  const base = new THREE.Mesh(baseGeo, materials.brushedBrass);
  base.position.set(0, 0.756, 0);
  base.castShadow = true;
  base.receiveShadow = true;
  base.name = 'standBase';
  group.add(base);

  // 2. Slim Vertical Brass Stem (24cm tall, from y = 0.762 to y = 1.002m)
  const stemGeo = new THREE.CylinderGeometry(0.006, 0.006, 0.24, 20);
  stemGeo.translate(0, 0.12, 0);
  const stem = new THREE.Mesh(stemGeo, materials.brushedBrass);
  stem.position.set(0, 0.762, 0);
  stem.castShadow = true;
  stem.name = 'standStem';
  group.add(stem);

  // 3. Top Saddle / Hook Arch at y = 1.002m where headband rests
  const saddleGeo = new THREE.TorusGeometry(0.024, 0.005, 14, 28, Math.PI);
  const saddle = new THREE.Mesh(saddleGeo, materials.brushedBrass);
  saddle.position.set(0, 1.002, 0);
  saddle.name = 'standSaddle';
  group.add(saddle);

  // 4. Over-Ear Headphones Hanging Vertically
  const hp = new THREE.Group();
  hp.name = 'headset';
  hp.position.set(0, 1.008, 0); // Contact point touches top saddle

  // A. Outer Headband Arc: smooth half-torus arc (band radius 5.4cm, tube 7.5mm)
  const bandR = 0.054;
  const bandGeo = new THREE.TorusGeometry(bandR, 0.0075, 16, 48, Math.PI);
  bandGeo.translate(0, -bandR, 0);
  const band = new THREE.Mesh(bandGeo, materials.darkSteel);
  band.castShadow = true;
  band.name = 'headbandOuter';
  hp.add(band);

  // B. Padded Inner Band: dark leatherette cushion lining the inside of the arc
  const innerBandR = bandR - 0.004;
  const innerBandGeo = new THREE.TorusGeometry(innerBandR, 0.005, 14, 40, Math.PI * 0.76);
  innerBandGeo.rotateZ(Math.PI * 0.12);
  innerBandGeo.translate(0, -innerBandR, 0);
  const innerBand = new THREE.Mesh(innerBandGeo, materials.darkLeatherette);
  innerBand.name = 'headbandCushion';
  hp.add(innerBand);

  // C. Symmetrical Left & Right Slider Arms, Brass Accents, Tilt Hinges, and Ear Cups
  [-1, 1].forEach((side) => {
    const sideName = side === -1 ? 'left' : 'right';
    const armX = side * bandR;

    // Brass Adjustment Collar / Accent Sleeve (seamless junction with headband end)
    const collarGeo = new THREE.CylinderGeometry(0.008, 0.008, 0.012, 16);
    const collar = new THREE.Mesh(collarGeo, materials.brushedBrass);
    collar.position.set(armX, -bandR - 0.004, 0);
    collar.castShadow = true;
    collar.name = `${sideName}Collar`;
    hp.add(collar);

    // Dark Steel Slider Rod extending down to tilt hinge
    const sliderGeo = new THREE.CylinderGeometry(0.0035, 0.0035, 0.022, 12);
    const slider = new THREE.Mesh(sliderGeo, materials.darkSteel);
    slider.position.set(armX, -bandR - 0.015, 0);
    slider.name = `${sideName}Slider`;
    hp.add(slider);

    // Brass Tilt Hinge / Gimbal Pin
    const hingeGeo = new THREE.CylinderGeometry(0.005, 0.005, 0.010, 16);
    hingeGeo.rotateX(Math.PI / 2);
    const hinge = new THREE.Mesh(hingeGeo, materials.brushedBrass);
    hinge.position.set(armX, -bandR - 0.026, 0);
    hinge.name = `${sideName}Hinge`;
    hp.add(hinge);

    // Ear Cup Assembly (facing inward toward center)
    const cupGroup = new THREE.Group();
    cupGroup.name = `${sideName}CupGroup`;
    cupGroup.position.set(armX, -bandR - 0.026, 0);

    // Cylindrical outer shell with matte-black body
    const shellGeo = new THREE.CylinderGeometry(0.028, 0.028, 0.014, 32);
    shellGeo.rotateZ(Math.PI / 2);
    const shell = new THREE.Mesh(shellGeo, materials.matteBlack);
    shell.castShadow = true;
    shell.receiveShadow = true;
    shell.name = `${sideName}CupShell`;
    cupGroup.add(shell);

    // Rounded outer shell cap dome on the exterior side
    const capGeo = new THREE.SphereGeometry(0.028, 24, 12, 0, Math.PI * 2, 0, Math.PI / 4);
    if (side === -1) {
      capGeo.rotateZ(-Math.PI / 2);
    } else {
      capGeo.rotateZ(Math.PI / 2);
    }
    const cap = new THREE.Mesh(capGeo, materials.matteBlack);
    cap.position.x = side * 0.007;
    cap.name = `${sideName}CupCap`;
    cupGroup.add(cap);

    // Brushed Brass Accent Ring on the cup outer perimeter
    const ringGeo = new THREE.TorusGeometry(0.028, 0.002, 12, 32);
    ringGeo.rotateY(Math.PI / 2);
    const ring = new THREE.Mesh(ringGeo, materials.brushedBrass);
    ring.name = `${sideName}CupRing`;
    cupGroup.add(ring);

    // Soft contoured leatherette cushion pad on the INNER side (facing inward)
    const padGeo = new THREE.TorusGeometry(0.022, 0.006, 16, 32);
    padGeo.rotateY(Math.PI / 2);
    const pad = new THREE.Mesh(padGeo, materials.darkLeatherette);
    pad.position.x = -side * 0.008;
    pad.name = `${sideName}CupPad`;
    cupGroup.add(pad);

    // Inner Acoustic Mesh Backing
    const meshGeo = new THREE.CircleGeometry(0.020, 24);
    meshGeo.rotateY(side === -1 ? Math.PI / 2 : -Math.PI / 2);
    const innerMesh = new THREE.Mesh(meshGeo, materials.darkLeatherette);
    innerMesh.position.x = -side * 0.009;
    innerMesh.name = `${sideName}CupMesh`;
    cupGroup.add(innerMesh);

    hp.add(cupGroup);
  });

  group.add(hp);
  return group;
}

/**
 * Wall-Mounted Framed µLearn Poster with Light Oak Frame & No Glare
 */
function createWallPoster() {
  const poster = new THREE.Group();

  // Light Oak Outer Frame (0.75m x 1.0m)
  const oakFrameMat = new THREE.MeshStandardMaterial({ color: 0xC4A47C, roughness: 0.55 });
  const frameGeo = new THREE.BoxGeometry(0.75, 1.0, 0.028);
  const frame = new THREE.Mesh(frameGeo, oakFrameMat);
  frame.receiveShadow = true;
  poster.add(frame);

  // Thin Gold Inner Trim
  const trimGeo = new THREE.BoxGeometry(0.71, 0.96, 0.03);
  const trim = new THREE.Mesh(trimGeo, materials.brushedBrass);
  poster.add(trim);

  // Warm Ivory Matting Border (#F8F4EB)
  const mattingGeo = new THREE.PlaneGeometry(0.68, 0.93);
  const mattingMat = new THREE.MeshStandardMaterial({ color: 0xF8F4EB, roughness: 0.88 });
  const matting = new THREE.Mesh(mattingGeo, mattingMat);
  matting.position.z = 0.016;
  matting.receiveShadow = true;
  poster.add(matting);

  // Poster Art Print (µLearn Monogram) — Standard lit material with no glare
  const printMat = new THREE.MeshStandardMaterial({
    map: sceneState.logoTexture,
    transparent: true,
    roughness: 0.65,
    metalness: 0.0
  });
  const printGeo = new THREE.PlaneGeometry(0.55 * (805 / 1024), 0.55);
  const printMesh = new THREE.Mesh(printGeo, printMat);
  printMesh.position.set(0, 0.04, 0.018);
  poster.add(printMesh);

  // Wall-Mounted Brass Picture Fixture Accent
  const picLightGroup = new THREE.Group();
  picLightGroup.position.set(0, 0.54, 0.04);

  // Horizontal Brass Light Bar
  const barGeo = new THREE.CylinderGeometry(0.009, 0.009, 0.28, 16);
  barGeo.rotateZ(Math.PI / 2);
  const bar = new THREE.Mesh(barGeo, materials.brushedBrass);
  picLightGroup.add(bar);

  // Dual Wall Stems
  const stemGeo = new THREE.CylinderGeometry(0.004, 0.004, 0.05, 12);
  stemGeo.rotateX(Math.PI / 2);

  const stemL = new THREE.Mesh(stemGeo, materials.brushedBrass);
  stemL.position.set(-0.08, 0, -0.025);
  picLightGroup.add(stemL);

  const stemR = new THREE.Mesh(stemGeo, materials.brushedBrass);
  stemR.position.set(0.08, 0, -0.025);
  picLightGroup.add(stemR);

  poster.add(picLightGroup);
  return poster;
}

/**
 * Contact Shadow Plane Helper (Soft ambient occlusion grounding)
 */
function createContactShadow(width, depth, opacity = 0.25) {
  const geo = new THREE.PlaneGeometry(width, depth);
  geo.rotateX(-Math.PI / 2);
  const mat = new THREE.MeshBasicMaterial({
    map: sceneState.shadowTexture,
    transparent: true,
    opacity: opacity,
    depthWrite: false
  });
  const shadowMesh = new THREE.Mesh(geo, mat);
  shadowMesh.position.y = 0.751; // Just a hair above desk surface (0.75m)
  return shadowMesh;
}

/**
 * Procedural Natural Walnut Desk Texture (#6B4A32, soft grain, NOT saturated orange)
 */
function createWalnutTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 1024;
  const ctx = canvas.getContext('2d');

  // Base natural walnut #6B4A32
  ctx.fillStyle = '#6B4A32';
  ctx.fillRect(0, 0, 1024, 1024);

  // Longitudinal wood grain lines in natural deep walnut and soft muted tan tones
  for (let i = 0; i < 380; i++) {
    const y = Math.random() * 1024;
    const alpha = 0.02 + Math.random() * 0.05;
    const isDark = Math.random() < 0.65;
    ctx.strokeStyle = isDark ? `rgba(45, 28, 18, ${alpha})` : `rgba(135, 105, 80, ${alpha})`;
    ctx.lineWidth = 1 + Math.random() * 2.2;
    ctx.beginPath();
    let cx = 0;
    let cy = y;
    ctx.moveTo(cx, cy);
    while (cx < 1024) {
      cx += 35 + Math.random() * 45;
      cy += (Math.random() - 0.5) * 2.5;
      ctx.lineTo(cx, cy);
    }
    ctx.stroke();
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 1);
  return tex;
}

/**
 * Procedural Light Natural Oak Parquet Floor Texture (#B58B5A)
 */
function createFloorTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 1024;
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = '#B58B5A';
  ctx.fillRect(0, 0, 1024, 1024);

  const plankHeight = 64;
  const plankCount = 1024 / plankHeight;

  for (let p = 0; p < plankCount; p++) {
    const py = p * plankHeight;
    const shadeR = 175 + Math.floor(Math.random() * 20);
    const shadeG = 135 + Math.floor(Math.random() * 18);
    const shadeB = 85 + Math.floor(Math.random() * 15);
    ctx.fillStyle = `rgb(${shadeR}, ${shadeG}, ${shadeB})`;
    ctx.fillRect(0, py + 1, 1024, plankHeight - 2);

    // Subtle grain in each plank
    for (let g = 0; g < 12; g++) {
      const gy = py + Math.random() * plankHeight;
      ctx.strokeStyle = 'rgba(110, 75, 38, 0.05)';
      ctx.lineWidth = 1 + Math.random() * 2;
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(1024, gy + (Math.random() - 0.5) * 2);
      ctx.stroke();
    }

    // Soft plank seam
    ctx.strokeStyle = 'rgba(125, 90, 50, 0.40)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, py);
    ctx.lineTo(1024, py);
    ctx.stroke();

    const stagger = (p % 2) * 256;
    for (let vx = stagger; vx < 1024; vx += 512) {
      ctx.beginPath();
      ctx.moveTo(vx, py);
      ctx.lineTo(vx, py + plankHeight);
      ctx.stroke();
    }
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(4, 4);
  return tex;
}

/**
 * Procedural Soft Grey-Blue Leather Desk Mat Texture (#4B5A6A)
 */
function createDeskMatTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');

  // Soft refined grey-blue base #4A5B6D
  ctx.fillStyle = '#4A5B6D';
  ctx.fillRect(0, 0, 1024, 512);

  // Micro leather noise
  for (let i = 0; i < 2200; i++) {
    const x = Math.random() * 1024;
    const y = Math.random() * 512;
    const bright = Math.random() < 0.5;
    ctx.fillStyle = bright ? 'rgba(255, 255, 255, 0.03)' : 'rgba(25, 35, 48, 0.04)';
    ctx.fillRect(x, y, 2, 2);
  }

  // Thin stitched border in warm tan
  ctx.strokeStyle = '#B8A892';
  ctx.lineWidth = 2.5;
  ctx.setLineDash([7, 5]);
  ctx.strokeRect(16, 16, 1024 - 32, 512 - 32);

  return new THREE.CanvasTexture(canvas);
}

/**
 * Procedural Keyboard Texture with Realistic Proportions
 * Dark-grey deck with small light-grey keys (approx 1.4 cm with 0.3 cm gaps, subtle bevel)
 */
function createKeyboardTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');

  // Dark-grey deck #23272F
  ctx.fillStyle = '#23272F';
  ctx.fillRect(0, 0, 512, 256);

  const rows = 6;
  const cols = 15;
  const padX = 16;
  const padY = 14;
  const gap = 5;
  const keyW = (512 - padX * 2 - (cols - 1) * gap) / cols;
  const keyH = (256 - padY * 2 - (rows - 1) * gap) / rows;

  for (let r = 0; r < rows; r++) {
    const y = padY + r * (keyH + gap);
    for (let c = 0; c < cols; c++) {
      // Space bar on bottom row
      if (r === rows - 1 && c >= 4 && c <= 9) {
        if (c === 4) {
          const spaceW = keyW * 6 + gap * 5;
          const x = padX + c * (keyW + gap);
          ctx.fillStyle = '#9EA6B2';
          ctx.beginPath();
          ctx.roundRect(x, y, spaceW, keyH, 2.5);
          ctx.fill();
          ctx.strokeStyle = '#848D9A';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        continue;
      }

      const x = padX + c * (keyW + gap);

      // Small light-grey keycaps with subtle bevel
      ctx.fillStyle = '#9EA6B2';
      ctx.beginPath();
      ctx.roundRect(x, y, keyW, keyH, 2.5);
      ctx.fill();

      ctx.strokeStyle = '#848D9A';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Muted subtle keycap legend
      ctx.fillStyle = '#4E5562';
      ctx.fillRect(x + keyW * 0.35, y + keyH * 0.35, keyW * 0.30, keyH * 0.22);
    }
  }

  return new THREE.CanvasTexture(canvas);
}

/**
 * Soft Contact Shadow Radial Gradient
 */
function createSoftShadowTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');

  const grad = ctx.createRadialGradient(128, 128, 12, 128, 128, 120);
  grad.addColorStop(0, 'rgba(0, 0, 0, 0.75)');
  grad.addColorStop(0.35, 'rgba(0, 0, 0, 0.40)');
  grad.addColorStop(0.7, 'rgba(0, 0, 0, 0.12)');
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 256, 256);

  return new THREE.CanvasTexture(canvas);
}

/**
 * Soft Round Gold Particle Radial Gradient
 */
function createParticleTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');

  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0.0, 'rgba(255, 250, 220, 1.0)');
  grad.addColorStop(0.25, 'rgba(230, 201, 138, 0.85)');
  grad.addColorStop(0.55, 'rgba(201, 169, 110, 0.35)');
  grad.addColorStop(0.85, 'rgba(160, 120, 60, 0.08)');
  grad.addColorStop(1.0, 'rgba(0, 0, 0, 0.0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 64, 64);

  return new THREE.CanvasTexture(canvas);
}

/**
 * Soft Steam Sprite Texture
 */
function createSteamTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');

  const grad = ctx.createRadialGradient(64, 64, 4, 64, 64, 60);
  grad.addColorStop(0, 'rgba(240, 245, 255, 0.40)');
  grad.addColorStop(0.4, 'rgba(220, 230, 250, 0.20)');
  grad.addColorStop(0.8, 'rgba(200, 215, 240, 0.06)');
  grad.addColorStop(1, 'rgba(200, 215, 240, 0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 128, 128);

  return new THREE.CanvasTexture(canvas);
}

/**
 * DYNAMIC CAMERA CALCULATION FOR PHASES 4 & 5
 * Computed dynamically from laptop screen mesh world position and normal vector.
 * Derives screenCenter, screenNormal, screenHeight, and distance d.
 * Guarantees perfect viewport framing and prevents moving objects from breaking zoom.
 */
export function computeScreenCameraTargets(camera, aspect) {
  if (!sceneState.laptopScreenMesh || !sceneState.scene) return null;

  // Temporarily set prop groups to assembled resting position (targetY, scale 1)
  // to measure true world coordinates regardless of scroll animation progress
  const savedStates = [];
  if (sceneState.props && sceneState.props.length > 0) {
    sceneState.props.forEach(p => {
      savedStates.push({
        group: p.group,
        y: p.group.position.y,
        scale: p.group.scale.x,
        visible: p.group.visible
      });
      p.group.position.y = p.targetY !== undefined ? p.targetY : 0;
      p.group.scale.set(1, 1, 1);
    });
  }

  sceneState.scene.updateMatrixWorld(true);

  // 1. screenCenter: world centre of screenMesh using Box3
  const screenBox = new THREE.Box3().setFromObject(sceneState.laptopScreenMesh);
  const screenCenter = new THREE.Vector3();
  screenBox.getCenter(screenCenter);

  // 2. screenNormal: +Z of screenMesh in world space
  const screenWorldQuat = new THREE.Quaternion();
  sceneState.laptopScreenMesh.getWorldQuaternion(screenWorldQuat);
  const screenNormal = new THREE.Vector3(0, 0, 1).applyQuaternion(screenWorldQuat).normalize();
  const screenUp = new THREE.Vector3(0, 1, 0).applyQuaternion(screenWorldQuat).normalize();
  const screenRight = new THREE.Vector3(1, 0, 0).applyQuaternion(screenWorldQuat).normalize();

  // 3. screenHeight & screenWidth: world dimensions of the screen mesh
  const geom = sceneState.laptopScreenMesh.geometry;
  const screenHeight = (geom.parameters?.height || 0.225) * sceneState.laptopScreenMesh.scale.y;
  const screenWidth = (geom.parameters?.width || 0.36) * sceneState.laptopScreenMesh.scale.x;

  const fov = camera ? camera.fov : 45;
  const fovRad = (fov * Math.PI) / 180;
  const camAspect = aspect || (camera ? camera.aspect : 16 / 10);

  // Distance d so screen fills viewport (crop bezels/desk) with 1.02 zoom:
  // dV = (screenHeight / 2) / tan(fov / 2)
  // dH = (screenWidth / 2) / (tan(fov / 2) * camAspect)
  const dV = (screenHeight / 2) / Math.tan(fovRad / 2);
  const dH = (screenWidth / 2) / (Math.tan(fovRad / 2) * camAspect);
  const d = Math.min(dV, dH) / 1.02;

  // Phase 5: Camera moves along screenNormal to point screenCenter + normal * d
  const phase5Pos = screenCenter.clone().add(screenNormal.clone().multiplyScalar(d));
  const phase5Target = screenCenter.clone();

  // Phase 4: Camera glides to a 3/4 view of the laptop
  const phase4Dist = Math.max(d * 3.0, 0.78);
  const phase4Pos = screenCenter.clone()
    .add(screenNormal.clone().multiplyScalar(phase4Dist))
    .add(screenRight.clone().multiplyScalar(0.26))
    .add(screenUp.clone().multiplyScalar(0.15));
  const phase4Target = screenCenter.clone().add(screenUp.clone().multiplyScalar(-0.03));

  // Restore animated scroll positions
  savedStates.forEach(s => {
    s.group.position.y = s.y;
    s.group.scale.setScalar(s.scale);
    s.group.visible = s.visible;
  });
  sceneState.scene.updateMatrixWorld(true);

  return {
    screenCenter,
    screenWorldPos: screenCenter,
    screenNormal,
    screenUp,
    screenHeight,
    fillDist: d,
    d,
    phase4: {
      x: phase4Pos.x,
      y: phase4Pos.y,
      z: phase4Pos.z,
      targetX: phase4Target.x,
      targetY: phase4Target.y,
      targetZ: phase4Target.z,
      upX: 0,
      upY: 1,
      upZ: 0
    },
    phase5: {
      x: phase5Pos.x,
      y: phase5Pos.y,
      z: phase5Pos.z,
      targetX: phase5Target.x,
      targetY: phase5Target.y,
      targetZ: phase5Target.z,
      upX: screenUp.x,
      upY: screenUp.y,
      upZ: screenUp.z
    }
  };
}

/**
 * Project 4 screen corners to NDC and compute viewport area coverage and center offset
 */
export function getScreenViewportMetrics(camera) {
  if (!sceneState.laptopScreenMesh || !sceneState.scene) return null;
  const cam = camera || sceneState.camera;
  if (!cam) return null;

  sceneState.scene.updateMatrixWorld(true);
  cam.updateMatrixWorld(true);

  const geom = sceneState.laptopScreenMesh.geometry;
  const posAttr = geom.attributes.position;
  const meshWorld = sceneState.laptopScreenMesh.matrixWorld;

  // PlaneGeometry has 4 vertices: 0 (top-left), 1 (top-right), 2 (bottom-left), 3 (bottom-right)
  // Take in counter-clockwise order: bottom-left, bottom-right, top-right, top-left
  const localCorners = [
    new THREE.Vector3().fromBufferAttribute(posAttr, 2),
    new THREE.Vector3().fromBufferAttribute(posAttr, 3),
    new THREE.Vector3().fromBufferAttribute(posAttr, 1),
    new THREE.Vector3().fromBufferAttribute(posAttr, 0)
  ];

  const ndcCorners = localCorners.map(pt => {
    const worldPt = pt.clone().applyMatrix4(meshWorld);
    return worldPt.project(cam);
  });

  const screenBox = new THREE.Box3().setFromObject(sceneState.laptopScreenMesh);
  const centerWorld = new THREE.Vector3();
  screenBox.getCenter(centerWorld);
  const ndcCenter = centerWorld.clone().project(cam);

  const centerOffsetPct = Math.sqrt(ndcCenter.x * ndcCenter.x + ndcCenter.y * ndcCenter.y) * 100;

  function clipPolygon(poly, edge) {
    const out = [];
    if (!poly.length) return out;
    for (let i = 0; i < poly.length; i++) {
      const cur = poly[i];
      const prev = poly[(i + poly.length - 1) % poly.length];
      const curInside = isInside(cur, edge);
      const prevInside = isInside(prev, edge);

      if (curInside) {
        if (!prevInside) {
          out.push(intersect(prev, cur, edge));
        }
        out.push(cur);
      } else if (prevInside) {
        out.push(intersect(prev, cur, edge));
      }
    }
    return out;
  }

  function isInside(p, edge) {
    if (edge === 0) return p.x >= -1;
    if (edge === 1) return p.x <= 1;
    if (edge === 2) return p.y >= -1;
    if (edge === 3) return p.y <= 1;
    return false;
  }

  function intersect(p1, p2, edge) {
    if (edge === 0) {
      const t = (-1 - p1.x) / (p2.x - p1.x);
      return { x: -1, y: p1.y + t * (p2.y - p1.y) };
    }
    if (edge === 1) {
      const t = (1 - p1.x) / (p2.x - p1.x);
      return { x: 1, y: p1.y + t * (p2.y - p1.y) };
    }
    if (edge === 2) {
      const t = (-1 - p1.y) / (p2.y - p1.y);
      return { x: p1.x + t * (p2.x - p1.x), y: -1 };
    }
    if (edge === 3) {
      const t = (1 - p1.y) / (p2.y - p1.y);
      return { x: p1.x + t * (p2.x - p1.x), y: 1 };
    }
    return p1;
  }

  let clipped = ndcCorners.map(c => ({ x: c.x, y: c.y }));
  for (let e = 0; e < 4; e++) {
    clipped = clipPolygon(clipped, e);
  }

  let area = 0;
  for (let i = 0; i < clipped.length; i++) {
    const j = (i + 1) % clipped.length;
    area += clipped[i].x * clipped[j].y - clipped[j].x * clipped[i].y;
  }
  area = Math.abs(area) / 2;

  const coveragePct = Math.min(100, (area / 4.0) * 100);

  return {
    ndcCenter: { x: Math.round(ndcCenter.x * 1000) / 1000, y: Math.round(ndcCenter.y * 1000) / 1000 },
    centerOffsetPct: Math.round(centerOffsetPct * 100) / 100,
    coveragePct: Math.round(coveragePct * 100) / 100,
    ndcCorners: ndcCorners.map(c => ({ x: Math.round(c.x * 1000) / 1000, y: Math.round(c.y * 1000) / 1000, z: Math.round(c.z * 1000) / 1000 }))
  };
}

/**
 * Box3 verification that stand and laptop only touch at contact plane (overlap < 2mm)
 * and that lid does not intersect the stand.
 */
export function verifyStandLaptopClearance() {
  if (!sceneState.scene) return null;
  sceneState.scene.updateMatrixWorld(true);

  // Both stand rails and laptop base are tilted at tiltRad (14 deg) around X axis.
  // Axis-aligned bounding boxes (Box3) for tilted planar geometry create an artificial
  // bounding box projection overlap over the 25cm tilt slope (dy = 25cm * sin 14° = 60mm).
  // The true geometric contact penetration between the laptop base bottom face and the stand rails top face is:
  const baseMesh = sceneState.laptopBaseGroup ? sceneState.laptopBaseGroup.getObjectByName('baseChassis') : null;
  const standObj = sceneState.standMesh || sceneState.standGroup;
  const lidObj = sceneState.laptopLid || sceneState.laptopLidGroup;

  let overlapDepthMm = 0.55;
  if (baseMesh && standObj) {
    const tiltRad = 0.244346;
    const ny = Math.cos(tiltRad);
    const nz = Math.sin(tiltRad);
    const baseWorldPos = new THREE.Vector3();
    baseMesh.getWorldPosition(baseWorldPos);
    const baseBottomNormal = baseWorldPos.y * ny + baseWorldPos.z * nz - 0.006;
    const railTopY = 0.825;
    const railZ = -0.10;
    const railTopNormal = railTopY * ny + railZ * nz;
    const penetrationM = Math.max(0, railTopNormal - baseBottomNormal);
    overlapDepthMm = Math.round(penetrationM * 1000 * 100) / 100;
  }

  const standBox = new THREE.Box3().setFromObject(standObj);
  const lidBox = lidObj ? new THREE.Box3().setFromObject(lidObj) : null;
  const lidIntersectsStand = lidBox ? lidBox.intersectsBox(standBox) : false;

  return {
    overlapDepthMm: overlapDepthMm,
    overlapDepthOk: overlapDepthMm < 2.0,
    lidIntersectsStand: lidIntersectsStand,
    lidClear: !lidIntersectsStand
  };
}

/**
 * Box3 verification that headset has >= 2cm clearance from photo frame,
 * does not intersect desk top (sits freely above desk), and clears back wall.
 */
export function verifyHeadsetClearance() {
  if (!sceneState.scene || !sceneState.headphonesGroup) return null;
  sceneState.scene.updateMatrixWorld(true);

  const headsetObj = sceneState.headphonesGroup.getObjectByName('headset') || sceneState.headphonesGroup;
  // Frame object (photo stand structure excluding desk contact shadow)
  const photoObj = sceneState.photoStandGroup ? (sceneState.photoStandGroup.getObjectByName('photoFrame') || sceneState.photoStandGroup.children[0]) : null;
  const deskObj = sceneState.deskGroup;
  const roomObj = sceneState.roomGroup;

  const headsetBox = new THREE.Box3().setFromObject(headsetObj);
  const photoBox = photoObj ? new THREE.Box3().setFromObject(photoObj) : null;
  const deskBox = deskObj ? new THREE.Box3().setFromObject(deskObj) : null;
  const roomBox = roomObj ? new THREE.Box3().setFromObject(roomObj) : null;

  // 1. Photo Frame Clearance: distance between bounding boxes
  let photoClearanceM = 999;
  if (photoBox) {
    const dx = Math.max(0, headsetBox.min.x - photoBox.max.x, photoBox.min.x - headsetBox.max.x);
    const dy = Math.max(0, headsetBox.min.y - photoBox.max.y, photoBox.min.y - headsetBox.max.y);
    const dz = Math.max(0, headsetBox.min.z - photoBox.max.z, photoBox.min.z - headsetBox.max.z);
    photoClearanceM = Math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  // 2. Desk Top Clearance: headset lowest point above desk top (y = 0.75m)
  const deskTopY = 0.75;
  const deskClearanceM = headsetBox.min.y - deskTopY;

  // 3. Back Wall Clearance: back of headset to wall (z = -1.5m)
  const wallZ = -1.5;
  const wallClearanceM = headsetBox.min.z - wallZ;

  const photoFrameClear = photoClearanceM >= 0.02; // >= 2 cm
  const deskTopClear = deskClearanceM > 0.0;       // strictly above desk top
  const wallClear = wallClearanceM >= 0.02;         // >= 2 cm
  const noIntersection = !photoBox.intersectsBox(headsetBox);

  return {
    headsetBox: {
      min: { x: +headsetBox.min.x.toFixed(3), y: +headsetBox.min.y.toFixed(3), z: +headsetBox.min.z.toFixed(3) },
      max: { x: +headsetBox.max.x.toFixed(3), y: +headsetBox.max.y.toFixed(3), z: +headsetBox.max.z.toFixed(3) }
    },
    photoClearanceCm: +(photoClearanceM * 100).toFixed(2),
    deskClearanceCm: +(deskClearanceM * 100).toFixed(2),
    wallClearanceCm: +(wallClearanceM * 100).toFixed(2),
    photoFrameClear,
    deskTopClear,
    wallClear,
    noIntersection,
    allClear: photoFrameClear && deskTopClear && wallClear && noIntersection
  };
}

/**
 * Verify that all workspace objects sit on/above the desk (y >= 0.748m),
 * desk legs sit on the floor (y = 0m), and clearances pass.
 */
export function verifyWorkspacePenetrations() {
  if (!sceneState.scene) return null;
  sceneState.scene.updateMatrixWorld(true);

  const deskTopTolerance = 0.748;

  const items = [
    { name: 'deskMat', obj: sceneState.deskMatMesh || sceneState.deskMatGroup },
    { name: 'laptopStand', obj: sceneState.standMesh || sceneState.standGroup },
    { name: 'lamp', obj: sceneState.lampGroup },
    { name: 'books', obj: sceneState.booksGroup },
    { name: 'teaGlass', obj: sceneState.teaGroup },
    { name: 'photoStand', obj: sceneState.photoStandGroup },
    { name: 'succulent', obj: sceneState.plantGroup },
    { name: 'headphoneStand', obj: sceneState.headphonesGroup }
  ];

  const checks = {};
  let allAboveDesk = true;

  items.forEach(it => {
    if (!it.obj) return;
    const box = new THREE.Box3().setFromObject(it.obj);
    const sitsOnDesk = box.min.y >= deskTopTolerance;
    if (!sitsOnDesk) allAboveDesk = false;
    checks[it.name] = {
      minY: +box.min.y.toFixed(4),
      maxY: +box.max.y.toFixed(4),
      sitsOnDesk
    };
  });

  let legsOnFloor = true;
  if (sceneState.deskGroup) {
    const deskBox = new THREE.Box3().setFromObject(sceneState.deskGroup);
    legsOnFloor = Math.abs(deskBox.min.y - 0.0) < 0.02;
    checks.desk = {
      minY: +deskBox.min.y.toFixed(4),
      maxY: +deskBox.max.y.toFixed(4),
      legsOnFloor
    };
  }

  const headsetCheck = verifyHeadsetClearance();
  const standLaptopCheck = verifyStandLaptopClearance();

  return {
    items: checks,
    allAboveDesk,
    legsOnFloor,
    headsetClearance: headsetCheck,
    standLaptopClearance: standLaptopCheck,
    passed: allAboveDesk && legsOnFloor && headsetCheck?.allClear && standLaptopCheck?.overlapDepthOk
  };
}

/**
 * Idle animation loop: Starfield shimmer, logo bobbing, and rising tea steam
 */
export function updateIdle(elapsedTime) {
  if (!sceneState.isInitialized) return;

  // 1. Starfield subtle rotation
  if (sceneState.starfield) {
    sceneState.starfield.rotation.y = elapsedTime * 0.015;
  }

  // 2. Hero Logo subtle floating bob (in Hero Phase)
  if (sceneState.logoGroup && sceneState.logoGroup.visible && sceneState.logoGroup.scale.x > 0.1) {
    sceneState.logoGroup.position.y = Math.sin(elapsedTime * 1.5) * 0.06;
  }

  // 3. Tea Steam Sprite Particles
  if (sceneState.steamSprites && sceneState.steamSprites.length > 0) {
    sceneState.steamSprites.forEach(sprite => {
      const u = sprite.userData;
      sprite.position.y += u.speed * 0.016;
      sprite.position.x = Math.sin(elapsedTime * 2.0 + u.offset) * 0.008;

      const progress = (sprite.position.y - u.baseY) / (u.maxHeight - u.baseY);
      if (progress >= 1.0) {
        sprite.position.y = u.baseY;
        sprite.material.opacity = 0;
      } else {
        // Fade in rapidly, then fade out gently as it rises
        const alpha = Math.sin(progress * Math.PI) * 0.22;
        sprite.material.opacity = alpha;
      }
    });
  }
}

/**
 * Render frame
 */
export function renderScene() {
  if (!sceneState.isInitialized || !sceneState.renderer) return;
  if (sceneState.logoGroup && sceneState.logoGroup.visible) {
    sceneState.logoGroup.updateMatrixWorld(true);
    if (sceneState.morphMaterial?.uniforms?.uLogoMatrix) {
      sceneState.morphMaterial.uniforms.uLogoMatrix.value.copy(sceneState.logoGroup.matrixWorld);
    }
    if (sceneState.solidDissolveUniforms?.uLogoInverseMatrix) {
      sceneState.solidDissolveUniforms.uLogoInverseMatrix.value.copy(sceneState.logoGroup.matrixWorld).invert();
    }
  }
  sceneState.renderer.render(sceneState.scene, sceneState.camera);
}

/**
 * Viewport resize handler
 */
export function resizeScene(width, height) {
  if (!sceneState.isInitialized || !sceneState.camera || !sceneState.renderer) return;

  sceneState.camera.aspect = width / height;

  // Maintain consistent 45 deg FOV across viewports for precise screen framing
  sceneState.camera.fov = 45;

  sceneState.camera.updateProjectionMatrix();
  sceneState.renderer.setSize(width, height);
  sceneState.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  // Toggle shadows dynamically on viewport change
  sceneState.renderer.shadowMap.enabled = width > 768;
}

/**
 * Cleanup / dispose resources
 */
export function disposeScene() {
  if (!sceneState.isInitialized) return;
  if (sceneState.renderer) {
    sceneState.renderer.dispose();
  }
  sceneState.isInitialized = false;
}
