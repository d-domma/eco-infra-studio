import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { BuildingSpec } from '../models';

export type ViewMode = 'exterior' | 'interior' | 'cutaway';

export interface CameraView {
  position: number[];
  target: number[];
}

@Component({
  selector: 'app-viewer',
  template: `<canvas #canvas class="viewer"></canvas>`,
  styles: [
    `
      :host {
        display: block;
        height: 100%;
        min-height: 420px;
      }
    `,
  ],
})
export class ViewerComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('canvas', { static: true }) canvas!: ElementRef<HTMLCanvasElement>;
  @Input() spec?: BuildingSpec;
  @Input() lotWidth = 18;
  @Input() lotDepth = 32;
  @Input() glbUrl?: string | null;
  @Input() viewMode: ViewMode = 'exterior';
  @Input() views: Record<string, CameraView> | null = null;

  private renderer?: THREE.WebGLRenderer;
  private scene?: THREE.Scene;
  private camera?: THREE.PerspectiveCamera;
  private controls?: OrbitControls;
  private root?: THREE.Object3D;
  private frame = 0;
  private resizeObs?: ResizeObserver;
  private loadedUrl?: string | null;

  ngAfterViewInit() {
    const canvas = this.canvas.nativeElement;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    this.renderer = renderer;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#cfdcc8');
    this.scene = scene;

    const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 250);
    camera.position.set(24, 16, 28);
    this.camera = camera;

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.enablePan = true;
    controls.minDistance = 0.4;
    controls.maxDistance = 80;
    controls.target.set(0, 1.4, 0);
    this.controls = controls;

    scene.add(new THREE.HemisphereLight(0xc5d6ee, 0x3e4a30, 0.62));
    const sun = new THREE.DirectionalLight(0xfff0d8, 2.6);
    sun.position.set(16, 26, 10);
    scene.add(sun);
    const fill = new THREE.DirectionalLight(0xd5e2ff, 0.7);
    fill.position.set(-14, 10, -8);
    scene.add(fill);

    this.resize();
    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(canvas.parentElement || canvas);
    this.ensureModel();
    const tick = () => {
      this.frame = requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    };
    tick();
  }

  ngOnChanges(changes: SimpleChanges) {
    if (!this.scene) return;
    if (changes['glbUrl'] && this.glbUrl !== this.loadedUrl) {
      this.ensureModel();
      return;
    }
    if (changes['viewMode'] || changes['views']) this.applyView();
  }

  ngOnDestroy() {
    cancelAnimationFrame(this.frame);
    this.resizeObs?.disconnect();
    this.controls?.dispose();
    this.renderer?.dispose();
  }

  private resize() {
    if (!this.renderer || !this.camera) return;
    const canvas = this.canvas.nativeElement;
    const w = canvas.clientWidth || 640;
    const h = canvas.clientHeight || 420;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private ensureModel() {
    if (!this.scene) return;
    if (this.root) {
      this.scene.remove(this.root);
      this.root = undefined;
    }
    this.loadedUrl = this.glbUrl;
    if (this.glbUrl) {
      const loader = new GLTFLoader();
      loader.load(
        this.glbUrl,
        (gltf) => {
          this.tuneImportedModel(gltf.scene);
          this.root = gltf.scene;
          this.scene?.add(gltf.scene);
          this.applyView();
        },
        undefined,
        () => this.drawProcedural(),
      );
      return;
    }
    this.drawProcedural();
  }

  private applyView() {
    if (!this.camera || !this.controls) return;
    this.root?.traverse((obj) => {
      if (obj.name.startsWith('CUTAWAY_')) {
        obj.visible = this.viewMode !== 'cutaway';
      }
    });
    const named = this.views?.[this.viewMode];
    if (named?.position?.length === 3 && named?.target?.length === 3) {
      this.camera.position.set(named.position[0], named.position[1], named.position[2]);
      this.controls.target.set(named.target[0], named.target[1], named.target[2]);
      this.camera.near = this.viewMode === 'interior' ? 0.08 : 0.2;
      this.camera.fov = this.viewMode === 'interior' ? 55 : 42;
      this.camera.updateProjectionMatrix();
      this.controls.update();
      return;
    }
    if (this.root) this.frameObject(this.root);
  }

  private frameObject(object: THREE.Object3D) {
    if (!this.camera || !this.controls) return;
    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3()).length();
    const center = box.getCenter(new THREE.Vector3());
    this.controls.target.copy(center);
    const offset =
      this.viewMode === 'interior'
        ? new THREE.Vector3(1.2, 1.5, 1.6)
        : this.viewMode === 'cutaway'
          ? new THREE.Vector3(0.2, 1.8, size * 0.28)
          : new THREE.Vector3(size * 0.45, size * 0.32, size * 0.55);
    this.camera.position.copy(center).add(offset);
    this.camera.near = 0.1;
    this.camera.far = Math.max(80, size * 10);
    this.camera.updateProjectionMatrix();
  }

  /** Blender exports its sun at ~1500 lux, which clips every lit face to white. */
  private tuneImportedModel(root: THREE.Object3D) {
    root.traverse((obj) => {
      const light = obj as THREE.Light;
      if (light.isLight && light.intensity > 8) {
        light.intensity = 0;
        light.visible = false;
      }
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const raw of materials) {
        const mat = raw as THREE.MeshPhysicalMaterial;
        if (mat.transmission > 0.01) {
          mat.transmission = 0;
          mat.thickness = 0;
          mat.transparent = false;
          mat.opacity = 1;
          mat.roughness = Math.min(mat.roughness ?? 0.15, 0.18);
          mat.metalness = Math.max(mat.metalness ?? 0, 0.04);
        }
        mat.needsUpdate = true;
      }
    });
  }

  private drawProcedural() {
    if (!this.scene) return;
    const spec = this.spec;
    const lotW = this.lotWidth;
    const lotD = this.lotDepth;
    const group = new THREE.Group();
    const grass = new THREE.MeshLambertMaterial({ color: 0x5d8a4a });
    const ground = new THREE.Mesh(new THREE.BoxGeometry(lotW, 0.16, lotD), grass);
    ground.position.y = -0.08;
    group.add(ground);
    if (spec) {
      const h = spec.stories * spec.story_height_m;
      const building = new THREE.Mesh(
        new THREE.BoxGeometry(spec.width_m, h, spec.depth_m),
        new THREE.MeshLambertMaterial({ color: 0xc48a4a }),
      );
      building.position.set(
        -lotW / 2 + spec.setback_side_m + spec.width_m / 2,
        h / 2,
        -lotD / 2 + spec.setback_front_m + spec.depth_m / 2,
      );
      group.add(building);
    }
    this.root = group;
    this.scene.add(group);
    this.applyView();
  }
}
