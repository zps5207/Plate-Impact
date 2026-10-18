/**
 * viewer.js - High-performance Client-Side WebGL (three.js) ODB Impact Viewer.
 *
 * Runs entirely on the browser GPU:
 *  - Loads manifest.json and precomputed binary buffers once.
 *  - Preallocates geometry buffers once.
 *  - On each animation frame, updates Float32 node positions and exposed face indices.
 *  - Full continuous OrbitControls manipulation without interrupting playback.
 *  - Camera presets: Iso (perspective), Symmetry (orthographic), Reset.
 *  - In-browser video recording via canvas.captureStream + MediaRecorder and PNG snapshot.
 */

(function () {
  'use strict';

  // --- Global Application State ---
  let manifest = null;
  let n_frames = 0;
  let currentFrame = 0;
  let isPlaying = false;
  let speed = 1.0;
  let isLoop = true;
  let targetFps = 30.0;
  let lastTickTime = performance.now();
  let lastStatusFrame = -1;

  // Render Modes
  let hostMode = 'wireframe';   // 'wireframe', 'solid', 'hidden'
  let fibersOnly = false;
  let ballMode = 'wireframe';   // 'wireframe', 'solid', 'hidden'
  let hostOpacity = 1.0;
  let hostEdges = false;

  // Colors
  let hostColor = '#8C8C8C';
  let fiberColor = '#0033CC';
  let ballColor = '#606060';
  let bgColor = '#FFFFFF';

  // Line Widths
  let fiberLineWidth = 1.0;
  let hostLineWidth = 1.0;
  let ballLineWidth = 1.0;

  // Binary Arrays
  let hostPosData = null;       // Float32Array [frames, n_host_nodes, 3]
  let ballPosData = null;       // Float32Array [frames, n_ball_nodes, 3]
  let fiberPosData = null;      // Float32Array [frames, n_fiber_nodes, 3]
  let hostStatusData = null;    // Uint8Array   [frames, n_host_elements]
  let hostFaceE1 = null;        // Uint32Array  [n_faces]
  let hostFaceE2 = null;        // Int32Array   [n_faces]
  let hostFaceTris = null;      // Uint32Array  [n_faces, 6]
  let hostFaceEdges = null;     // Uint32Array  [n_faces, 8]
  let ballFacesTris = null;     // Uint32Array
  let ballFacesEdges = null;    // Uint32Array
  let fiberLines = null;        // Uint32Array

  // Counts
  let n_host_nodes = 0;
  let n_host_elements = 0;
  let n_host_faces = 0;
  let n_ball_nodes = 0;
  let n_fiber_nodes = 0;
  let n_fiber_segments = 0;

  // Three.js Core Objects
  let scene, renderer;
  let perspectiveCamera, orthographicCamera, activeCamera;
  let controls;
  let viewportContainer, canvas;

  // Mesh & Geometry Objects
  let hostSolidGeom, hostSolidPosAttr, hostSolidIndices, hostSolidMesh, hostSolidMaterial;
  let hostWireGeom, hostWirePosAttr, hostWireIndices, hostWireMesh, hostWireMaterial;
  let ballSolidGeom, ballPosAttr, ballSolidMesh, ballSolidMaterial;
  let ballWireGeom, ballWireMesh, ballWireMaterial;
  let fiberGeom, fiberPosAttr, fiberMesh, fiberMaterial;

  // Fat Lines for Fibers
  let fiberFatGeom = null;
  let fiberFatMaterial = null;
  let fiberFatMesh = null;
  let fiberFatPositions = null;

  // Recording State
  let isRecording = false;
  let recordingCancelled = false;

  // DOM Elements
  const btnPlay = document.getElementById('btn-play');
  const iconPlay = document.getElementById('icon-play');
  const iconPause = document.getElementById('icon-pause');
  const lblPlay = document.getElementById('lbl-play');
  const btnStepBack = document.getElementById('btn-step-back');
  const btnStepForward = document.getElementById('btn-step-forward');
  const scrubber = document.getElementById('scrubber');
  const lblTime = document.getElementById('lbl-time');
  const selSpeed = document.getElementById('sel-speed');
  const btnLoop = document.getElementById('btn-loop');
  const btnCamIso = document.getElementById('btn-cam-iso');
  const btnCamSym = document.getElementById('btn-cam-sym');
  const btnCamReset = document.getElementById('btn-cam-reset');
  const btnSnapshot = document.getElementById('btn-snapshot');
  const btnRecord = document.getElementById('btn-record');
  const btnToggleDrawer = document.getElementById('btn-toggle-drawer');
  const drawer = document.getElementById('drawer');

  const selHostMode = document.getElementById('sel-host-mode');
  const chkFibersOnly = document.getElementById('chk-fibers-only');
  const selBallMode = document.getElementById('sel-ball-mode');
  const sliderHostOpacity = document.getElementById('slider-host-opacity');
  const lblHostOpacity = document.getElementById('lbl-host-opacity');
  const chkHostEdges = document.getElementById('chk-host-edges');

  const colHost = document.getElementById('col-host');
  const colFiber = document.getElementById('col-fiber');
  const colBall = document.getElementById('col-ball');
  const colBg = document.getElementById('col-bg');
  const lblColHost = document.getElementById('lbl-col-host');
  const lblColFiber = document.getElementById('lbl-col-fiber');
  const lblColBall = document.getElementById('lbl-col-ball');
  const lblColBg = document.getElementById('lbl-col-bg');

  const sliderFiberLw = document.getElementById('slider-fiber-lw');
  const sliderHostLw = document.getElementById('slider-host-lw');
  const sliderBallLw = document.getElementById('slider-ball-lw');
  const lblFiberLw = document.getElementById('lbl-fiber-lw');
  const lblHostLw = document.getElementById('lbl-host-lw');
  const lblBallLw = document.getElementById('lbl-ball-lw');

  const hudLine1 = document.getElementById('hud-line1');
  const hudLine2 = document.getElementById('hud-line2');
  const loadingScreen = document.getElementById('loading-screen');
  const loadingDetail = document.getElementById('loading-detail');

  // Modal elements
  const modalRecord = document.getElementById('modal-record');
  const btnRecStart = document.getElementById('btn-rec-start');
  const btnRecCancel = document.getElementById('btn-rec-cancel');
  const recFps = document.getElementById('rec-fps');
  const recStart = document.getElementById('rec-start');
  const recEnd = document.getElementById('rec-end');
  const recProgressContainer = document.getElementById('rec-progress-container');
  const recProgressFill = document.getElementById('rec-progress-fill');
  const recStatusText = document.getElementById('rec-status-text');
  const recPctText = document.getElementById('rec-pct-text');
  const recDownloadContainer = document.getElementById('rec-download-container');
  const recDownloadLink = document.getElementById('rec-download-link');

  // --- Entry Point ---
  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  async function init() {
    canvas = document.getElementById('webgl-canvas');
    viewportContainer = document.getElementById('viewport-container');

    initThree();
    setupEventListeners();

    try {
      await loadDataset();
      buildGeometries();
      applyPreset('iso');
      updateFrame(0, true);
      hideLoading();
      requestAnimationFrame(renderLoop);
    } catch (err) {
      console.error('Initialization failed:', err);
      loadingDetail.textContent = 'Error: ' + err.message;
      loadingDetail.style.color = '#ff6b6b';
    }
  }

  // --- Three.js Initialization ---
  function initThree() {
    const w = viewportContainer.clientWidth || window.innerWidth;
    const h = viewportContainer.clientHeight || window.innerHeight;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(bgColor);

    // Renderer with high visual fidelity and screenshot support
    renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      preserveDrawingBuffer: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    // Perspective Camera (30 deg FOV matching VTK / odb_viewer.py)
    perspectiveCamera = new THREE.PerspectiveCamera(30, w / h, 0.001, 20.0);
    perspectiveCamera.up.set(0, 0, 1);

    // Orthographic Camera for Symmetry view
    const aspect = w / h;
    const s = 0.03;
    orthographicCamera = new THREE.OrthographicCamera(-s * aspect, s * aspect, s, -s, 0.001, 20.0);
    orthographicCamera.up.set(1, 0, 0);

    activeCamera = perspectiveCamera;

    // Controls
    controls = new THREE.OrbitControls(activeCamera, canvas);
    controls.enableDamping = false;
    controls.screenSpacePanning = true;

    // Headlight and ambient lighting matching PyVista / Abaqus renders
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.5);
    dirLight1.position.set(1, 2, 3);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.3);
    dirLight2.position.set(-1, -2, -3);
    scene.add(dirLight2);

    window.addEventListener('resize', onWindowResize);
  }

  function onWindowResize() {
    const w = viewportContainer.clientWidth;
    const h = viewportContainer.clientHeight;
    if (w <= 0 || h <= 0) return;

    renderer.setSize(w, h);

    const aspect = w / h;
    perspectiveCamera.aspect = aspect;
    perspectiveCamera.updateProjectionMatrix();

    if (activeCamera === orthographicCamera && manifest && manifest.camera_presets?.symmetry) {
      const s = manifest.camera_presets.symmetry.parallel_scale || 0.027;
      orthographicCamera.left = -s * aspect;
      orthographicCamera.right = s * aspect;
      orthographicCamera.top = s;
      orthographicCamera.bottom = -s;
      orthographicCamera.updateProjectionMatrix();
    }

    if (fiberFatMaterial) {
      fiberFatMaterial.resolution.set(w, h);
    }
  }

  // --- Data Loading ---
  async function fetchBuffer(url, name) {
    loadingDetail.textContent = `Fetching ${name}...`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`);
    return await res.arrayBuffer();
  }

  async function loadDataset() {
    const urlParams = new URLSearchParams(window.location.search);
    const dataDir = urlParams.get('data') || '/data';

    loadingDetail.textContent = 'Loading manifest.json...';
    const mRes = await fetch(`${dataDir}/manifest.json`);
    if (!mRes.ok) throw new Error(`Cannot load manifest.json from ${dataDir}`);
    manifest = await mRes.json();

    n_frames = manifest.n_frames;
    targetFps = manifest.fps || 30.0;
    n_host_nodes = manifest.counts.host_nodes;
    n_host_elements = manifest.counts.host_elements;
    n_host_faces = manifest.counts.host_faces;
    n_ball_nodes = manifest.counts.ball_nodes;
    n_fiber_nodes = manifest.counts.fiber_nodes;
    n_fiber_segments = manifest.counts.fiber_segments;

    scrubber.max = n_frames - 1;
    recStart.max = n_frames;
    recEnd.max = n_frames;
    recEnd.value = n_frames;

    // Apply color defaults from manifest
    if (manifest.default_colors) {
      hostColor = manifest.default_colors.host || hostColor;
      fiberColor = manifest.default_colors.fiber || fiberColor;
      ballColor = manifest.default_colors.ball || ballColor;
      bgColor = manifest.default_colors.bg || bgColor;
      syncColorInputs();
    }
    populateSwatches();

    // Fetch binary buffers in parallel batches
    const files = manifest.files;
    const fetchPromises = [
      fetchBuffer(`${dataDir}/${files.host_pos.filename}`, 'host_pos.f32').then(b => hostPosData = new Float32Array(b)),
      fetchBuffer(`${dataDir}/${files.ball_pos.filename}`, 'ball_pos.f32').then(b => ballPosData = new Float32Array(b)),
      fetchBuffer(`${dataDir}/${files.fiber_pos.filename}`, 'fiber_pos.f32').then(b => fiberPosData = new Float32Array(b)),
      fetchBuffer(`${dataDir}/${files.host_status.filename}`, 'host_status.u8').then(b => hostStatusData = new Uint8Array(b)),
      fetchBuffer(`${dataDir}/${files.host_faces_e1.filename}`, 'host_faces_e1.u32').then(b => hostFaceE1 = new Uint32Array(b)),
      fetchBuffer(`${dataDir}/${files.host_faces_e2.filename}`, 'host_faces_e2.i32').then(b => hostFaceE2 = new Int32Array(b)),
      fetchBuffer(`${dataDir}/${files.host_faces_tris.filename}`, 'host_faces_tris.u32').then(b => hostFaceTris = new Uint32Array(b)),
      fetchBuffer(`${dataDir}/${files.host_faces_edges.filename}`, 'host_faces_edges.u32').then(b => hostFaceEdges = new Uint32Array(b)),
      fetchBuffer(`${dataDir}/${files.ball_faces_tris.filename}`, 'ball_faces_tris.u32').then(b => ballFacesTris = new Uint32Array(b)),
      fetchBuffer(`${dataDir}/${files.ball_faces_edges.filename}`, 'ball_faces_edges.u32').then(b => ballFacesEdges = new Uint32Array(b)),
      fetchBuffer(`${dataDir}/${files.fiber_lines.filename}`, 'fiber_lines.u32').then(b => fiberLines = new Uint32Array(b)),
    ];

    await Promise.all(fetchPromises);
    loadingDetail.textContent = 'Constructing WebGL buffers...';
  }

  // --- Geometry Construction ---
  function buildGeometries() {
    // 1. Host Geometries
    hostSolidPosAttr = new THREE.BufferAttribute(new Float32Array(n_host_nodes * 3), 3);
    hostSolidPosAttr.setUsage(THREE.DynamicDrawUsage);

    // Solid
    hostSolidGeom = new THREE.BufferGeometry();
    hostSolidGeom.setAttribute('position', hostSolidPosAttr);
    hostSolidIndices = new Uint32Array(n_host_faces * 6);
    const hostSolidIndexAttr = new THREE.BufferAttribute(hostSolidIndices, 1);
    hostSolidIndexAttr.setUsage(THREE.DynamicDrawUsage);
    hostSolidGeom.setIndex(hostSolidIndexAttr);

    hostSolidMaterial = new THREE.MeshStandardMaterial({
      color: new THREE.Color(hostColor),
      roughness: 0.6,
      metalness: 0.1,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: hostOpacity,
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    });
    hostSolidMesh = new THREE.Mesh(hostSolidGeom, hostSolidMaterial);
    scene.add(hostSolidMesh);

    // Wireframe (Exterior Edges)
    hostWireGeom = new THREE.BufferGeometry();
    hostWireGeom.setAttribute('position', hostSolidPosAttr); // share position buffer
    hostWireIndices = new Uint32Array(n_host_faces * 8);
    const hostWireIndexAttr = new THREE.BufferAttribute(hostWireIndices, 1);
    hostWireIndexAttr.setUsage(THREE.DynamicDrawUsage);
    hostWireGeom.setIndex(hostWireIndexAttr);

    hostWireMaterial = new THREE.LineBasicMaterial({
      color: new THREE.Color(hostColor),
    });
    hostWireMesh = new THREE.LineSegments(hostWireGeom, hostWireMaterial);
    scene.add(hostWireMesh);

    // 2. Ball Geometries (Static Exterior Topology)
    ballPosAttr = new THREE.BufferAttribute(new Float32Array(n_ball_nodes * 3), 3);
    ballPosAttr.setUsage(THREE.DynamicDrawUsage);

    // Solid Ball
    ballSolidGeom = new THREE.BufferGeometry();
    ballSolidGeom.setAttribute('position', ballPosAttr);
    ballSolidGeom.setIndex(new THREE.BufferAttribute(ballFacesTris, 1));
    ballSolidMaterial = new THREE.MeshStandardMaterial({
      color: new THREE.Color(ballColor),
      roughness: 0.5,
      metalness: 0.2,
      side: THREE.DoubleSide,
    });
    ballSolidMesh = new THREE.Mesh(ballSolidGeom, ballSolidMaterial);
    scene.add(ballSolidMesh);

    // Wireframe Ball
    ballWireGeom = new THREE.BufferGeometry();
    ballWireGeom.setAttribute('position', ballPosAttr);
    ballWireGeom.setIndex(new THREE.BufferAttribute(ballFacesEdges, 1));
    ballWireMaterial = new THREE.LineBasicMaterial({
      color: new THREE.Color(ballColor),
    });
    ballWireMesh = new THREE.LineSegments(ballWireGeom, ballWireMaterial);
    scene.add(ballWireMesh);

    // 3. Fiber Geometries (Static Line Segments)
    fiberPosAttr = new THREE.BufferAttribute(new Float32Array(n_fiber_nodes * 3), 3);
    fiberPosAttr.setUsage(THREE.DynamicDrawUsage);

    fiberGeom = new THREE.BufferGeometry();
    fiberGeom.setAttribute('position', fiberPosAttr);
    fiberGeom.setIndex(new THREE.BufferAttribute(fiberLines, 1));
    fiberMaterial = new THREE.LineBasicMaterial({
      color: new THREE.Color(fiberColor),
    });
    fiberMesh = new THREE.LineSegments(fiberGeom, fiberMaterial);
    scene.add(fiberMesh);

    // Optional Fat Lines support using LineSegments2
    if (window.THREE && THREE.LineSegments2 && THREE.LineSegmentsGeometry && THREE.LineMaterial) {
      fiberFatPositions = new Float32Array(n_fiber_segments * 6);
      fiberFatGeom = new THREE.LineSegmentsGeometry();
      const w = viewportContainer.clientWidth || window.innerWidth;
      const h = viewportContainer.clientHeight || window.innerHeight;
      fiberFatMaterial = new THREE.LineMaterial({
        color: new THREE.Color(fiberColor).getHex(),
        linewidth: fiberLineWidth,
        resolution: new THREE.Vector2(w, h),
      });
      fiberFatMesh = new THREE.LineSegments2(fiberFatGeom, fiberFatMaterial);
      fiberFatMesh.visible = false;
      scene.add(fiberFatMesh);
    }

    updateMeshVisibilities();
  }

  // --- Fast Per-Frame Buffer Updates ---
  function updateFrame(frame, forceStatusUpdate = false) {
    if (frame < 0 || frame >= n_frames) return;
    currentFrame = frame;

    // 1. Update Host Positions (328 KB copy)
    const hostOffset = frame * n_host_nodes * 3;
    hostSolidPosAttr.array.set(hostPosData.subarray(hostOffset, hostOffset + n_host_nodes * 3));
    hostSolidPosAttr.needsUpdate = true;

    // 2. Update Ball Positions
    const ballOffset = frame * n_ball_nodes * 3;
    ballPosAttr.array.set(ballPosData.subarray(ballOffset, ballOffset + n_ball_nodes * 3));
    ballPosAttr.needsUpdate = true;

    // 3. Update Fiber Positions
    const fiberOffset = frame * n_fiber_nodes * 3;
    fiberPosAttr.array.set(fiberPosData.subarray(fiberOffset, fiberOffset + n_fiber_nodes * 3));
    fiberPosAttr.needsUpdate = true;

    // If using fat lines
    if (fiberFatMesh && fiberFatMesh.visible) {
      updateFiberFatPositions();
    }

    // 4. Update Host Exposed Exterior Faces & Edges if status changed
    if (forceStatusUpdate || frame !== lastStatusFrame) {
      updateHostVisibility(frame);
      lastStatusFrame = frame;
    }

    // 5. Update UI controls & HUD
    updateUI();

    // 6. Immediately render updated frame
    if (renderer && scene && activeCamera) {
      renderer.render(scene, activeCamera);
    }
  }

  function updateHostVisibility(frame) {
    const statusOffset = frame * n_host_elements;
    const status = hostStatusData.subarray(statusOffset, statusOffset + n_host_elements);

    let triCount = 0;
    let edgeCount = 0;

    const needTris = hostSolidMesh.visible;
    const needEdges = hostWireMesh.visible;

    for (let i = 0; i < n_host_faces; i++) {
      const e1 = hostFaceE1[i];
      const e2 = hostFaceE2[i];

      // Conformal Face Ownership rule from odb_viewer.py:
      // Boundary face (e2 == -1): visible iff owner alive
      // Interior face (e2 != -1): visible iff exactly one is alive and one is dead
      let isVis = false;
      if (e2 === -1) {
        isVis = (status[e1] === 1);
      } else {
        isVis = (status[e1] !== status[e2]);
      }

      if (isVis) {
        if (needTris) {
          const src = i * 6;
          hostSolidIndices[triCount++] = hostFaceTris[src];
          hostSolidIndices[triCount++] = hostFaceTris[src + 1];
          hostSolidIndices[triCount++] = hostFaceTris[src + 2];
          hostSolidIndices[triCount++] = hostFaceTris[src + 3];
          hostSolidIndices[triCount++] = hostFaceTris[src + 4];
          hostSolidIndices[triCount++] = hostFaceTris[src + 5];
        }
        if (needEdges) {
          const src = i * 8;
          hostWireIndices[edgeCount++] = hostFaceEdges[src];
          hostWireIndices[edgeCount++] = hostFaceEdges[src + 1];
          hostWireIndices[edgeCount++] = hostFaceEdges[src + 2];
          hostWireIndices[edgeCount++] = hostFaceEdges[src + 3];
          hostWireIndices[edgeCount++] = hostFaceEdges[src + 4];
          hostWireIndices[edgeCount++] = hostFaceEdges[src + 5];
          hostWireIndices[edgeCount++] = hostFaceEdges[src + 6];
          hostWireIndices[edgeCount++] = hostFaceEdges[src + 7];
        }
      }
    }

    if (needTris) {
      hostSolidGeom.setDrawRange(0, triCount);
      hostSolidGeom.index.needsUpdate = true;
    }
    if (needEdges) {
      hostWireGeom.setDrawRange(0, edgeCount);
      hostWireGeom.index.needsUpdate = true;
    }
  }

  function updateFiberFatPositions() {
    if (!fiberFatPositions || !fiberFatGeom) return;
    const pos = fiberPosAttr.array;
    let dst = 0;
    for (let i = 0; i < n_fiber_segments; i++) {
      const n0 = fiberLines[i * 2] * 3;
      const n1 = fiberLines[i * 2 + 1] * 3;
      fiberFatPositions[dst++] = pos[n0];
      fiberFatPositions[dst++] = pos[n0 + 1];
      fiberFatPositions[dst++] = pos[n0 + 2];
      fiberFatPositions[dst++] = pos[n1];
      fiberFatPositions[dst++] = pos[n1 + 1];
      fiberFatPositions[dst++] = pos[n1 + 2];
    }
    fiberFatGeom.setPositions(fiberFatPositions);
  }

  function updateMeshVisibilities() {
    // Host
    if (fibersOnly || hostMode === 'hidden') {
      hostSolidMesh.visible = false;
      hostWireMesh.visible = false;
    } else if (hostMode === 'wireframe') {
      hostSolidMesh.visible = false;
      hostWireMesh.visible = true;
      hostWireMaterial.color.set(hostColor);
    } else if (hostMode === 'solid') {
      hostSolidMesh.visible = true;
      hostSolidMaterial.color.set(hostColor);
      hostSolidMaterial.opacity = hostOpacity;
      if (hostEdges) {
        hostWireMesh.visible = true;
        hostWireMaterial.color.set('#303030');
      } else {
        hostWireMesh.visible = false;
      }
    }

    // Ball
    if (ballMode === 'wireframe') {
      ballSolidMesh.visible = false;
      ballWireMesh.visible = true;
      ballWireMaterial.color.set(ballColor);
    } else if (ballMode === 'solid') {
      ballSolidMesh.visible = true;
      ballSolidMaterial.color.set(ballColor);
      ballWireMesh.visible = false;
    } else {
      ballSolidMesh.visible = false;
      ballWireMesh.visible = false;
    }

    // Fibers
    if (fiberLineWidth > 1.0 && fiberFatMesh) {
      fiberMesh.visible = false;
      fiberFatMesh.visible = true;
      fiberFatMaterial.linewidth = fiberLineWidth;
      fiberFatMaterial.color.set(new THREE.Color(fiberColor).getHex());
      updateFiberFatPositions();
    } else {
      if (fiberFatMesh) fiberFatMesh.visible = false;
      fiberMesh.visible = true;
      fiberMaterial.color.set(fiberColor);
    }

    updateHostVisibility(currentFrame);
    if (renderer && scene && activeCamera) {
      renderer.render(scene, activeCamera);
    }
  }

  // --- Animation Render Loop ---
  function renderLoop(now) {
    requestAnimationFrame(renderLoop);

    if (isPlaying && !isRecording) {
      const dt = (now - lastTickTime) / 1000.0;
      const targetInterval = 1.0 / (targetFps * speed);

      if (dt >= targetInterval) {
        const framesToAdvance = Math.max(1, Math.floor(dt / targetInterval));
        let nextFrame = currentFrame + framesToAdvance;

        if (nextFrame >= n_frames) {
          if (isLoop) {
            nextFrame = nextFrame % n_frames;
          } else {
            nextFrame = n_frames - 1;
            pause();
          }
        }
        updateFrame(nextFrame);
        lastTickTime = now - (dt % targetInterval);
      }
    }

    controls.update();
    renderer.render(scene, activeCamera);
  }

  // --- Playback Controls ---
  function play() {
    if (currentFrame >= n_frames - 1 && !isLoop) {
      updateFrame(0);
    }
    isPlaying = true;
    lastTickTime = performance.now();
    updatePlayPauseButton();
  }

  function pause() {
    isPlaying = false;
    updatePlayPauseButton();
  }

  function togglePlay() {
    if (isPlaying) pause();
    else play();
  }

  function stepFrame(delta) {
    pause();
    let target = (currentFrame + delta) % n_frames;
    if (target < 0) target += n_frames;
    updateFrame(target);
  }

  function updatePlayPauseButton() {
    if (isPlaying) {
      iconPlay.style.display = 'none';
      iconPause.style.display = 'inline';
      lblPlay.textContent = 'Pause';
      btnPlay.classList.add('btn-danger');
      btnPlay.classList.remove('btn-primary');
    } else {
      iconPlay.style.display = 'inline';
      iconPause.style.display = 'none';
      lblPlay.textContent = 'Play';
      btnPlay.classList.add('btn-primary');
      btnPlay.classList.remove('btn-danger');
    }
    updateUI();
  }

  // --- Camera Presets ---
  function applyPreset(preset) {
    if (!manifest?.camera_presets) return;
    const presets = manifest.camera_presets;

    const w = viewportContainer.clientWidth || window.innerWidth;
    const h = viewportContainer.clientHeight || window.innerHeight;
    const aspect = w / h;

    if (preset === 'iso' && presets.iso) {
      const p = presets.iso;
      activeCamera = perspectiveCamera;
      perspectiveCamera.aspect = aspect;
      perspectiveCamera.fov = p.fov || 30.0;
      perspectiveCamera.up.set(p.up[0], p.up[1], p.up[2]);
      perspectiveCamera.position.set(p.position[0], p.position[1], p.position[2]);
      perspectiveCamera.lookAt(p.focal_point[0], p.focal_point[1], p.focal_point[2]);
      perspectiveCamera.updateProjectionMatrix();

      controls.object = perspectiveCamera;
      controls.target.set(p.focal_point[0], p.focal_point[1], p.focal_point[2]);
      controls.update();
    } else if (preset === 'symmetry' && presets.symmetry) {
      const p = presets.symmetry;
      activeCamera = orthographicCamera;
      const s = p.parallel_scale || 0.027002;
      orthographicCamera.left = -s * aspect;
      orthographicCamera.right = s * aspect;
      orthographicCamera.top = s;
      orthographicCamera.bottom = -s;
      orthographicCamera.up.set(p.up[0], p.up[1], p.up[2]);
      orthographicCamera.position.set(p.position[0], p.position[1], p.position[2]);
      orthographicCamera.lookAt(p.focal_point[0], p.focal_point[1], p.focal_point[2]);
      orthographicCamera.updateProjectionMatrix();

      controls.object = orthographicCamera;
      controls.target.set(p.focal_point[0], p.focal_point[1], p.focal_point[2]);
      controls.update();
    } else if (preset === 'reset' && presets.reset) {
      const p = presets.reset;
      activeCamera = perspectiveCamera;
      perspectiveCamera.aspect = aspect;
      perspectiveCamera.fov = p.fov || 30.0;
      perspectiveCamera.up.set(p.up[0], p.up[1], p.up[2]);
      perspectiveCamera.position.set(p.position[0], p.position[1], p.position[2]);
      perspectiveCamera.lookAt(p.focal_point[0], p.focal_point[1], p.focal_point[2]);
      perspectiveCamera.updateProjectionMatrix();

      controls.object = perspectiveCamera;
      controls.target.set(p.focal_point[0], p.focal_point[1], p.focal_point[2]);
      controls.update();
    }

    if (renderer && scene && activeCamera) {
      renderer.render(scene, activeCamera);
    }
  }

  // --- Snapshot & In-Browser Recording ---
  function takeSnapshot() {
    renderer.render(scene, activeCamera);
    const dataUrl = renderer.domElement.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `impact_frame_${currentFrame + 1}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  async function startRecording() {
    if (isRecording) return;
    const fps = parseInt(recFps.value, 10) || 30;
    const startF = Math.max(0, (parseInt(recStart.value, 10) || 1) - 1);
    const endF = Math.min(n_frames - 1, (parseInt(recEnd.value, 10) || n_frames) - 1);
    if (startF > endF) return;

    isRecording = true;
    recordingCancelled = false;
    pause();

    recProgressContainer.style.display = 'block';
    recDownloadContainer.style.display = 'none';
    btnRecStart.disabled = true;

    // Detect browser-supported video encoding
    let mimeType = 'video/webm;codecs=vp9';
    if (window.MediaRecorder) {
      if (MediaRecorder.isTypeSupported('video/mp4;codecs=avc1')) {
        mimeType = 'video/mp4;codecs=avc1';
      } else if (MediaRecorder.isTypeSupported('video/mp4')) {
        mimeType = 'video/mp4';
      } else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9')) {
        mimeType = 'video/webm;codecs=vp9';
      } else if (MediaRecorder.isTypeSupported('video/webm')) {
        mimeType = 'video/webm';
      }
    }

    const stream = canvas.captureStream(fps);
    const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 12000000 });
    const chunks = [];

    recorder.ondataavailable = e => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };

    recorder.start();

    const totalSteps = endF - startF + 1;
    for (let f = startF; f <= endF; f++) {
      if (recordingCancelled) break;
      updateFrame(f);
      renderer.render(scene, activeCamera);

      const stepIdx = f - startF + 1;
      const pct = Math.round((stepIdx / totalSteps) * 100);
      recProgressFill.style.width = pct + '%';
      recPctText.textContent = pct + '%';
      recStatusText.textContent = `Recording frame ${f + 1} of ${endF + 1}...`;

      await new Promise(r => setTimeout(r, 1000 / fps));
    }

    recorder.stop();
    await new Promise(r => { recorder.onstop = r; });

    btnRecStart.disabled = false;
    isRecording = false;

    if (!recordingCancelled && chunks.length > 0) {
      const ext = mimeType.includes('mp4') ? 'mp4' : 'webm';
      const blob = new Blob(chunks, { type: mimeType });
      const url = URL.createObjectURL(blob);
      recDownloadLink.href = url;
      recDownloadLink.download = `impact_frames_${startF + 1}_to_${endF + 1}.${ext}`;
      recDownloadContainer.style.display = 'block';
      recStatusText.textContent = `Recording complete (${(blob.size / 1024 / 1024).toFixed(2)} MB)!`;
    } else {
      recStatusText.textContent = 'Recording cancelled.';
    }
  }

  // --- UI Update & HUD ---
  function updateUI() {
    scrubber.value = currentFrame;

    const t_us = (manifest && manifest.times_us && manifest.times_us[currentFrame] !== undefined)
      ? manifest.times_us[currentFrame]
      : (currentFrame * (1000000.0 / targetFps));

    const timeStr = `${t_us.toFixed(2)} \u03bcs (Frame ${currentFrame + 1}/${n_frames})`;
    lblTime.textContent = timeStr;

    // HUD overlays
    const statusStr = isPlaying ? 'PLAYING' : 'PAUSED';
    const hostStr = fibersOnly ? 'hidden' : hostMode;
    const fibStr = fibersOnly ? 'ONLY' : 'ON';
    hudLine1.textContent = `Time: ${t_us.toFixed(2)} \u03bcs | Frame: ${currentFrame + 1}/${n_frames} | Speed: ${speed.toFixed(2)}x [${statusStr}]`;
    hudLine2.textContent = `Host: ${hostStr} | Fibers: ${fibStr} | Ball: ${ballMode}`;
  }

  function hideLoading() {
    loadingScreen.style.opacity = '0';
    setTimeout(() => loadingScreen.style.display = 'none', 300);
  }

  function syncColorInputs() {
    colHost.value = hostColor;
    colFiber.value = fiberColor;
    colBall.value = ballColor;
    colBg.value = bgColor;
    lblColHost.textContent = hostColor;
    lblColFiber.textContent = fiberColor;
    lblColBall.textContent = ballColor;
    lblColBg.textContent = bgColor;
    scene.background = new THREE.Color(bgColor);
  }

  function populateSwatches() {
    if (!manifest?.color_palettes) return;
    const p = manifest.color_palettes;

    function buildRow(containerId, list, onPick) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = '';
      list.forEach(c => {
        const div = document.createElement('div');
        div.className = 'swatch';
        div.style.backgroundColor = c;
        div.onclick = () => onPick(c);
        container.appendChild(div);
      });
    }

    if (p.host) buildRow('swatches-host', p.host, c => { hostColor = c; syncColorInputs(); updateMeshVisibilities(); });
    if (p.fiber) buildRow('swatches-fiber', p.fiber, c => { fiberColor = c; syncColorInputs(); updateMeshVisibilities(); });
    if (p.ball) buildRow('swatches-ball', p.ball, c => { ballColor = c; syncColorInputs(); updateMeshVisibilities(); });
    if (p.bg) buildRow('swatches-bg', p.bg, c => { bgColor = c; syncColorInputs(); });
  }

  // --- Event Listeners & Keyboard Controls ---
  function setupEventListeners() {
    btnPlay.addEventListener('click', togglePlay);
    btnStepBack.addEventListener('click', () => stepFrame(-1));
    btnStepForward.addEventListener('click', () => stepFrame(1));

    scrubber.addEventListener('input', e => {
      pause();
      updateFrame(parseInt(e.target.value, 10));
    });

    selSpeed.addEventListener('change', e => {
      speed = parseFloat(e.target.value) || 1.0;
      updateUI();
    });

    btnLoop.addEventListener('click', () => {
      isLoop = !isLoop;
      btnLoop.classList.toggle('active', isLoop);
    });

    btnCamIso.addEventListener('click', () => applyPreset('iso'));
    btnCamSym.addEventListener('click', () => applyPreset('symmetry'));
    btnCamReset.addEventListener('click', () => applyPreset('reset'));

    btnSnapshot.addEventListener('click', takeSnapshot);

    // Modal dialogs
    btnRecord.addEventListener('click', () => {
      modalRecord.classList.add('open');
      recProgressContainer.style.display = 'none';
      recDownloadContainer.style.display = 'none';
    });
    btnRecCancel.addEventListener('click', () => {
      recordingCancelled = true;
      modalRecord.classList.remove('open');
    });
    btnRecStart.addEventListener('click', startRecording);

    btnToggleDrawer.addEventListener('click', () => {
      drawer.classList.toggle('collapsed');
      setTimeout(onWindowResize, 220);
    });

    // Drawer options
    selHostMode.addEventListener('change', e => {
      hostMode = e.target.value;
      updateMeshVisibilities();
      updateUI();
    });

    chkFibersOnly.addEventListener('change', e => {
      fibersOnly = e.target.checked;
      updateMeshVisibilities();
      updateUI();
    });

    selBallMode.addEventListener('change', e => {
      ballMode = e.target.value;
      updateMeshVisibilities();
      updateUI();
    });

    sliderHostOpacity.addEventListener('input', e => {
      hostOpacity = parseFloat(e.target.value);
      lblHostOpacity.textContent = hostOpacity.toFixed(2);
      updateMeshVisibilities();
    });

    chkHostEdges.addEventListener('change', e => {
      hostEdges = e.target.checked;
      updateMeshVisibilities();
    });

    // Colors
    colHost.addEventListener('input', e => { hostColor = e.target.value; syncColorInputs(); updateMeshVisibilities(); });
    colFiber.addEventListener('input', e => { fiberColor = e.target.value; syncColorInputs(); updateMeshVisibilities(); });
    colBall.addEventListener('input', e => { ballColor = e.target.value; syncColorInputs(); updateMeshVisibilities(); });
    colBg.addEventListener('input', e => { bgColor = e.target.value; syncColorInputs(); });

    // Line widths
    sliderFiberLw.addEventListener('input', e => {
      fiberLineWidth = parseFloat(e.target.value);
      lblFiberLw.textContent = fiberLineWidth.toFixed(1);
      updateMeshVisibilities();
    });
    sliderHostLw.addEventListener('input', e => {
      hostLineWidth = parseFloat(e.target.value);
      lblHostLw.textContent = hostLineWidth.toFixed(1);
      if (hostWireMaterial) hostWireMaterial.linewidth = hostLineWidth;
    });
    sliderBallLw.addEventListener('input', e => {
      ballLineWidth = parseFloat(e.target.value);
      lblBallLw.textContent = ballLineWidth.toFixed(1);
      if (ballWireMaterial) ballWireMaterial.linewidth = ballLineWidth;
    });

    // Keyboard Shortcuts (matching odb_viewer.py)
    window.addEventListener('keydown', e => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

      const key = e.key;
      if (key === ' ' || key === 'p' || key === 'P') {
        e.preventDefault();
        togglePlay();
      } else if (key === 'ArrowLeft' || key === '[') {
        e.preventDefault();
        stepFrame(-1);
      } else if (key === 'ArrowRight' || key === ']') {
        e.preventDefault();
        stepFrame(1);
      } else if (key === 'Home' || key === '0') {
        e.preventDefault();
        pause();
        updateFrame(0);
      } else if (key === 'End' || key === '9') {
        e.preventDefault();
        pause();
        updateFrame(n_frames - 1);
      } else if (key === '+' || key === '=') {
        e.preventDefault();
        speed = Math.min(8.0, speed * 2.0);
        selSpeed.value = String(speed);
        updateUI();
      } else if (key === '-' || key === '_') {
        e.preventDefault();
        speed = Math.max(0.25, speed / 2.0);
        selSpeed.value = String(speed);
        updateUI();
      } else if (key === 'l' || key === 'L') {
        isLoop = !isLoop;
        btnLoop.classList.toggle('active', isLoop);
      } else if (key === '1') {
        applyPreset('iso');
      } else if (key === '2') {
        applyPreset('symmetry');
      } else if (key === '3' || key === 'r' || key === 'R') {
        applyPreset('reset');
      } else if (key === 'h' || key === 'H') {
        // Cycle host mode
        hostMode = hostMode === 'wireframe' ? 'solid' : (hostMode === 'solid' ? 'hidden' : 'wireframe');
        selHostMode.value = hostMode;
        updateMeshVisibilities();
        updateUI();
      } else if (key === 'f' || key === 'F') {
        fibersOnly = !fibersOnly;
        chkFibersOnly.checked = fibersOnly;
        updateMeshVisibilities();
        updateUI();
      } else if (key === 'b' || key === 'B') {
        ballMode = ballMode === 'wireframe' ? 'solid' : (ballMode === 'solid' ? 'hidden' : 'wireframe');
        selBallMode.value = ballMode;
        updateMeshVisibilities();
        updateUI();
      } else if (key === 'o' || key === 'O') {
        hostOpacity = hostOpacity <= 0.26 ? 1.0 : hostOpacity - 0.25;
        sliderHostOpacity.value = String(hostOpacity);
        lblHostOpacity.textContent = hostOpacity.toFixed(2);
        updateMeshVisibilities();
      } else if (key === 'e' || key === 'E') {
        hostEdges = !hostEdges;
        chkHostEdges.checked = hostEdges;
        updateMeshVisibilities();
      } else if (key === 's' || key === 'S') {
        takeSnapshot();
      } else if (key === 'd' || key === 'D') {
        drawer.classList.toggle('collapsed');
        setTimeout(onWindowResize, 220);
      }
    });

    // Expose for testing and external automation
    window.__viewer = {
      getCamera: () => activeCamera,
      getControls: () => controls,
      getFrame: () => currentFrame,
      isPlaying: () => isPlaying,
      updateFrame: updateFrame,
      applyPreset: applyPreset,
      play: play,
      pause: pause,
      togglePlay: togglePlay,
    };
  }
})();
