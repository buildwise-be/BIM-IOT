import type { IoTDevice } from "../domain/IfcIoTLinker";

export class DeviceMenu {
  private detailsDiv: HTMLDivElement;
  private menu: HTMLDivElement;
  private menuBody: HTMLDivElement;
  private container: HTMLElement;
  private isCollapsed = false;
  private collapseButton: HTMLButtonElement;

  constructor(
    container: HTMLElement,
    devices: IoTDevice[],
    onSelect: (device: IoTDevice) => void
  ) {
    this.container = container;

    this.menu = document.createElement("div");
    this.menu.className = "device-menu";

    const header = document.createElement("div");
    header.className = "device-menu-header";

    const title = document.createElement("h3");
    title.className = "device-menu-title";
    title.textContent = "IoT Devices";

    const actions = document.createElement("div");
    actions.className = "device-menu-actions";

    this.collapseButton = document.createElement("button");
    this.collapseButton.className = "device-menu-action";
    this.collapseButton.type = "button";
    this.collapseButton.title = "Toggle menu";
    this.collapseButton.textContent = "–";
    this.collapseButton.addEventListener("click", (event) => {
      event.stopPropagation();
      this.toggleCollapsed();
    });

    actions.appendChild(this.collapseButton);
    header.appendChild(title);
    header.appendChild(actions);
    this.menu.appendChild(header);

    this.menuBody = document.createElement("div");
    this.menuBody.className = "device-menu-body";

    devices.forEach((device) => {
      const button = document.createElement("button");
      button.textContent = `${device.id} (${device.type})`;
      button.onclick = () => onSelect(device);
      this.menuBody.appendChild(button);
    });

    this.detailsDiv = document.createElement("div");
    this.detailsDiv.className = "device-details";
    this.menuBody.appendChild(this.detailsDiv);

    this.menu.appendChild(this.menuBody);
    container.appendChild(this.menu);

    this.enableDrag(header);
  }

  setDetails(details: string[]) {
    this.detailsDiv.innerHTML = "<h4>IFC Elements:</h4>";
    details.forEach(detail => {
      const p = document.createElement("p");
      p.textContent = detail;
      this.detailsDiv.appendChild(p);
    });
  }

  private toggleCollapsed() {
    this.isCollapsed = !this.isCollapsed;
    if (this.isCollapsed) {
      this.menu.classList.add("collapsed");
      this.collapseButton.textContent = "+";
    } else {
      this.menu.classList.remove("collapsed");
      this.collapseButton.textContent = "–";
    }
  }

  private enableDrag(handle: HTMLElement) {
    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;
    let activePointerId: number | null = null;

    const onPointerMove = (event: PointerEvent) => {
      if (!isDragging) return;
      const containerRect = this.container.getBoundingClientRect();
      const menuRect = this.menu.getBoundingClientRect();

      let nextLeft = event.clientX - containerRect.left - offsetX;
      let nextTop = event.clientY - containerRect.top - offsetY;

      const maxLeft = Math.max(0, containerRect.width - menuRect.width);
      const maxTop = Math.max(0, containerRect.height - menuRect.height);

      nextLeft = Math.min(Math.max(0, nextLeft), maxLeft);
      nextTop = Math.min(Math.max(0, nextTop), maxTop);

      this.menu.style.left = `${nextLeft}px`;
      this.menu.style.top = `${nextTop}px`;
    };

    const onPointerUp = () => {
      if (!isDragging) return;
      isDragging = false;
      if (activePointerId !== null) {
        handle.releasePointerCapture?.(activePointerId);
      }
      activePointerId = null;
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
    };

    handle.addEventListener("pointerdown", (event) => {
      if ((event.target as HTMLElement).closest(".device-menu-action")) return;
      isDragging = true;
      activePointerId = event.pointerId;

      const menuRect = this.menu.getBoundingClientRect();
      offsetX = event.clientX - menuRect.left;
      offsetY = event.clientY - menuRect.top;

      handle.setPointerCapture?.(event.pointerId);
      document.addEventListener("pointermove", onPointerMove);
      document.addEventListener("pointerup", onPointerUp);
    });
  }
}
