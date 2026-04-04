/**
 * API client for WLED Matrix Manager backend.
 * No auth required — Home Assistant handles authorization.
 */

const BASE = "/api";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE}${path}`;
  const headers: Record<string, string> = {};

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const resp = await fetch(url, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string>) },
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }

  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return resp.json();
  }
  return resp as unknown as T;
}

// ─── Status ─────────────────────────────────────────────

export const getStatus = () =>
  request<{ status: string; version: string; message: string }>("/status");

export const getStats = () =>
  request<{
    total_scenes: number;
    total_devices: number;
    active_playbacks: number;
  }>("/stats");

// ─── Devices ────────────────────────────────────────────

export interface DeviceData {
  id: number;
  name: string;
  ip_address: string;
  ha_entity_id?: string;
  matrix_width: number;
  matrix_height: number;
  communication_protocol: string;
  chain_count: number;
  segment_id: number;
  is_active: boolean;
  is_healthy?: boolean;
}

export const getDevices = () => request<DeviceData[]>("/devices");

export const createDevice = (d: Omit<DeviceData, "id" | "is_active">) =>
  request<DeviceData>("/devices", { method: "POST", body: JSON.stringify(d) });

export const updateDevice = (id: number, d: Partial<DeviceData>) =>
  request<DeviceData>(`/devices/${id}`, {
    method: "PUT",
    body: JSON.stringify(d),
  });

export const deleteDevice = (id: number) =>
  request<{ success: boolean }>(`/devices/${id}`, { method: "DELETE" });

export const checkDeviceHealth = (id: number) =>
  request<{ device_id: number; healthy: boolean }>(`/devices/${id}/health`);

// ─── HA Discovery ───────────────────────────────────────

export interface HADevice {
  entity_id: string;
  name: string;
  ip_address: string;
  state: string;
  attributes: Record<string, unknown>;
}

export const discoverHADevices = () =>
  request<{ devices: HADevice[] }>("/ha/discover");

// ─── Scenes ─────────────────────────────────────────────

export interface FrameData {
  frame_index: number;
  pixel_data: {
    pixels: Array<{ index: number; color: number[] }>;
    width: number;
    height: number;
  };
  duration?: number;
  brightness: number;
  color_r: number;
  color_g: number;
  color_b: number;
}

export interface SceneData {
  id: number;
  name: string;
  description?: string;
  matrix_width: number;
  matrix_height: number;
  default_frame_duration: number;
  loop_mode: string;
  is_active: boolean;
  frame_count: number;
  device_ids: number[];
  frames: FrameData[];
}

export interface SceneCreate {
  name: string;
  description?: string;
  matrix_width: number;
  matrix_height: number;
  default_frame_duration: number;
  loop_mode: string;
  device_ids: number[];
  frames: FrameData[];
}

export const getScenes = () => request<SceneData[]>("/scenes");

export const getScene = (id: number) => request<SceneData>(`/scenes/${id}`);

export const createScene = (s: SceneCreate) =>
  request<SceneData>("/scenes", { method: "POST", body: JSON.stringify(s) });

export const updateScene = (id: number, s: Partial<SceneCreate>) =>
  request<SceneData>(`/scenes/${id}`, {
    method: "PUT",
    body: JSON.stringify(s),
  });

export const deleteScene = (id: number) =>
  request<{ success: boolean }>(`/scenes/${id}`, { method: "DELETE" });

// ─── Playback ───────────────────────────────────────────

export const playScene = (id: number, deviceIds: number[] = []) =>
  request<{ success: boolean }>(`/scenes/${id}/play`, {
    method: "POST",
    body: JSON.stringify({ device_ids: deviceIds }),
  });

export const stopScene = (id: number) =>
  request<{ success: boolean }>(`/scenes/${id}/stop`, { method: "POST" });

export const getPlaybackStatus = () =>
  request<Record<string, { is_playing: boolean; loop_mode: string }>>(
    "/playback/status",
  );

// ─── Export / Import ────────────────────────────────────

export const exportScene = async (id: number): Promise<Blob> => {
  const resp = await fetch(`${BASE}/scenes/${id}/export`);
  if (!resp.ok) throw new Error("Export failed");
  return resp.blob();
};

export const importScene = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return request<{ success: boolean; scene_id: number; name: string }>(
    "/scenes/import",
    {
      method: "POST",
      body: form,
    },
  );
};

// ─── Image ──────────────────────────────────────────────

export const convertImage = async (
  file: File,
  width: number,
  height: number,
  colors = 256,
) => {
  const form = new FormData();
  form.append("file", file);
  return request<{
    pixels: Array<{ index: number; color: number[] }>;
    width: number;
    height: number;
  }>(`/image/convert?width=${width}&height=${height}&colors=${colors}`, {
    method: "POST",
    body: form,
  });
};
