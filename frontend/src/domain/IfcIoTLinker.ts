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
  }

  updateMapping(mapping: { devices?: Record<string, { type: string; ifcGuids: string[]; connector?: { type: string; deviceId?: string; telemetryKey?: string } }> }) {
    this.devices = this.buildDevices(mapping);
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

  private buildDevices(mapping: { devices?: Record<string, { type: string; ifcGuids: string[]; connector?: { type: string; deviceId?: string; telemetryKey?: string } }> }): IoTDevice[] {
    const source = mapping?.devices || {};
    return Object.entries(source).map(([id, data]) => ({
      id,
      type: data.type,
      ifcGuids: data.ifcGuids,
      connector: data.connector,
    }));
  }
}
