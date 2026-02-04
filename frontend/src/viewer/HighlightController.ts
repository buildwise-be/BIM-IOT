import * as THREE from "three";
import * as FRAGS from "@thatopen/fragments";
import { FragmentLoader } from "./FragmentLoader";

export class HighlightController {
  private loader: FragmentLoader;
  private queue: Promise<void> = Promise.resolve();
  private materialState = new WeakMap<THREE.Material, { opacity: number; transparent: boolean }>();

  constructor(loader: FragmentLoader) {
    this.loader = loader;
  }

  async runExclusive(task: () => Promise<void>) {
    const run = this.queue.then(task, task);
    this.queue = run.catch(() => undefined);
    return run;
  }

  async resetAllHighlights() {
    if (!this.loader.fragments) return;
    for (const model of this.loader.fragments.list.values()) {
      this.restoreModelOpacity(model);
    }
    await this.loader.fragments.resetHighlight();
    await this.loader.fragments.core.update(true);
  }

  private applyModelOpacity(model: any, opacity: number) {
    if (!model?.object) return;
    model.object.traverse((obj: THREE.Object3D) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.material) return;
      if (Array.isArray(mesh.material)) {
        for (const mat of mesh.material) {
          this.applyMaterialOpacity(mat, opacity);
        }
      } else {
        this.applyMaterialOpacity(mesh.material, opacity);
      }
    });
  }

  private restoreModelOpacity(model: any) {
    if (!model?.object) return;
    model.object.traverse((obj: THREE.Object3D) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.material) return;
      if (Array.isArray(mesh.material)) {
        for (const mat of mesh.material) {
          this.restoreMaterialOpacity(mat);
        }
      } else {
        this.restoreMaterialOpacity(mesh.material);
      }
    });
  }

  private restoreOpacityForExpressIDs(model: any, expressIDs: number[]) {
    if (!model?.object || expressIDs.length === 0) return;
    const idSet = new Set(expressIDs);
    model.object.traverse((obj: THREE.Object3D) => {
      const mesh = obj as THREE.Mesh;
      const geometry = mesh.geometry as THREE.BufferGeometry | undefined;
      if (!geometry || !mesh.material) return;

      const attr = this.getIdAttribute(geometry);
      if (!attr) return;
      if (!this.attributeContainsAnyId(attr, idSet)) return;

      if (Array.isArray(mesh.material)) {
        for (const mat of mesh.material) {
          this.restoreMaterialOpacity(mat);
        }
      } else {
        this.restoreMaterialOpacity(mesh.material);
      }
    });
  }

  private applyOpacityForExpressIDs(model: any, expressIDs: number[], opacity: number) {
    if (!model?.object || expressIDs.length === 0) return;
    const idSet = new Set(expressIDs);
    model.object.traverse((obj: THREE.Object3D) => {
      const mesh = obj as THREE.Mesh;
      const geometry = mesh.geometry as THREE.BufferGeometry | undefined;
      if (!geometry || !mesh.material) return;

      const attr = this.getIdAttribute(geometry);
      if (!attr) return;
      if (!this.attributeContainsAnyId(attr, idSet)) return;

      if (Array.isArray(mesh.material)) {
        for (const mat of mesh.material) {
          this.applyMaterialOpacity(mat, opacity);
        }
      } else {
        this.applyMaterialOpacity(mesh.material, opacity);
      }
    });
  }

  private getIdAttribute(geometry: THREE.BufferGeometry): THREE.BufferAttribute | undefined {
    const candidates = Object.keys(geometry.attributes).filter((name) =>
      /itemid|localid|expressid/i.test(name),
    );
    const attrName = candidates[0];
    if (!attrName) return undefined;
    return geometry.getAttribute(attrName);
  }

  private attributeContainsAnyId(
    attribute: THREE.BufferAttribute,
    idSet: Set<number>,
  ): boolean {
    const array = attribute.array as ArrayLike<number>;
    for (let i = 0; i < array.length; i++) {
      if (idSet.has(array[i] as number)) return true;
    }
    return false;
  }

  private applyMaterialOpacity(material: THREE.Material, opacity: number) {
    if (!this.materialState.has(material)) {
      this.materialState.set(material, {
        opacity: material.opacity,
        transparent: material.transparent,
      });
    }
    material.transparent = opacity < 1 ? true : material.transparent;
    material.opacity = opacity;
    material.needsUpdate = true;
  }

  private restoreMaterialOpacity(material: THREE.Material) {
    const saved = this.materialState.get(material);
    if (!saved) return;
    material.opacity = saved.opacity;
    material.transparent = saved.transparent;
    material.needsUpdate = true;
  }

  async highlightByExpressIDs(modelID: number, expressIDs: number[]) {
    if (!this.loader.fragments) return;
    await this.loader.fragments.resetHighlight();

    // Dim everything first.
    await this.dimAllModels(0.5);

    const modelIdMap = { [modelID]: new Set(expressIDs) };
    const model = this.loader.fragments.list.get(modelID);
    const color = new THREE.Color("red");
    console.log(model)
    await this.loader.fragments.highlight(
      {
        color,
        renderedFaces: FRAGS.RenderedFaces.ONE,
        opacity: 1,
        transparent: false,
        preserveOriginalMaterial: false,
      },
      modelIdMap,
    );
    if (model) {
      // Force selected elements back to full opacity.
      this.applyOpacityForExpressIDs(model, expressIDs, 1);
    }

    await this.loader.fragments.core.update(true);
  }

  private async dimAllModels(opacity: number) {
    if (!this.loader.fragments) return;
    const gray = new THREE.Color("gray");
    for (const model of this.loader.fragments.list.values()) {
      if (!model) continue;
      const ids = await model.getLocalIds();
      const modelIdMap = { [model.modelId]: new Set(ids) };
      await this.loader.fragments.highlight(
        {
          color: gray,
          renderedFaces: FRAGS.RenderedFaces.ONE,
          opacity,
          transparent: true,
        },
        modelIdMap,
      );
    }
  }
}
