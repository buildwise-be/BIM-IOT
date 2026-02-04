import * as OBC from "@thatopen/components";
import * as FRAGS from "@thatopen/fragments";
import * as THREE from "three";
import { FragmentLoader } from "./FragmentLoader";

export class IfcPickController {
  private components: OBC.Components;
  private world: any;
  private loader: FragmentLoader;
  private onPick?: (payload: { expressID: number; guid?: string; ifcType?: string; name?: string }) => Promise<boolean> | boolean;

  constructor(
    components: OBC.Components,
    world: any,
    container: HTMLElement,
    loader: FragmentLoader,
    onPick?: (payload: { expressID: number; guid?: string; ifcType?: string; name?: string }) => Promise<boolean> | boolean
  ) {
    this.components = components;
    this.world = world;
    this.loader = loader;
    this.onPick = onPick;

    const raycasters = components.get(OBC.Raycasters);
    const caster = raycasters.get(world);

    console.log("IfcPickController ready");

    container.addEventListener("dblclick", async () => {
      const result = await caster.castRay();
      if (!result) return;

      const expressID = result.localId;
      if (!expressID) return;

      try {
        const modelId = result.fragments.modelId;
        const modelIdMap = { [modelId]: new Set([result.localId]) };
        const model = loader.fragments.list.get(modelId)!;
        const [data] = await model.getItemsData([...modelIdMap[modelId]]);

        const guid = data?._guid?.value;
        const ifcType = data?._category?.value;
        const name = data?.Name?.value;
        console.log("Element Pick: ", { name, guid, ifcType });
        console.log(  model);

        //hightlightM = components.get(OBC.highlightController);

        //console.log( await model)
        console.log( await loader.fragments)
        console.log( await loader)


        let handled = false;
        if (this.onPick) {
          handled = await this.onPick({ expressID, guid, ifcType, name });
        }

        if (!handled) {
          await loader.fragments.resetHighlight();
          //await model.setOpacity( [expressID], 0.1)
          await this.dimAllMeshes(0.5);
          const color = new THREE.Color("red");
          
          await loader.fragments.highlight(
            {
              color,
              renderedFaces: FRAGS.RenderedFaces.ONE,
              opacity: 1,
              transparent: false,
            },
            modelIdMap,
          );
          
          await loader.fragments.core.update(true);
  
        }
      } catch (error) {
        console.error("Error:", error);
      }
    });
  }

  private async dimAllMeshes(opacity: number) {
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
