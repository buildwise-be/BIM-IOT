
import * as OBC from "@thatopen/components";
import * as FRAGS from "@thatopen/fragments";
import * as THREE from "three";
import { FragmentLoader } from "./FragmentLoader";

export class IfcPickController {
  private components: OBC.Components;
  private world: any;
  private loader: FragmentLoader;

  constructor(
    components: OBC.Components,
    world: any,
    container: HTMLElement,
    loader: FragmentLoader
  ) {
    this.components = components;
    this.world = world;
    this.loader = loader;

    const raycasters = components.get(OBC.Raycasters);
    const caster = raycasters.get(world);

    console.log("✅ IfcPickController ready");

    container.addEventListener("dblclick", async () => { // 🔥 Double-clic pour éviter conflits
      const result = await caster.castRay();
      
      if (!result) return;

      const fragmentsGroup = result.fragments;
      const expressID = result.localId;
      const itemId = (result as any).itemId;

      console.log("🎯 Clicked:", { expressID, itemId });

      if (!expressID) return;

      try {
        // 🔥 SOLUTION FINALE: Utiliser l'itemsManager avec les données
        
        console.log("🔍 Getting item data...");
        
        

        // 🔥 Vérifier si dataManager a une méthode pour obtenir le GUID
        
        const modelId = result.fragments.modelId;
        const modelIdMap = { [modelId]: new Set([result.localId]) };
        console.log("result.fragments.modelId : ",result.fragments.modelId);
        console.log("modelIdMap : ",modelIdMap);


        const model = loader.fragments.list.get(modelId)!;
        const [data] = await model.getItemsData([...modelIdMap[modelId]]);
        console.log(data)
        console.log(model.getItemsData)

        // 🔥 Essayer les méthodes qui semblent prometteuses
        
         
        try {
          // Peut-être que les threads sont maintenant prêts?
          const guids = data._guid.value;
          
          const ifcType = data._category.value;
          const IfcElementName = data.Name.value;
          console.log("🧩 IFC ELEMENT (basic):");
          console.log(" • IFC Name:", IfcElementName);
          console.log(" • IFC type:", ifcType);
          console.log(" • ExpressID:", expressID);
          console.log(" • GUID:", guids);
          console.log(" • ItemID:", itemId);
          //console.log(FRAGS);
          //console.log(FRAGS.Attribute());
          const color = new THREE.Color("purple");
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

          
        } catch (e) {
          console.log("⚠️ Erreur log :", e);
        }
        

        

        
        

      } catch (error) {
        console.error("❌ Error:", error);
      }
    });
  }
}