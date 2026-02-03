import * as OBC from "@thatopen/components";
import * as THREE from "three";

export class ViewerFactory {
  static create(container: HTMLElement) {
    const components = new OBC.Components();

    const worlds = components.get(OBC.Worlds);

    
    // 🔥 Types génériques sur une seule ligne
    const world = worlds.create<OBC.SimpleScene, OBC.SimpleCamera, OBC.SimpleRenderer>();

    world.scene = new OBC.SimpleScene(components);
    world.renderer = new OBC.SimpleRenderer(components, container);
    world.camera = new OBC.SimpleCamera(components);

   const grids = components.get(OBC.Grids);
// create the grid for the world we set
const grid = grids.create(world);

    components.init();

    world.camera.controls.setLookAt(12, 6, 8, 0, 0, -10);
    world.scene.setup();

    const clipper = components.get(OBC.Clipper);
    clipper.enabled = true;

    return { components, world };
  }
}