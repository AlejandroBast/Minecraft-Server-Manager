"use client";

import { Loader2, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { ApiError, NetworkError, api } from "@/lib/api";
import { formatMemory } from "@/lib/format";
import {
  DIFFICULTIES,
  GAMEMODES,
  SERVER_TYPES,
  type Difficulty,
  type GameMode,
  type Recommendation,
  type ServerCreatePayload,
  type ServerType,
} from "@/lib/types";

const TYPE_LABELS: Record<ServerType, string> = {
  vanilla: "Vanilla — el servidor oficial",
  paper: "Paper — optimizado, admite plugins",
  purpur: "Purpur — Paper con más ajustes",
  spigot: "Spigot — clásico, admite plugins",
  fabric: "Fabric — mods ligeros",
  forge: "Forge — mods clásicos",
  neoforge: "NeoForge — sucesor de Forge",
};

const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  peaceful: "Pacífico",
  easy: "Fácil",
  normal: "Normal",
  hard: "Difícil",
};

const GAMEMODE_LABELS: Record<GameMode, string> = {
  survival: "Supervivencia",
  creative: "Creativo",
  adventure: "Aventura",
  spectator: "Espectador",
};

const DEFAULTS: ServerCreatePayload = {
  name: "",
  type: "paper",
  version: "1.21.4",
  port: 25565,
  max_players: 20,
  motd: "Un servidor de Minecraft",
  difficulty: "normal",
  gamemode: "survival",
  online_mode: true,
  hardcore: false,
  allow_commands: true,
  whitelist_enabled: false,
  generate_world: true,
  seed: null,
  memory_min_mb: 1024,
  memory_max_mb: 2048,
};

interface CreateServerDialogProps {
  recommendations: Recommendation[];
  onCreated: () => void;
}

