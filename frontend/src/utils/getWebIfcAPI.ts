export function getWebIfcAPI(ifcLoader: any): any {
  // Cas 1 — exposée directement
  if (ifcLoader?.ifcAPI?.GetLineIDsWithType) {
    return ifcLoader.ifcAPI;
  }

  // Cas 2 — via ifcManager
  if (ifcLoader?.ifcManager?.ifcAPI?.GetLineIDsWithType) {
    return ifcLoader.ifcManager.ifcAPI;
  }

  // Cas 3 — via ifcManager API directe
  if (ifcLoader?.ifcManager?.GetLineIDsWithType) {
    return ifcLoader.ifcManager;
  }

  console.error("❌ web-ifc API not found", ifcLoader);
  return null;
}
