/**
 * Tipos espejo de los esquemas Pydantic del backend.
 *
 * Se escriben a mano a propósito: son la única fuente de verdad del contrato en
 * el frontend y cualquier cambio del backend debe romper aquí la compilación.
 */

export const SERVER_TYPES = [
  "vanilla",
  "paper",
  "purpur",
  "spigot",
  "fabric",
  "forge",
  "neoforge",
] as const;

export type ServerType = (typeof SERVER_TYPES)[number];

export type ServerStatus =
  | "stopped"
  | "starting"
  | "online"
  | "stopping"
  | "restarting"
  | "saving"
  | "installing"
  | "error";

export const DIFFICULTIES = ["peaceful", "easy", "normal", "hard"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];

export const GAMEMODES = ["survival", "creative", "adventure", "spectator"] as const;
export type GameMode = (typeof GAMEMODES)[number];

export interface Server {
  id: number;
  name: string;
  folder: string;
  type: ServerType;
  version: string;
  build: string | null;
  status: ServerStatus;
  port: number;
  max_players: number;
  motd: string;
  difficulty: Difficulty;
  gamemode: GameMode;
  online_mode: boolean;
  hardcore: boolean;
  allow_commands: boolean;
  whitelist_enabled: boolean;
  generate_world: boolean;
  seed: string | null;
  memory_min_mb: number;
  memory_max_mb: number;
  java_path: string | null;
  last_error: string | null;
  supports_plugins: boolean;
  supports_mods: boolean;
  uptime_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface ServerCreatePayload {
  name: string;
  type: ServerType;
  version: string;
  port: number;
  max_players: number;
  motd: string;
  difficulty: Difficulty;
  gamemode: GameMode;
  online_mode: boolean;
  hardcore: boolean;
  allow_commands: boolean;
  whitelist_enabled: boolean;
  generate_world: boolean;
  seed: string | null;
  memory_min_mb: number;
  memory_max_mb: number;
}

export interface ServerCreated {
  server: Server;
  warnings: string[];
}

export interface SystemInfo {
  os: string;
  os_version: string;
  architecture: string;
  python_version: string;
  cpu: {
    name: string;
    physical_cores: number;
    logical_cores: number;
    frequency_mhz: number;
    usage_percent: number;
  };
  memory: {
    total_mb: number;
    available_mb: number;
    used_percent: number;
  };
  disk: {
    path: string;
    total_gb: number;
    free_gb: number;
    used_percent: number;
  };
  java: {
    installed: boolean;
    version: string | null;
    major: number | null;
    path: string | null;
    managed: boolean;
  };
  network: {
    hostname: string;
    local_ip: string;
    public_ip: string | null;
  };
}

export interface Recommendation {
  server_type: ServerType;
  estimated_players: number;
  memory_min_mb: number;
  memory_max_mb: number;
  warnings: string[];
}

export interface AppSettings {
  values: Record<string, string | null>;
}

export interface VersionList {
  type: ServerType;
  supported: boolean;
  reason: string | null;
  versions: { version: string; stable: boolean }[];
}

export interface InstallProgress {
  stage: string;
  progress: number;
  detail: string;
}

export interface ServerStats {
  server_id: number;
  running: boolean;
  cpu_percent: number | null;
  memory_mb: number | null;
  memory_percent_of_limit: number | null;
  uptime_seconds: number | null;
  online_players: number | null;
  max_players: number | null;
  tps: number | null;
  world_size_bytes: number;
  disk_free_gb: number;
}

export interface CleanupResult {
  orphan_backups_removed: number;
  bytes_freed: number;
  temp_files_removed: number;
}

export interface PortStatus {
  port: number;
  listening: boolean;
  upnp_mapped: boolean;
}

export interface NetworkDiagnosis {
  local_ip: string;
  public_ip: string | null;
  router_external_ip: string | null;
  upnp_available: boolean;
  behind_carrier_nat: boolean;
  ports: PortStatus[];
  notes: string[];
}

export interface DnsRecord {
  type: string;
  name: string;
  value: string;
  explanation: string;
}

export interface DnsInstructions {
  domain: string;
  records: DnsRecord[];
}

export interface PortActionResult {
  success: boolean;
  message: string;
}

export type AddonKind = "plugins" | "mods";

export interface Addon {
  file: string;
  size_bytes: number;
  enabled: boolean;
}

export type BackupStatus = "pending" | "running" | "completed" | "failed";

export interface Backup {
  id: number;
  server_id: number;
  file: string;
  size_bytes: number;
  status: BackupStatus;
  notes: string | null;
  created_at: string;
}

export interface ConsoleLine {
  index: number;
  line: string;
}

export interface ConsoleOutput {
  lines: ConsoleLine[];
  next_index: number;
  running: boolean;
}
