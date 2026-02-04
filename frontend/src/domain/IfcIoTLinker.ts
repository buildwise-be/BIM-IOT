export type IoTDevice = {
  id: string;
  type: string;
  ifcGuids: string[];
  connector?: {
    type: string;
    deviceId?: string;
    telemetryKey?: string;
  };
};

export class IfcIoTLinker {
  private devices: IoTDevice[] = [];
  private guidToExpressId: Map<string, number> = new Map();
  private guidToDevice: Map<string, IoTDevice> = new Map();

  constructor(
    mapping: {
      devices?: Record<
        string,
        { type: string; ifcGuids: string[]; connector?: { type: string; deviceId?: string; telemetryKey?: string } }
      >;
    },
    guidMap: Map<string, number>
  ) {
    this.devices = this.buildDevices(mapping);
    this.guidToExpressId = guidMap;
    this.guidToDevice = this.buildGuidToDeviceMap(this.devices);
  }

  updateMapping(mapping: { devices?: Record<string, { type: string; ifcGuids: string[]; connector?: { type: string; deviceId?: string; telemetryKey?: string } }> }) {
    this.devices = this.buildDevices(mapping);
    this.guidToDevice = this.buildGuidToDeviceMap(this.devices);
  }

  getDevices(): IoTDevice[] {
    return this.devices;
  }

  getDeviceById(deviceId: string): IoTDevice | undefined {
    return this.devices.find((device) => device.id === deviceId);
  }

  getDeviceByGuid(guid: string): IoTDevice | undefined {
    return this.guidToDevice.get(guid);
  }

  getGuidsForDevice(deviceId: string): string[] {
    const device = this.devices.find(d => d.id === deviceId);
    return device ? device.ifcGuids : [];
  }

  async getExpressIdFromGuid(modelID: number, guid: string): Promise<number | undefined> {
    return this.guidToExpressId.get(guid);
  }

  private buildDevices(mapping: { devices?: Record<string, { type: string; ifcGuids: string[]; connector?: { type: string; deviceId?: string; telemetryKey?: string } }> }): IoTDevice[] {
    const source = mapping?.devices || {};
    return Object.entries(source).map(([id, data]) => ({
      id,
      type: data.type,
      ifcGuids: data.ifcGuids,
      connector: data.connector,
    }));
  }

  private buildGuidToDeviceMap(devices: IoTDevice[]): Map<string, IoTDevice> {
    const map = new Map<string, IoTDevice>();
    for (const device of devices) {
      for (const guid of device.ifcGuids || []) {
        if (!map.has(guid)) {
          map.set(guid, device);
        }
      }
    }
    return map;
  }
}
