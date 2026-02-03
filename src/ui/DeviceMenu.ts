import type { IoTDevice } from "../domain/IfcIoTLinker";

export class DeviceMenu {
  private detailsDiv: HTMLDivElement;

  constructor(
    container: HTMLElement,
    devices: IoTDevice[],
    onSelect: (device: IoTDevice) => void
  ) {
    // Create a menu element
    const menu = document.createElement("div");
    menu.className = "device-menu";

    const title = document.createElement("h3");
    title.textContent = "IoT Devices";
    menu.appendChild(title);

    devices.forEach((device) => {
      const button = document.createElement("button");
      button.textContent = `${device.id} (${device.type})`;
      button.onclick = () => onSelect(device);
      menu.appendChild(button);
    });

    // Add details section
    this.detailsDiv = document.createElement("div");
    this.detailsDiv.className = "device-details";
    menu.appendChild(this.detailsDiv);

    // Append to device-list instead of body
    const deviceList = document.getElementById("device-list");
    if (deviceList) {
      deviceList.appendChild(menu);
    } else {
      container.appendChild(menu);
    }
  }

  setDetails(details: string[]) {
    this.detailsDiv.innerHTML = "<h4>IFC Elements:</h4>";
    details.forEach(detail => {
      const p = document.createElement("p");
      p.textContent = detail;
      this.detailsDiv.appendChild(p);
    });
  }
}