export function CreateServerDialog({ recommendations, onCreated }: CreateServerDialogProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ServerCreatePayload>(DEFAULTS);

  const recommendation = recommendations.find((item) => item.server_type === form.type);

  function update(patch: Partial<ServerCreatePayload>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function applyRecommendedMemory() {
    if (!recommendation) return;
    update({
      memory_min_mb: recommendation.memory_min_mb,
      memory_max_mb: recommendation.memory_max_mb,
    });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      const created = await api.createServer({
        ...form,
        seed: form.seed?.trim() ? form.seed.trim() : null,
      });
      toast.success(`Servidor «${created.server.name}» creado.`);
      created.warnings.forEach((warning) => toast.warning(warning));
      setForm(DEFAULTS);
      setOpen(false);
      onCreated();
    } catch (error) {
      if (error instanceof NetworkError) {
        toast.error("No se puede conectar con el backend.");
      } else if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("No se pudo crear el servidor.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Crear servidor
        </Button>
      </DialogTrigger>

      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Nuevo servidor</DialogTitle>
          <DialogDescription>
            No hace falta descargar nada: el programa se encarga de Java y de los archivos.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="name">Nombre</Label>
              <Input
                id="name"
                value={form.name}
                onChange={(event) => update({ name: event.target.value })}
                placeholder="Mi servidor"
                minLength={2}
                maxLength={50}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="type">Tipo</Label>
              <Select value={form.type} onValueChange={(value) => update({ type: value as ServerType })}>
                <SelectTrigger id="type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SERVER_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      {TYPE_LABELS[type]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="version">Versión</Label>
              <Input
                id="version"
                value={form.version}
                onChange={(event) => update({ version: event.target.value })}
                placeholder="1.21.4"
                required
              />
              <p className="text-xs text-muted-foreground">
                La lista automática de versiones llega en la fase 5.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="port">Puerto</Label>
              <Input
                id="port"
                type="number"
                value={form.port}
                onChange={(event) => update({ port: Number(event.target.value) })}
                min={1024}
                max={65535}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="max_players">Jugadores máximos</Label>
              <Input
                id="max_players"
                type="number"
                value={form.max_players}
                onChange={(event) => update({ max_players: Number(event.target.value) })}
                min={1}
                max={1000}
                required
              />
            </div>

            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="motd">Mensaje del servidor (MOTD)</Label>
              <Input
                id="motd"
                value={form.motd}
                onChange={(event) => update({ motd: event.target.value })}
                maxLength={120}
              />
            </div>
          </div>

          <Separator />

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="difficulty">Dificultad</Label>
              <Select
                value={form.difficulty}
                onValueChange={(value) => update({ difficulty: value as Difficulty })}
                disabled={form.hardcore}
              >
                <SelectTrigger id="difficulty" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DIFFICULTIES.map((difficulty) => (
                    <SelectItem key={difficulty} value={difficulty}>
                      {DIFFICULTY_LABELS[difficulty]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {form.hardcore && (
                <p className="text-xs text-muted-foreground">
                  El modo hardcore obliga a dificultad difícil.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="gamemode">Modo de juego</Label>
              <Select
                value={form.gamemode}
                onValueChange={(value) => update({ gamemode: value as GameMode })}
              >
                <SelectTrigger id="gamemode" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {GAMEMODES.map((gamemode) => (
                    <SelectItem key={gamemode} value={gamemode}>
                      {GAMEMODE_LABELS[gamemode]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="seed">Semilla del mundo (opcional)</Label>
              <Input
                id="seed"
                value={form.seed ?? ""}
                onChange={(event) => update({ seed: event.target.value })}
                placeholder="Dejar vacío para una semilla aleatoria"
                maxLength={64}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <ToggleRow
              id="online_mode"
              label="Modo online"
              hint="Verifica las cuentas con Mojang."
              checked={form.online_mode}
              onChange={(checked) => update({ online_mode: checked })}
            />
            <ToggleRow
              id="hardcore"
              label="Hardcore"
              hint="Una sola vida por jugador."
              checked={form.hardcore}
              onChange={(checked) =>
                update({ hardcore: checked, difficulty: checked ? "hard" : form.difficulty })
              }
            />
            <ToggleRow
              id="allow_commands"
              label="Permitir comandos"
              hint="Habilita los trucos en el mundo."
              checked={form.allow_commands}
              onChange={(checked) => update({ allow_commands: checked })}
            />
            <ToggleRow
              id="whitelist_enabled"
              label="Lista blanca"
              hint="Sólo entran los jugadores autorizados."
              checked={form.whitelist_enabled}
              onChange={(checked) => update({ whitelist_enabled: checked })}
            />
          </div>

          <Separator />

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <Label>Memoria asignada</Label>
              {recommendation && (
                <Button type="button" variant="ghost" size="xs" onClick={applyRecommendedMemory}>
                  <Sparkles /> Usar la recomendada
                </Button>
              )}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="memory_min_mb" className="text-xs text-muted-foreground">
                  Mínima (MB)
                </Label>
                <Input
                  id="memory_min_mb"
                  type="number"
                  value={form.memory_min_mb}
                  onChange={(event) => update({ memory_min_mb: Number(event.target.value) })}
                  min={512}
                  step={512}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="memory_max_mb" className="text-xs text-muted-foreground">
                  Máxima (MB)
                </Label>
                <Input
                  id="memory_max_mb"
                  type="number"
                  value={form.memory_max_mb}
                  onChange={(event) => update({ memory_max_mb: Number(event.target.value) })}
                  min={512}
                  step={512}
                  required
                />
              </div>
            </div>

            {recommendation && (
              <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
                <p>
                  Tu equipo puede alojar aproximadamente{" "}
                  <strong className="tabular-nums">
                    {recommendation.estimated_players} jugadores
                  </strong>{" "}
                  con este tipo de servidor, usando{" "}
                  {formatMemory(recommendation.memory_min_mb)} –{" "}
                  {formatMemory(recommendation.memory_max_mb)}.
                </p>
                {recommendation.warnings.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                    {recommendation.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={saving}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="animate-spin" /> : <Plus />}
              Crear servidor
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface ToggleRowProps {
  id: string;
  label: string;
  hint: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function ToggleRow({ id, label, hint, checked, onChange }: ToggleRowProps) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
      <div className="space-y-0.5">
        <Label htmlFor={id}>{label}</Label>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
