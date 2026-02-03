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
  private apiBaseUrl = "http://localhost:8000";

  private isSelectionActive(token: number): boolean {
    return token === this.selectionToken;
  }

  async init() {
    const container = document.getElementById("viewer");
    if (!container) throw new Error("Viewer container not found");

    const viewer = ViewerFactory.create(container);
    this.components = viewer.components;
    this.world = viewer.world;

    this.initSplitLayout();

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
    if ((devicesData as any).backend?.baseUrl) {
      this.apiBaseUrl = (devicesData as any).backend.baseUrl;
    }

    this.initDeviceMenu();
    
    console.log("✅ App ready – IFC picking SAFE");
  }

  private initSplitLayout(): void {
    const topContainer = document.getElementById("top-container");
    const bottomContainer = document.getElementById("iot-data");
    const splitter = document.getElementById("splitter");
    if (!topContainer || !bottomContainer || !splitter) return;

    const minTop = 240;
    const minBottom = 140;

    const setHeights = (topHeight: number) => {
      const total = document.body.clientHeight;
      const splitterHeight = splitter.getBoundingClientRect().height || 8;
      const maxTop = total - splitterHeight - minBottom;
      const clampedTop = Math.min(Math.max(minTop, topHeight), maxTop);
      const bottomHeight = Math.max(minBottom, total - splitterHeight - clampedTop);

      topContainer.style.height = `${clampedTop}px`;
      bottomContainer.style.height = `${bottomHeight}px`;
    };

    const initialTop = topContainer.getBoundingClientRect().height || Math.floor(window.innerHeight * 0.7);
    setHeights(initialTop);

    let isDragging = false;
    let activePointerId: number | null = null;

    const onMove = (event: PointerEvent) => {
      if (!isDragging) return;
      const top = event.clientY;
      setHeights(top);
    };

    const onUp = () => {
      if (!isDragging) return;
      isDragging = false;
      splitter.classList.remove("dragging");
      if (activePointerId !== null) {
        splitter.releasePointerCapture?.(activePointerId);
      }
      activePointerId = null;
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    };

    splitter.addEventListener("pointerdown", (event) => {
      isDragging = true;
      activePointerId = event.pointerId;
      splitter.classList.add("dragging");
      splitter.setPointerCapture?.(event.pointerId);
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    });

    window.addEventListener("resize", () => {
      const topHeight = topContainer.getBoundingClientRect().height;
      setHeights(topHeight);
    });
  }

  private initDeviceMenu(): void {
    const viewerContainer = document.getElementById("viewer") || document.body;
    this.deviceMenu = new DeviceMenu(
      viewerContainer,
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
      await this.displayIoTData(device);
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

  private async displayIoTData(device: any): Promise<void> {
    const iotDataDiv = document.getElementById("iot-data");
    if (!iotDataDiv) return;

    // Clear previous content
    iotDataDiv.innerHTML = `<h4>IoT Data for ${device.id}</h4>`;

    const loading = document.createElement("p");
    loading.textContent = "Loading telemetry...";
    iotDataDiv.appendChild(loading);

    const telemetryKey = device.connector?.telemetryKey || device.type;
    const telemetryUrl = `${this.apiBaseUrl}/devices/${encodeURIComponent(device.id)}/telemetry?key=${encodeURIComponent(
      telemetryKey
    )}&limit=24`;

    let points: Array<{ ts: number; value: number }> = [];
    try {
      const response = await fetch(telemetryUrl);
      if (!response.ok) {
        throw new Error(`Telemetry fetch failed: ${response.status}`);
      }
      const payload = await response.json();
      points = Array.isArray(payload.points) ? payload.points : [];
    } catch (error) {
      loading.textContent = "No telemetry data available.";
      return;
    }

    loading.remove();

    if (points.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No telemetry data available.";
      iotDataDiv.appendChild(empty);
      return;
    }

    const latestPoint = points[points.length - 1];
    const lastTelemetry = document.createElement("p");
    lastTelemetry.textContent = `Last value: ${latestPoint.value} - Updated: ${new Date(
      latestPoint.ts
    ).toLocaleTimeString()}`;
    iotDataDiv.appendChild(lastTelemetry);

    // Create canvas for chart
    const canvas = document.createElement("canvas");
    canvas.height = 400;
    canvas.style.width = "100%";
    canvas.style.height = "90px";
    iotDataDiv.appendChild(canvas);

    const labels = points.map((point) =>
      new Date(point.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    );
    const data = points.map((point) => point.value);

    // Create chart
    new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label:
              device.type === "temperature"
                ? "Temperature (°C)"
                : device.type === "humidity"
                ? "Humidity (%)"
                : "Value",
            data: data,
            borderColor: "rgb(75, 192, 192)",
            backgroundColor: "rgba(75, 192, 192, 0.2)",
            tension: 0.5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            ticks: {
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 6
            },
            grid: {
              display: false
            }
          },
          y: {
            beginAtZero: false,
            ticks: {
              maxTicksLimit: 4
            }
          }
        }
      }
    });
  }
}
