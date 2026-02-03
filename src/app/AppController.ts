import { ViewerFactory } from "../viewer/ViewerFactory";
import { FragmentLoader } from "../viewer/FragmentLoader";
import { IfcPickController } from "../viewer/IfcPickController";
import { HighlightController } from "../viewer/HighlightController";
import { DeviceMenu } from "../ui/DeviceMenu";
import { IfcIoTLinker } from "../domain/IfcIoTLinker";
import devicesData from "../data/devices.ifc.json";
import * as OBC from "@thatopen/components";
import Chart from 'chart.js/auto';
import * as THREE from "three";

export class AppController {
  private components: any;
  private world: any;
  private loader: FragmentLoader;
  private ifcIoTLinker: IfcIoTLinker;
  private highlightController: HighlightController;
  private modelID: number;
  private deviceMenu: DeviceMenu;
  private selectionToken = 0;

  private isSelectionActive(token: number): boolean {
    return token === this.selectionToken;
  }

  async init() {
    const container = document.getElementById("viewer");
    if (!container) throw new Error("Viewer container not found");

    const viewer = ViewerFactory.create(container);
    this.components = viewer.components;
    this.world = viewer.world;

    // Handle container resize to maintain aspect ratio
    const resizeObserver = new ResizeObserver(() => {
      const rect = container.getBoundingClientRect();
      this.world.renderer.three.setSize(rect.width, rect.height);
      this.world.camera.three.aspect = rect.width / rect.height;
      this.world.camera.three.updateProjectionMatrix();
    });
    resizeObserver.observe(container);

    // Setup IFC loader
    const ifcLoader = this.components.get(OBC.IfcLoader);
    await ifcLoader.setup({});
    (this.world as any).IFC = { loader: ifcLoader };

    this.loader = new FragmentLoader(viewer);
    await this.loader.load("/model.ifc");

    // 🔥 Passer le loader ET le canvas
    const pickController = new IfcPickController(
      this.components,
      this.world,
      this.world.renderer.three.domElement,
      this.loader // 🔥 Passer le loader en dernier
    );

    this.highlightController = new HighlightController(this.loader);
    window.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      this.selectionToken++;
      this.highlightController.runExclusive(() => this.highlightController.resetAllHighlights());
    });

    // Create GUID to expressID mapping
    const guidMap = new Map<string, number>();
    const availableModels = Array.from(this.loader.fragments.list.keys());
    if (availableModels.length > 0) {
      const modelKey = availableModels[0];
      const model = this.loader.fragments.list.get(modelKey);
      if (model) {
        this.modelID = model.modelId;
        const itemsMap = await model.getItems();
        for (const [expressID, item] of itemsMap) {
          guidMap.set(item.guid, expressID);
        }
      }
    }

    // Load devices data
    this.ifcIoTLinker = new IfcIoTLinker(devicesData, guidMap);

    this.initDeviceMenu();
    
    console.log("✅ App ready – IFC picking SAFE");
  }

  private initDeviceMenu(): void {
    this.deviceMenu = new DeviceMenu(
      document.body,
      this.ifcIoTLinker.getDevices(),
      (device) => this.onDeviceSelected(device)
    );
  }

  private async onDeviceSelected(device: any): Promise<void> {
    console.log("onDeviceSelected", device);

    const token = ++this.selectionToken;
    const expressIDs: number[] = [];
    for (const guid of device.ifcGuids) {
      console.log("processing guid", guid);
      const expressID = await this.ifcIoTLinker.getExpressIdFromGuid(this.modelID, guid);
      if (expressID !== undefined) {
        expressIDs.push(expressID);
      }
    }

    if (!this.isSelectionActive(token)) return;

    if (expressIDs.length > 0) {
      await this.highlightController.runExclusive(async () => {
        //if (!this.isSelectionActive(token)) return;
        //await this.highlightController.resetAllHighlights();
        if (!this.isSelectionActive(token)) return;
        await this.highlightController.highlightByExpressIDs(this.modelID, expressIDs);
        //if (!this.isSelectionActive(token)) {
        //  await this.highlightController.resetAllHighlights();
        //}
      });
      if (!this.isSelectionActive(token)) return;
      await this.focusOnExpressIDs(expressIDs);

      // Get details for display
      const model = this.loader.fragments.list.get(this.modelID);
      const itemsMap = await model.getItems();
      const details: string[] = [];
      for (const expressID of expressIDs) {
        const item = itemsMap.get(expressID);
        if (item) {
          details.push(`GUID: ${item.guid}, Type: ${item.category}, Name: ${item.data.Name?.value || 'N/A'}`);
        }
      }
      if (!this.isSelectionActive(token)) return;
      this.deviceMenu.setDetails(details);

      // Display IoT data
      if (!this.isSelectionActive(token)) return;
      this.displayIoTData(device);
    }
  }

  private async focusOnExpressIDs(expressIDs: number[]): Promise<void> {
    if (!expressIDs.length) return;
    const model = this.loader.fragments.list.get(this.modelID);
    if (!model) return;

    const box = await model.getMergedBox(expressIDs);
    if (!box || box.isEmpty()) return;

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxSize = Math.max(size.x, size.y, size.z);

    const camera = this.world.camera.three as THREE.PerspectiveCamera | THREE.OrthographicCamera;
    const controls = this.world.camera.controls;
    if (!camera || !controls) return;

    let distance = maxSize;
    if ((camera as THREE.PerspectiveCamera).isPerspectiveCamera) {
      const fov = (camera as THREE.PerspectiveCamera).fov;
      distance = maxSize / (2 * Math.tan(THREE.MathUtils.degToRad(fov / 2)));
    }
    distance = distance * 1.2 + 0.5;

    const currentPos = new THREE.Vector3();
    const currentTarget = new THREE.Vector3();
    if (typeof controls.getPosition === "function") {
      controls.getPosition(currentPos);
    } else {
      currentPos.copy(camera.position);
    }
    if (typeof controls.getTarget === "function") {
      controls.getTarget(currentTarget);
    } else {
      currentTarget.set(0, 0, 0);
    }

    const dir = currentPos.clone().sub(currentTarget);
    if (dir.lengthSq() < 1e-6) dir.set(1, 1, 1);
    dir.normalize();

    const newPos = center.clone().add(dir.multiplyScalar(distance));
    controls.setLookAt(newPos.x, newPos.y, newPos.z, center.x, center.y, center.z, true);
  }

  private displayIoTData(device: any): void {
    const iotDataDiv = document.getElementById("iot-data");
    if (!iotDataDiv) return;

    // Clear previous content
    iotDataDiv.innerHTML = `<h4>IoT Data for ${device.id}</h4>`;

    // Show last telemetry
    let lastValue;
    if (device.type === "temperature") {
      lastValue = `${Math.round(Math.random() * 10 + 20)}°C`;
    } else if (device.type === "humidity") {
      lastValue = `${Math.round(Math.random() * 20 + 40)}%`;
    } else {
      lastValue = `${Math.random().toFixed(2)}`;
    }
    const lastTelemetry = document.createElement("p");
    lastTelemetry.textContent = `Last value: ${lastValue} - Updated: ${new Date().toLocaleTimeString()}`;
    iotDataDiv.appendChild(lastTelemetry);

    // Create canvas for chart
    const canvas = document.createElement("canvas");
    canvas.width = 400;
    canvas.height = 200;
    iotDataDiv.appendChild(canvas);

    // Generate historical data (last 24 hours, hourly)
    const labels = [];
    const data = [];
    const now = new Date();
    for (let i = 23; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 60 * 60 * 1000);
      labels.push(time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

      let value;
      if (device.type === "temperature") {
        value = Math.round((20 + Math.random() * 10 + Math.sin(i / 4) * 5) * 10) / 10; // 20-30°C with variation
      } else if (device.type === "humidity") {
        value = Math.round((40 + Math.random() * 20 + Math.cos(i / 6) * 10) * 10) / 10; // 40-60% with variation
      } else {
        value = Math.round((Math.random() * 100) * 10) / 10;
      }
      data.push(value);
    }

    // Create chart
    new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: device.type === "temperature" ? 'Temperature (°C)' : device.type === "humidity" ? 'Humidity (%)' : 'Value',
          data: data,
          borderColor: 'rgb(75, 192, 192)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
          tension: 0.1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: false
          }
        }
      }
    });
  }
}
