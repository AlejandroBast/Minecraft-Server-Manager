"use client";

import { SendHorizonal, Terminal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { API_URL, ApiError, api } from "@/lib/api";
import type { ConsoleLine, Server } from "@/lib/types";

interface ConsoleDialogProps {
  server: Server;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ConsoleDialog({ server, open, onOpenChange }: ConsoleDialogProps) {
  const [lines, setLines] = useState<ConsoleLine[]>([]);
  const [command, setCommand] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // WebSocket de sólo lectura: el backend emite el histórico y luego cada
  // línea nueva. Los comandos entran por POST, donde se validan.
  useEffect(() => {
    if (!open) return;
    const wsUrl = `${API_URL.replace(/^http/, "ws")}/servers/${server.id}/console/ws`;
    const socket = new WebSocket(wsUrl);

    // El backend reenvía el histórico al conectar: se limpia justo entonces.
    socket.onopen = () => setLines([]);
    socket.onmessage = (event) => {
      const line = JSON.parse(event.data) as ConsoleLine;
      setLines((current) => [...current.slice(-999), line]);
    };
    socket.onerror = () => toast.error("Se perdió la conexión con la consola.");

    return () => socket.close();
  }, [open, server.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [lines]);

  async function handleSend(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = command.trim();
    if (!trimmed) return;
    setSending(true);
    try {
      await api.sendCommand(server.id, trimmed);
      setCommand("");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "No se pudo enviar el comando.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Terminal className="size-4" /> Consola — {server.name}
            <StatusBadge status={server.status} />
          </DialogTitle>
          <DialogDescription>
            Salida en tiempo real. Escribe comandos como <code>say Hola</code>,{" "}
            <code>time set day</code> u <code>op Steve</code>.
          </DialogDescription>
        </DialogHeader>

        <div
          ref={scrollRef}
          className="min-h-64 flex-1 overflow-y-auto rounded-lg border border-border bg-zinc-950 p-3 font-mono text-xs text-zinc-100"
        >
          {lines.length === 0 ? (
            <p className="text-zinc-500">Sin salida todavía…</p>
          ) : (
            lines.map((item) => (
              <div key={item.index} className="whitespace-pre-wrap break-all">
                {item.line}
              </div>
            ))
          )}
        </div>

        <form onSubmit={handleSend} className="flex gap-2">
          <Input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="Comando (sin la barra inicial)"
            maxLength={500}
            disabled={server.status !== "online" && server.status !== "starting"}
            autoFocus
            className="font-mono"
          />
          <Button type="submit" disabled={sending || !command.trim()}>
            <SendHorizonal /> Enviar
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
