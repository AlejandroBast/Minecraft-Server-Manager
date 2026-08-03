/**
 * Cliente HTTP del backend.
 *
 * El navegador llama directamente a la API: todo corre en el mismo equipo y no
 * hay secretos que ocultar, así que un proxy en Next sólo añadiría latencia.
 */

import type {
  Addon,
  AddonKind,
  AppSettings,
  Backup,
  CleanupResult,
  ConsoleOutput,
  DnsInstructions,
  InstallProgress,
  NetworkDiagnosis,
  PortActionResult,
  Recommendation,
  Server,
  ServerCreatePayload,
  ServerCreated,
  ServerStats,
  ServerType,
  SystemInfo,
  TunnelStatus,
  VersionList,
} from "@/lib/types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

interface DomainErrorBody {
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

interface ValidationErrorBody {
  detail: { loc: (string | number)[]; msg: string }[];
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export class NetworkError extends Error {
  constructor() {
    super("No se puede conectar con el backend.");
    this.name = "NetworkError";
  }
}

function isDomainError(body: unknown): body is DomainErrorBody {
  return typeof body === "object" && body !== null && "message" in body && "error" in body;
}

function isValidationError(body: unknown): body is ValidationErrorBody {
  return (
    typeof body === "object" &&
    body !== null &&
    "detail" in body &&
    Array.isArray((body as ValidationErrorBody).detail)
  );
}

/** Convierte los errores de FastAPI en un mensaje legible en español. */
function toApiError(status: number, body: unknown): ApiError {
  if (isDomainError(body)) {
    return new ApiError(status, body.error, body.message, body.details ?? {});
  }
  if (isValidationError(body)) {
    const messages = body.detail.map((item) => {
      const field = item.loc.filter((part) => part !== "body").join(".");
      return field ? `${field}: ${item.msg}` : item.msg;
    });
    return new ApiError(status, "validation_error", messages.join(" · "));
  }
  return new ApiError(status, "unknown_error", `Error inesperado del servidor (${status}).`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new NetworkError();
  }
  return handleResponse<T>(response);
}

/** Subida multipart: el navegador fija solo el Content-Type con el boundary. */
async function upload<T>(path: string, formData: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { method: "POST", body: formData });
  } catch {
    throw new NetworkError();
  }
  return handleResponse<T>(response);
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw toApiError(response.status, body);
  }
  return body as T;
}

export const api = {
  listServers: () => request<Server[]>("/servers"),
  createServer: (payload: ServerCreatePayload) =>
    request<ServerCreated>("/servers", { method: "POST", body: JSON.stringify(payload) }),
  updateServer: (id: number, payload: Partial<ServerCreatePayload>) =>
    request<Server>(`/servers/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteServer: (id: number) => request<void>(`/servers/${id}`, { method: "DELETE" }),
  retryInstall: (id: number) => request<void>(`/servers/${id}/install/retry`, { method: "POST" }),
  startServer: (id: number) => request<void>(`/servers/${id}/start`, { method: "POST" }),
  stopServer: (id: number) => request<void>(`/servers/${id}/stop`, { method: "POST" }),
  restartServer: (id: number) => request<void>(`/servers/${id}/restart`, { method: "POST" }),
  consoleOutput: (id: number, since = 0) =>
    request<ConsoleOutput>(`/servers/${id}/console?since=${since}`),
  sendCommand: (id: number, command: string) =>
    request<{ sent: string }>(`/servers/${id}/console`, {
      method: "POST",
      body: JSON.stringify({ command }),
    }),
  listAddons: (serverId: number, kind: AddonKind) =>
    request<Addon[]>(`/servers/${serverId}/addons/${kind}`),
  uploadAddon: (serverId: number, kind: AddonKind, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return upload<Addon>(`/servers/${serverId}/addons/${kind}`, formData);
  },
  toggleAddon: (serverId: number, kind: AddonKind, filename: string, enabled: boolean) =>
    request<Addon>(`/servers/${serverId}/addons/${kind}/${encodeURIComponent(filename)}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
  deleteAddon: (serverId: number, kind: AddonKind, filename: string) =>
    request<void>(`/servers/${serverId}/addons/${kind}/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    }),
  listBackups: (serverId: number) => request<Backup[]>(`/servers/${serverId}/backups`),
  createBackup: (serverId: number, notes: string | null = null) =>
    request<Backup>(`/servers/${serverId}/backups`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    }),
  restoreBackup: (backupId: number) =>
    request<void>(`/backups/${backupId}/restore`, { method: "POST" }),
  deleteBackup: (backupId: number) =>
    request<void>(`/backups/${backupId}`, { method: "DELETE" }),
  versions: (type: ServerType) => request<VersionList>(`/downloads/versions/${type}`),
  installProgress: (id: number) => request<InstallProgress>(`/servers/${id}/install`),
  serverStats: (id: number) => request<ServerStats>(`/servers/${id}/stats`),
  cleanup: () => request<CleanupResult>("/system/cleanup", { method: "POST" }),
  tunnel: () => request<TunnelStatus>("/tunnel"),
  saveTunnelSecret: (secret: string) =>
    request<TunnelStatus>("/tunnel/secret", { method: "PUT", body: JSON.stringify({ secret }) }),
  deleteTunnelSecret: () => request<void>("/tunnel/secret", { method: "DELETE" }),
  startTunnel: () => request<TunnelStatus>("/tunnel/start", { method: "POST" }),
  stopTunnel: () => request<TunnelStatus>("/tunnel/stop", { method: "POST" }),
  network: () => request<NetworkDiagnosis>("/network"),
  openPort: (port: number) =>
    request<PortActionResult>(`/network/ports/${port}/open`, { method: "POST" }),
  closePort: (port: number) =>
    request<PortActionResult>(`/network/ports/${port}/close`, { method: "POST" }),
  dnsInstructions: (domain: string, port: number) =>
    request<DnsInstructions>("/network/dns", {
      method: "POST",
      body: JSON.stringify({ domain, port }),
    }),
  systemInfo: () => request<SystemInfo>("/system/info"),
  recommendations: () => request<Recommendation[]>("/system/recommendations"),
  settings: () => request<AppSettings>("/settings"),
};
