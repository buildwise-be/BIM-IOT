import * as OBC from "@thatopen/components";
import * as FRAGS from "@thatopen/fragments";

export const ifcRoots: THREE.Object3D[] = [];

export class FragmentLoader {
  private components: OBC.Components;
  private world: any;
  public fragmentsGroup: any = null;
  public ifcMetadata: Map<number, any> = new Map(); // 🔥 Stocker les métadonnées
  public fragments : any=null;

  constructor(viewer: any) {
    this.components = viewer.components;
    this.world = viewer.world;
  }

  async load(url: string): Promise<void> {
    const { components, world } = this;

    this.fragments = components.get(OBC.FragmentsManager);
    const ifcLoader = components.get(OBC.IfcLoader);

    this.fragments.settings = {
      enableBVH: false
    };

    await this.fragments.init("/worker/fragment-worker.mjs");

    await ifcLoader.setup({
      autoSetWasm: false,
      wasm: { path: "/wasm/", absolute: true }
    });

    this.fragments.list.onItemSet.add(({ value: model }) => {
      model.useCamera(world.camera.three);
      world.scene.three.add(model.object);
      ifcRoots.push(model.object);
      
      this.fragmentsGroup = model;
      
      // 🔥 Essayer d'extraire les métadonnées IFC si disponibles
      console.log("📦 Model structure:", {
        keys: Object.keys(model),
        ifcMetadata: (model as any).ifcMetadata,
        properties: (model as any).properties,
        data: (model as any).data
      });
      
      this.fragments.core.update(true);
      console.log("📦 Model loaded");
    });

    const buffer = new Uint8Array(
      await (await fetch(url)).arrayBuffer()
    );

    const loadedModel = await ifcLoader.load(buffer, false, "model");
    
    // 🔥 Essayer d'accéder aux propriétés du modèle chargé
    console.log("📦 Loaded model:", loadedModel);
    console.log("📦 Loaded model keys:", Object.keys(loadedModel));

    console.log("✅ IFC loaded as fragments");
  }
}