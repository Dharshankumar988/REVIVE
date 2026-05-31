"use client";

import { type ReactElement, useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PulseAIWidget } from "@/components/PulseAIWidget";
import { getApiBases, getWsCandidateUrls, toApiBaseFromWs } from "@/lib/api";
import { getSupabaseClient } from "@/lib/supabase";
import { Session } from "@supabase/supabase-js";

type RiskStatus = "Normal" | "Warning" | "Critical";
type Scenario = "Stable" | "Gradual Decline" | "Sudden Cardiac Event" | "Cardiac Arrest";
type TrendLabel = "stable" | "declining" | "critical";
type ThreatLevel = "LOW" | "ELEVATED" | "HIGH" | "SEVERE";
type SimulationChoice = "1" | "2" | "3" | "4";

type VitalsPoint = {
  hr: number;
  spo2: number;
  movement: number;
  timestamp: string;
  status: RiskStatus;
  scenario: string;
  instant_action?: string | null;
  detailed_steps?: string[];
  veteran_brief?: string | null;
  trend?: TrendLabel;
};

const MAX_POINTS = 20;
const WS_CANDIDATE_URLS = getWsCandidateUrls();

const API_CANDIDATE_BASES = getApiBases();

const scenarios: Scenario[] = ["Stable", "Gradual Decline", "Sudden Cardiac Event"];
const simulationChoices: Array<{ value: SimulationChoice; label: Scenario }> = [
  { value: "1", label: "Stable" },
  { value: "2", label: "Gradual Decline" },
  { value: "3", label: "Sudden Cardiac Event" },
  { value: "4", label: "Cardiac Arrest" },
];

const scenarioValueToChoice: Record<string, SimulationChoice> = {
  "1": "1",
  "2": "2",
  "3": "3",
  "4": "4",
  stable: "1",
  gradual_decline: "2",
  sudden_cardiac_event: "3",
  cardiac_arrest: "4",
};

function toSimulationChoice(raw: unknown): SimulationChoice | null {
  if (typeof raw !== "string") {
    return null;
  }

  const normalized = raw.trim().toLowerCase().replace(/\s+/g, "_");
  return scenarioValueToChoice[normalized] ?? null;
}

const statusStyles: Record<RiskStatus, { label: string; chip: string; card: string }> = {
  Normal: {
    label: "NORMAL",
    chip: "bg-emerald-500 text-emerald-950",
    card: "border-emerald-200 bg-emerald-50",
  },
  Warning: {
    label: "WARNING",
    chip: "bg-amber-400 text-amber-950",
    card: "border-amber-200 bg-amber-50",
  },
  Critical: {
    label: "CRITICAL",
    chip: "bg-red-500 text-red-50",
    card: "border-red-200 bg-red-50",
  },
};

const valueColorMap: Record<RiskStatus, string> = {
  Normal: "text-emerald-600",
  Warning: "text-amber-500",
  Critical: "text-red-600",
};

const trendStyles: Record<TrendLabel, { text: string; className: string }> = {
  stable: { text: "Trend: Stable", className: "text-emerald-600" },
  declining: { text: "Trend: Declining ⚠️", className: "text-amber-500" },
  critical: { text: "Trend: Critical 🚨", className: "text-red-600" },
};

function formatClockLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }

  return date.toLocaleTimeString([], {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function getHeartRateStatus(hr: number): RiskStatus {
  if (hr < 50 || hr > 130) {
    return "Critical";
  }
  if (hr < 60 || hr > 110) {
    return "Warning";
  }
  return "Normal";
}

function getSpo2Status(spo2: number): RiskStatus {
  if (spo2 < 90) {
    return "Critical";
  }
  if (spo2 < 94) {
    return "Warning";
  }
  return "Normal";
}

function getThreatLevel(status: RiskStatus, trend: TrendLabel): ThreatLevel {
  if (status === "Critical") {
    return "SEVERE";
  }
  if (status === "Warning" && trend === "critical") {
    return "HIGH";
  }
  if (status === "Warning" || trend === "declining") {
    return "ELEVATED";
  }
  return "LOW";
}



const threatStyles: Record<ThreatLevel, { chip: string; note: string }> = {
  LOW: {
    chip: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300",
    note: "Patient is stable. Continue routine monitoring and periodic reassessment.",
  },
  ELEVATED: {
    chip: "bg-amber-100 text-amber-900 ring-1 ring-amber-300",
    note: "Signs of deterioration are present. Increase observation frequency and prepare escalation.",
  },
  HIGH: {
    chip: "bg-orange-100 text-orange-900 ring-1 ring-orange-300",
    note: "High-risk pattern detected. Keep emergency resources ready and brief the response team.",
  },
  SEVERE: {
    chip: "bg-red-100 text-red-900 ring-1 ring-red-300",
    note: "Emergency state. Trigger protocol immediately and coordinate critical response.",
  },
};

export default function Page() {
  const [points, setPoints] = useState<VitalsPoint[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [activeWsUrl, setActiveWsUrl] = useState<string | null>(null);
  const [simulationChoice, setSimulationChoice] = useState<SimulationChoice>("1");
  const wsRef = useRef<WebSocket | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  const handleLogout = async () => {
    try {
      const supabase = getSupabaseClient();
      await supabase.auth.signOut();
      window.location.href = "/login";
    } catch (error) {
      console.error("Logout failed", error);
    }
  };


  useEffect(() => {
    let mounted = true;

    const setSessionState = async (session: Session | null) => {
      if (!mounted) {
        return;
      }

      if (!session) {
        setAuthReady(false);
        setUserEmail(null);
        window.location.href = "/login";
        return;
      }

      try {
        const supabase = getSupabaseClient();
        const { data: profile, error: profileError } = await supabase
          .from("profiles")
          .select("role,is_approved")
          .eq("id", session.user.id)
          .single();

        if (profileError || !profile) {
          await supabase.auth.signOut();
          setAuthReady(false);
          setUserEmail(null);
          window.location.href = "/login";
          return;
        }

        if (!profile.is_approved) {
          await supabase.auth.signOut();
          setAuthReady(false);
          setUserEmail(null);
          window.location.href = "/login?pending=1";
          return;
        }

        setUserEmail(session.user.email ?? null);
        setAuthReady(true);
      } catch {
        setAuthReady(false);
        setUserEmail(null);
        window.location.href = "/login";
      }
    };

    const initialize = async () => {
      try {
        const supabase = getSupabaseClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        await setSessionState(session);

        const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
          void setSessionState(nextSession);
        });

        return () => {
          data.subscription.unsubscribe();
        };
      } catch {
        if (mounted) {
          setAuthReady(false);
          window.location.href = "/login";
        }
      }

      return undefined;
    };

    let cleanup: (() => void) | undefined;
    void initialize().then((fn) => {
      cleanup = fn;
    });

    return () => {
      mounted = false;
      if (cleanup) {
        cleanup();
      }
    };
  }, []);

  useEffect(() => {
    if (!authReady) {
      return;
    }

    let disposed = false;
    let socket: WebSocket | null = null;
    let retryHandle: number | null = null;
    let candidateIndex = 0;

    const connect = () => {
      if (disposed || WS_CANDIDATE_URLS.length === 0) {
        return;
      }

      const wsUrl = WS_CANDIDATE_URLS[candidateIndex % WS_CANDIDATE_URLS.length];
      let opened = false;

      try {
        socket = new WebSocket(wsUrl);
        wsRef.current = socket;
      } catch {
        candidateIndex += 1;
        retryHandle = window.setTimeout(connect, 1200);
        return;
      }

      socket.onopen = () => {
        opened = true;
        setIsConnected(true);
        setActiveWsUrl(wsUrl);
      };

      socket.onclose = () => {
        if (disposed) {
          return;
        }
        if (wsRef.current === socket) {
          wsRef.current = null;
        }
        setIsConnected(false);
        if (!opened) {
          candidateIndex += 1;
        }
        retryHandle = window.setTimeout(connect, 1200);
      };

      socket.onerror = () => {
        setIsConnected(false);
      };

      socket.onmessage = (event) => {
        try {
          const incoming = JSON.parse(event.data) as Partial<VitalsPoint>;
          if (
            typeof incoming.hr !== "number" ||
            typeof incoming.spo2 !== "number" ||
            typeof incoming.movement !== "number" ||
            typeof incoming.timestamp !== "string" ||
            typeof incoming.status !== "string" ||
            typeof incoming.scenario !== "string"
          ) {
            return;
          }

          const status =
            incoming.status === "Critical" || incoming.status === "Warning" || incoming.status === "Normal"
              ? incoming.status
              : "Normal";

          const next: VitalsPoint = {
            hr: incoming.hr,
            spo2: incoming.spo2,
            movement: incoming.movement,
            timestamp: incoming.timestamp,
            status,
            scenario: incoming.scenario,
            instant_action:
              typeof incoming.instant_action === "string" || incoming.instant_action === null
                ? incoming.instant_action
                : null,
            detailed_steps:
              Array.isArray(incoming.detailed_steps) && incoming.detailed_steps.every((step) => typeof step === "string")
                ? incoming.detailed_steps
                : [],
            veteran_brief:
              typeof incoming.veteran_brief === "string" || incoming.veteran_brief === null
                ? incoming.veteran_brief
                : null,
            trend:
              incoming.trend === "critical" || incoming.trend === "declining" || incoming.trend === "stable"
                ? incoming.trend
                : "stable",
          };

          setPoints((prev) => {
            const appended = [...prev, next];
            return appended.length > MAX_POINTS ? appended.slice(-MAX_POINTS) : appended;
          });
        } catch {
          // Ignore malformed socket messages.
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      wsRef.current = null;
      setIsConnected(false);
      if (retryHandle !== null) {
        window.clearTimeout(retryHandle);
      }
      if (socket) {
        socket.close();
      }
    };
  }, [authReady]);

  useEffect(() => {
    if (!authReady) {
      return;
    }

    let disposed = false;
    let lastTimestamp: string | null = null;

    const pollLatestVitals = async () => {
      if (disposed) {
        return;
      }

      for (const base of API_CANDIDATE_BASES) {
        try {
          const response = await fetch(`${base}/api/vitals/latest`);
          if (!response.ok) {
            continue;
          }

          const payload = (await response.json()) as {
            ok?: boolean;
            data?: Partial<VitalsPoint> | null;
          };

          if (payload.ok !== true || !payload.data || typeof payload.data.timestamp !== "string") {
            continue;
          }

          if (payload.data.timestamp === lastTimestamp) {
            return;
          }

          lastTimestamp = payload.data.timestamp;

          if (
            typeof payload.data.hr !== "number" ||
            typeof payload.data.spo2 !== "number" ||
            typeof payload.data.movement !== "number" ||
            typeof payload.data.status !== "string" ||
            typeof payload.data.scenario !== "string"
          ) {
            return;
          }

          const status =
            payload.data.status === "Critical" || payload.data.status === "Warning" || payload.data.status === "Normal"
              ? payload.data.status
              : "Normal";

          const next: VitalsPoint = {
            hr: payload.data.hr,
            spo2: payload.data.spo2,
            movement: payload.data.movement,
            timestamp: payload.data.timestamp,
            status,
            scenario: payload.data.scenario,
            instant_action:
              typeof payload.data.instant_action === "string" || payload.data.instant_action === null
                ? payload.data.instant_action
                : null,
            detailed_steps:
              Array.isArray(payload.data.detailed_steps) && payload.data.detailed_steps.every((step) => typeof step === "string")
                ? payload.data.detailed_steps
                : [],
            veteran_brief:
              typeof payload.data.veteran_brief === "string" || payload.data.veteran_brief === null
                ? payload.data.veteran_brief
                : null,
            trend:
              payload.data.trend === "critical" || payload.data.trend === "declining" || payload.data.trend === "stable"
                ? payload.data.trend
                : "stable",
          };

          setPoints((prev) => {
            if (prev.some((point) => point.timestamp === next.timestamp)) {
              return prev;
            }

            const appended = [...prev, next];
            return appended.length > MAX_POINTS ? appended.slice(-MAX_POINTS) : appended;
          });
          return;
        } catch {
          // Try the next configured API base.
        }
      }
    };

    void pollLatestVitals();
    const pollHandle = window.setInterval(() => {
      void pollLatestVitals();
    }, 1500);

    return () => {
      disposed = true;
      window.clearInterval(pollHandle);
    };
  }, [authReady]);

  const latest = points[points.length - 1];
  const currentStatus: RiskStatus = latest?.status ?? "Normal";
  const currentTrend: TrendLabel = latest?.trend ?? "stable";
  const threatLevel = getThreatLevel(currentStatus, currentTrend);
  const threatStyle = threatStyles[threatLevel];
  const statusStyle = statusStyles[currentStatus];
  const trendStyle = trendStyles[currentTrend];
  const isCritical = currentStatus === "Critical";
  const emergencyAction = latest?.instant_action?.trim() ?? "";
  const emergencySteps = Array.isArray(latest?.detailed_steps)
    ? latest.detailed_steps.filter((step) => typeof step === "string" && step.trim().length > 0)
    : [];
  const veteranBrief = latest?.veteran_brief?.trim() ?? "";
  const streamFreshnessMs = latest ? Date.now() - new Date(latest.timestamp).getTime() : Number.POSITIVE_INFINITY;
  const isStreamLive = isConnected || streamFreshnessMs < 15000;
  const emergencyHandoffSnapshot = latest
    ? `HR ${latest.hr} BPM | SpO2 ${latest.spo2}% | Movement ${latest.movement} | Trend ${currentTrend.toUpperCase()}`
    : "Latest vitals are not available yet.";

  const apiBases = [
    toApiBaseFromWs(activeWsUrl),
    ...WS_CANDIDATE_URLS.map((candidate) => toApiBaseFromWs(candidate)),
    ...API_CANDIDATE_BASES,
  ].filter((value, index, arr): value is string => !!value && arr.indexOf(value) === index);
  const apiBaseSignature = apiBases.join("|");

  useEffect(() => {

    let mounted = true;

    const syncScenario = async () => {
      for (const base of apiBases) {
        try {
          const response = await fetch(`${base}/api/simulation/scenario`);
          if (!response.ok) {
            continue;
          }

          const payload = (await response.json()) as {
            ok?: boolean;
            scenario?: string;
            label?: string;
          };

          if (!mounted || payload.ok !== true) {
            return;
          }

          const mappedChoice = toSimulationChoice(payload.scenario) ?? toSimulationChoice(payload.label);
          if (mappedChoice) {
            setSimulationChoice(mappedChoice);
          }
          return;
        } catch {
          // Try the next configured API base.
        }
      }
    };

    void syncScenario();

    return () => {
      mounted = false;
    };
  }, [apiBaseSignature]);

  useEffect(() => {
    if (latest?.scenario === "Gradual Decline") {
      setSimulationChoice("2");
      return;
    }

    if (latest?.scenario === "Sudden Cardiac Event") {
      setSimulationChoice("3");
      return;
    }

    if (latest?.scenario === "Cardiac Arrest") {
      setSimulationChoice("4");
      return;
    }

    if (latest?.scenario === "Stable") {
      setSimulationChoice("1");
    }
  }, [latest?.scenario]);

  const hrStatus = latest ? getHeartRateStatus(latest.hr) : "Normal";
  const spo2Status = latest ? getSpo2Status(latest.spo2) : "Normal";

  const chartData = useMemo(
    () =>
      points.map((point) => ({
        ...point,
        timeLabel: formatClockLabel(point.timestamp),
      })),
    [points],
  );


  const handleSetSimulationScenario = async (choice: SimulationChoice) => {
    const previousChoice = simulationChoice;
    setSimulationChoice(choice);

    const socket = wsRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ type: "set_scenario", scenario: choice }));
        return;
      } catch {
        // Fall through to HTTP API fallback path.
      }
    }

    if (apiBases.length === 0) {
      setSimulationChoice(previousChoice);
      return;
    }

    for (const base of apiBases) {
      try {
        const response = await fetch(`${base}/api/simulation/scenario`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ scenario: choice }),
        });

        if (!response.ok) {
          continue;
        }

        const payload = (await response.json()) as {
          ok?: boolean;
          scenario?: string;
          label?: string;
        };

        const mappedChoice =
          payload.ok === true
            ? toSimulationChoice(payload.scenario) ?? toSimulationChoice(payload.label)
            : null;

        if (mappedChoice) {
          setSimulationChoice(mappedChoice);
          return;
        }
      } catch {
        // Try the next configured API base.
      }
    }

    setSimulationChoice(previousChoice);
  };


  return (
    <main
      className={`relative min-h-screen p-4 md:p-8 ${
        isCritical ? "bg-red-50/90" : "bg-slate-50/90"
      } transition-colors duration-500 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-white to-slate-100`}
    >
      {isCritical ? <div className="pointer-events-none absolute inset-0 animate-pulse-glow bg-red-500/10 shadow-glow-red" /> : null}
      <div className="mx-auto max-w-[90rem] space-y-8">
        <header className="rounded-3xl bg-white/60 backdrop-blur-xl px-6 py-5 shadow-glass border border-white/40 md:px-8 md:py-6 relative overflow-hidden transition-all duration-300 hover:shadow-glass-hover hover:-translate-y-1">
          {isCritical && <div className="absolute top-0 left-0 w-full h-1 bg-red-500 animate-pulse-glow" />}
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between relative z-10">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl drop-shadow-sm">REVIVE Golden Hour Dashboard</h1>
                {isCritical && <span className="px-3 py-1 bg-red-100 text-red-700 text-xs font-bold rounded-full animate-pulse ring-1 ring-red-500/50">ACTIVE EMERGENCY</span>}
              </div>
              <p className="text-sm text-slate-600 mt-1 font-medium">Real-world clinical triage & general health monitoring</p>
            </div>
            <div className="flex items-center gap-4">
              {userEmail && <span className="text-sm text-slate-600 font-medium">{userEmail}</span>}
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-glass transition-all"
              >
                Log Out
              </button>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2 self-start rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            <span
              className={`h-2.5 w-2.5 rounded-full ${isStreamLive ? "bg-emerald-500" : "bg-red-500"}`}
              aria-hidden
            />
            {isStreamLive ? "LIVE" : "DISCONNECTED"}
          </div>
        </header>



        <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className={`relative overflow-hidden rounded-3xl p-8 transition-all duration-500 hover:-translate-y-1 ${isCritical ? 'bg-gradient-to-br from-red-950 to-slate-900 shadow-glow-red border border-red-500/30' : 'bg-gradient-to-br from-slate-900 to-slate-800 shadow-glass border border-slate-700/50 hover:shadow-glass-hover'}`}>
            <div className="relative z-10 flex flex-col items-center justify-center">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">Current Heart Rate</p>
              <div className="flex items-baseline gap-2">
                <p className={`font-mono text-8xl font-bold tracking-tighter drop-shadow-md ${isCritical ? 'text-red-400 animate-pulse' : valueColorMap[hrStatus]}`}>
                  {latest?.hr ?? "--"}
                </p>
                <span className="text-2xl font-medium text-slate-400">BPM</span>
              </div>
            </div>
            {isCritical && <div className="absolute -inset-10 bg-red-500/20 blur-3xl rounded-full animate-pulse-glow" />}
          </div>
          
          <div className={`relative overflow-hidden rounded-3xl p-8 transition-all duration-500 hover:-translate-y-1 ${isCritical ? 'bg-gradient-to-br from-red-950 to-slate-900 shadow-glow-red border border-red-500/30' : 'bg-gradient-to-br from-slate-900 to-slate-800 shadow-glass border border-slate-700/50 hover:shadow-glass-hover'}`}>
            <div className="relative z-10 flex flex-col items-center justify-center">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">Current SpO2</p>
              <div className="flex items-baseline gap-2">
                <p className={`font-mono text-8xl font-bold tracking-tighter drop-shadow-md ${isCritical ? 'text-red-400 animate-pulse' : valueColorMap[spo2Status]}`}>
                  {latest?.spo2 ?? "--"}
                </p>
                <span className="text-2xl font-medium text-slate-400">%</span>
              </div>
            </div>
            {isCritical && <div className="absolute -inset-10 bg-red-500/20 blur-3xl rounded-full animate-pulse-glow" />}
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wide text-slate-500">Heart Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-2">
                <p className="text-4xl font-bold text-slate-900">{latest?.hr ?? "--"}</p>
                <p className="pb-1 text-sm text-slate-500">BPM</p>
              </div>
              <p className="mt-3 text-xs text-slate-500">Last update: {latest ? formatClockLabel(latest.timestamp) : "Waiting for stream"}</p>
            </CardContent>
          </Card>

          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wide text-slate-500">SpO2</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-2">
                <p className="text-4xl font-bold text-slate-900">{latest?.spo2 ?? "--"}</p>
                <p className="pb-1 text-sm text-slate-500">%</p>
              </div>
              <p className="mt-3 text-xs text-slate-500">Scenario: {latest?.scenario ?? "N/A"}</p>
            </CardContent>
          </Card>

          <Card className={`rounded-2xl border-2 shadow-sm ${statusStyle.card}`}>
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wide text-slate-600">Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`inline-flex rounded-xl px-6 py-3 text-2xl font-extrabold tracking-wide ${statusStyle.chip}`}>
                {statusStyle.label}
              </div>
              <p className={`mt-3 text-sm font-semibold ${trendStyle.className}`}>{trendStyle.text}</p>
              <p className="mt-4 text-sm text-slate-600">Movement: {latest?.movement ?? "--"}</p>
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Heart Rate Trend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
                    <XAxis dataKey="timeLabel" tick={{ fontSize: 12, fill: "#475569" }} minTickGap={24} />
                    <YAxis
                      domain={[40, 160]}
                      tick={{ fontSize: 12, fill: "#475569" }}
                      tickCount={7}
                      width={36}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, borderColor: "#cbd5e1" }}
                      formatter={(value) => [`${value} BPM`, "Heart Rate"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="hr"
                      stroke="#e11d48"
                      strokeWidth={3}
                      dot={false}
                      isAnimationActive
                      animationDuration={350}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">SpO2 Trend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
                    <XAxis dataKey="timeLabel" tick={{ fontSize: 12, fill: "#475569" }} minTickGap={24} />
                    <YAxis
                      domain={[80, 100]}
                      tick={{ fontSize: 12, fill: "#475569" }}
                      tickCount={6}
                      width={36}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, borderColor: "#cbd5e1" }}
                      formatter={(value) => [`${value}%`, "SpO2"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="spo2"
                      stroke="#0284c7"
                      strokeWidth={3}
                      dot={false}
                      isAnimationActive
                      animationDuration={350}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <Card className="rounded-2xl border-l-4 border-l-slate-500 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Threat Level</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`inline-flex rounded-lg px-4 py-2 text-lg font-bold tracking-wide ${threatStyle.chip}`}>
                {threatLevel}
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-700">{threatStyle.note}</p>

              <div className="mt-4 border-t border-slate-200 pt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Escalation brief</p>
                {isCritical ? (
                  veteranBrief ? (
                    <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">{veteranBrief}</p>
                  ) : (
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      Escalation brief is preparing. Continue oxygen escalation and 60-second reassessment.
                    </p>
                  )
                ) : (
                  <p className="mt-2 text-sm leading-6 text-slate-700">
                    No escalation brief required while risk level is non-critical.
                  </p>
                )}

                {isCritical ? (
                  <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Trigger rule</p>
                    <p className="mt-1 text-xs text-slate-700">
                      Trigger rapid response if SpO2 stays below 90 for two checks or trend remains critical.
                    </p>
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-l-4 border-l-blue-500 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Further Actions Needed</CardTitle>
            </CardHeader>
            <CardContent>
              {isCritical ? (
                <div className="space-y-3">
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-red-700">Emergency support active</p>
                    <p className="mt-1 text-sm font-medium leading-6 text-red-900">
                      {emergencyAction ||
                        "Critical telemetry detected. Start airway, breathing, and circulation checks immediately."}
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Protocol assist</p>
                    {emergencySteps.length > 0 ? (
                      <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm leading-6 text-slate-700">
                        {emergencySteps.slice(0, 2).map((step, index) => (
                          <li key={`${step}-${index}`}>{step}</li>
                        ))}
                      </ol>
                    ) : (
                      <p className="mt-1 text-sm leading-6 text-slate-700">
                        Gemini-backed protocol retrieval is preparing response guidance. Continue baseline emergency steps.
                      </p>
                    )}
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Rapid Handoff Snapshot</p>
                    <p className="mt-1 text-sm text-slate-700">{emergencyHandoffSnapshot}</p>
                    <p className="mt-1 text-xs text-slate-500">Last telemetry: {latest ? formatClockLabel(latest.timestamp) : "N/A"}</p>
                  </div>


                </div>
              ) : emergencyAction ? (
                <p className="text-sm leading-6 text-slate-700">{emergencyAction}</p>
              ) : (
                <p className="text-sm leading-6 text-slate-700">
                  Continue observation, maintain oxygenation, and re-evaluate trend after the next vital updates.
                </p>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-l-4 border-l-red-500 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Emergency Protocols</CardTitle>
            </CardHeader>
            <CardContent>
              {isCritical && latest?.detailed_steps && latest.detailed_steps.length > 0 ? (
                <ol className="list-decimal space-y-1 pl-5 text-sm leading-6 text-slate-700">
                  {latest.detailed_steps.map((step, index) => (
                    <li key={`${step}-${index}`}>{step}</li>
                  ))}
                </ol>
              ) : isCritical ? (
                <p className="text-sm leading-6 text-slate-700">
                  Gemini is assembling retrieved protocol context. Continue core life-support actions while guidance finalizes.
                </p>
              ) : (
                <p className="text-sm leading-6 text-slate-700">No emergency protocol required while patient status remains calm.</p>
              )}
            </CardContent>
          </Card>
        </section>
      </div>

      <div className="fixed bottom-4 right-4 z-50 flex items-center gap-1 rounded-full bg-white/20 px-2 py-1 opacity-25 shadow-sm ring-1 ring-slate-300/40 backdrop-blur-md transition hover:opacity-100 focus-within:opacity-100">
        {simulationChoices.map((choice) => (
          <button
            key={choice.value}
            type="button"
            onClick={() => void handleSetSimulationScenario(choice.value)}
            aria-label={`Switch simulation to ${choice.label}`}
            title={choice.label}
            className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-semibold transition ${
              simulationChoice === choice.value
                ? "bg-slate-900 text-white"
                : "bg-white/70 text-slate-700 hover:bg-white"
            }`}
          >
            {choice.value}
          </button>
        ))}
      </div>
      <PulseAIWidget isCritical={isCritical} />
    </main>
  );
}
