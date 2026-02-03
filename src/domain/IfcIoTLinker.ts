export type IoTDevice = {
  id: string;
  type: string;
  ifcGuids: string[];
};

export class IfcIoTLinker {
  private devices: IoTDevice[] = [];
  private guidToExpressId: Map<string, number> = new Map();

  constructor(mapping: { devices: Record<string, { type: string; ifcGuids: string[] }> }, guidMap: Map<string, number>) {
    this.devices = Object.entries(mapping.devices).map(([id, data]) => ({
      id,
      type: data.type,
      ifcGuids: data.ifcGuids,
    }));
    this.guidToExpressId = guidMap;
  }

  getDevices(): IoTDevice[] {
    return this.devices;
  }

  getGuidsForDevice(deviceId: string): string[] {
    const device = this.devices.find(d => d.id === deviceId);
    return device ? device.ifcGuids : [];
  }

  async getExpressIdFromGuid(modelID: number, guid: string): Promise<number | undefined> {
    return this.guidToExpressId.get(guid);
  }
}