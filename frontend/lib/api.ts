const LOCAL_API_BASES = ["http://localhost:8000", "http://localhost:8080"];
const LOCAL_WS_BASES = ["ws://localhost:8000/ws/vitals", "ws://localhost:8080/ws/vitals"];

function unique(values: string[]): string[] {
  return values.filter((value, index) => values.indexOf(value) === index);
}

function compact(values: Array<string | undefined | null>): string[] {
  return values
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter((value) => value.length > 0);
}

export function getApiBases(): string[] {
  const configured = compact([process.env.NEXT_PUBLIC_API_URL]);
  if (process.env.NODE_ENV === "development") {
    return unique([...configured, ...LOCAL_API_BASES]);
  }
  return unique(configured);
}

export function getWsCandidateUrls(): string[] {
  const configured = compact([process.env.NEXT_PUBLIC_WS_URL]);
  if (process.env.NODE_ENV === "development") {
    return unique([...configured, ...LOCAL_WS_BASES]);
  }
  return unique(configured);
}

export function toApiBaseFromWs(wsUrl: string | null): string | null {
  if (!wsUrl) {
    return null;
  }

  try {
    const parsed = new URL(wsUrl);
    parsed.protocol = parsed.protocol === "wss:" ? "https:" : "http:";
    parsed.pathname = "";
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return null;
  }
}
