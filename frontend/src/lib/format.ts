/** Formateo de unidades para la interfaz. */

export function formatMemory(megabytes: number): string {
  if (megabytes < 1024) {
    return `${megabytes} MB`;
  }
  return `${(megabytes / 1024).toFixed(1).replace(".0", "")} GB`;
}

export function formatGigabytes(gigabytes: number): string {
  return `${gigabytes.toFixed(1).replace(".0", "")} GB`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

export function formatFrequency(megahertz: number): string {
  return megahertz > 0 ? `${(megahertz / 1000).toFixed(1)} GHz` : "—";
}
