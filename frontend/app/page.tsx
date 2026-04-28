"use client";

import { Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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
import { signOut } from "@/lib/auth";
import { getApiBases, getWsCandidateUrls, toApiBaseFromWs } from "@/lib/api";
import { getSupabaseClient } from "@/lib/supabase";

type RiskStatus = "Normal" | "Warning" | "Critical";
type Scenario = "Stable" | "Gradual Decline" | "Sudden Cardiac Event" | "Cardiac Arrest";
type TrendLabel = "stable" | "declining" | "critical";
type AppRole = "admin" | "user";
type ThreatLevel = "LOW" | "ELEVATED" | "HIGH" | "SEVERE";
type SimulationChoice = "1" | "2" | "3" | "4";

type PendingUser = {
  id: string;
  email: string;
  created_at: string;
};

type Patient = {
  id: string;
  name: string;
  age: number | null;
  notes: string | null;
  created_at: string;
};

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

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
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

function renderInlineBold(text: string, highlightClass: string): Array<string | JSX.Element> {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={`bold-${index}`} className={highlightClass}>
          {part.slice(2, -2)}
        </strong>
      );
    }

    return <span key={`text-${index}`}>{part}</span>;
  });
}

function renderChatContent(content: string, isUser: boolean): JSX.Element {
  const highlightClass = isUser ? "font-semibold text-white" : "font-semibold text-slate-900";
  const lines = content.split(/\r?\n/);
  const blocks: Array<{ type: "paragraph"; text: string } | { type: "list"; ordered: boolean; items: string[] }> = [];
  let listItems: string[] = [];
  let listOrdered: boolean | null = null;

  const flushList = () => {
    if (listItems.length === 0 || listOrdered === null) {
      listItems = [];
      listOrdered = null;
      return;
    }

    blocks.push({ type: "list", ordered: listOrdered, items: listItems });
    listItems = [];
    listOrdered = null;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }

    const orderedMatch = line.match(/^\d+[.)]\s+(.+)$/);
    const bulletMatch = line.match(/^[-*•]\s+(.+)$/);

    if (orderedMatch || bulletMatch) {
      const ordered = Boolean(orderedMatch);
      const itemText = (orderedMatch?.[1] ?? bulletMatch?.[1] ?? line).trim();
      if (listOrdered === null) {
        listOrdered = ordered;
      }
      if (listOrdered !== ordered) {
        flushList();
        listOrdered = ordered;
      }
      listItems.push(itemText);
      continue;
    }

    flushList();
    blocks.push({ type: "paragraph", text: line });
  }

  flushList();

  return (
    <div className="space-y-2">
      {blocks.map((block, index) => {
        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          const listClass = block.ordered ? "list-decimal" : "list-disc";
          return (
            <ListTag key={`list-${index}`} className={`${listClass} space-y-1 pl-4`}>
              {block.items.map((item, itemIndex) => (
                <li key={`item-${index}-${itemIndex}`}>{renderInlineBold(item, highlightClass)}</li>
              ))}
            </ListTag>
          );
        }

        return (
          <p key={`para-${index}`}>
            {renderInlineBold(block.text, highlightClass)}
          </p>
        );
      })}
    </div>
  );
}

function buildLocalAssistantReply(message: string, latest?: VitalsPoint): string {
  const lowered = message.trim().toLowerCase();

  const hasBleeding =
    lowered.includes("bleeding") ||
    lowered.includes("bleed") ||
    lowered.includes("hemorrhage") ||
    lowered.includes("haemorrhage") ||
    lowered.includes("hemorrage") ||
    lowered.includes("heamorrhage") ||
    lowered.includes("internal bleeding") ||
    lowered.includes("internal bleed") ||
    lowered.includes("blood loss");

  const hasLungBleed =
    lowered.includes("hemoptysis") ||
    lowered.includes("coughing blood") ||
    lowered.includes("coughing up blood") ||
    lowered.includes("lung bleeding") ||
    lowered.includes("bleeding in lungs") ||
    lowered.includes("bleeding in the lungs") ||
    lowered.includes("pulmonary hemorrhage") ||
    (hasBleeding && (lowered.includes("lung") || lowered.includes("lungs")));

  const isSevere =
    lowered.includes("severe") ||
    lowered.includes("massive") ||
    lowered.includes("critical") ||
    lowered.includes("unresponsive") ||
    lowered.includes("collapse") ||
    lowered.includes("deteriorating");

  if (!lowered) {
    return "Ask me anything about vitals, risk trend, or next-step support and I will keep it concise.";
  }

  if (hasLungBleed && isSevere) {
    return (
      "Clinical read: severe hemoptysis risk; airway compromise likely.\n"
      + "Priority actions: call emergency services now; keep patient upright or bleeding lung down; suction if trained; avoid oral intake.\n"
      + "Escalation: prepare for airway support and urgent transfer for bronchoscopic/surgical control."
    );
  }

  if (hasBleeding && isSevere) {
    return (
      "Clinical read: severe hemorrhage risk.\n"
      + "Priority actions: call emergency services now; direct pressure if external; keep patient flat if no breathing distress; no oral intake.\n"
      + "Escalation: prepare for rapid transfer, IV access, and blood products if available."
    );
  }

  if (lowered.includes("pizza") || lowered.includes("joke") || lowered.includes("movie") || lowered.includes("game") || lowered.includes("music") || lowered.includes("weather") || lowered.includes("stock") || lowered.includes("crypto") || lowered.includes("sports") || lowered.includes("politics") || lowered.includes("meme")) {
    return "I am trained for medical emergencies only. Ask me about a disease, symptom, vitals, drug option, red flag, or the next step, and I will answer in plain language.";
  }

  if (lowered.includes("drug") || lowered.includes("medicine") || lowered.includes("medication") || lowered.includes("what can i take") || lowered.includes("what should i take")) {
    if (lowered.includes("headache") || lowered.includes("head ache") || lowered.includes("hedache") || lowered.includes("migraine")) {
      return "For a simple headache, acetaminophen is usually the safest first option if there is no liver disease or allergy. Ibuprofen can help too if there is no ulcer, kidney disease, blood thinner use, or pregnancy concern. If the headache is sudden, severe, or comes with weakness, confusion, speech trouble, or vision changes, get urgent assessment instead of just treating it at home.";
    }

    if (lowered.includes("fever") || lowered.includes("temperature")) {
      return "For fever, acetaminophen or ibuprofen may help if the person can take them safely, but hydration and watching for confusion, breathing changes, or dehydration matter more. If the fever is high or the person looks unwell, get checked.";
    }

    if (lowered.includes("allergy") || lowered.includes("hives") || lowered.includes("rash") || lowered.includes("itching")) {
      return "For a mild allergic rash or itching, a non-drowsy antihistamine is often used if it is safe for the person. If there is swelling of the lips or tongue, wheezing, or trouble breathing, treat it as an emergency instead of waiting.";
    }

    if (lowered.includes("nausea") || lowered.includes("vomit") || lowered.includes("vomiting")) {
      if (lowered.includes("internal bleeding") || lowered.includes("bleeding") || lowered.includes("blood") || lowered.includes("black stool") || lowered.includes("melena") || lowered.includes("coffee ground") || lowered.includes("coffee-ground")) {
        return "Vomiting with internal bleeding is an emergency. Keep the person lying on their side if they are drowsy, do not give food, alcohol, or painkillers like ibuprofen, and get emergency help now. In hospital, the usual immediate steps are IV access, fluids or blood if needed, anti-nausea medicine such as ondansetron, and urgent evaluation for the bleeding source.";
      }

      return "For vomiting, start with small frequent sips of oral rehydration solution or clear fluids if the person can keep them down. If medication is needed, an anti-nausea medicine such as ondansetron is commonly used, and in some adults promethazine or metoclopramide may be options depending on age and other conditions. If vomiting is severe, repeated, or mixed with blood or black material, or there is abdominal pain, weakness, confusion, or dehydration, it needs urgent assessment.";
    }

    if (lowered.includes("cough") || lowered.includes("wheezing")) {
      return "For cough or wheeze, the right medicine depends on the cause. If this is known asthma, a prescribed rescue inhaler is the first step; otherwise watch the breathing rate, SpO2, and whether it is getting worse.";
    }

    if (lowered.includes("pain") || lowered.includes("back pain") || lowered.includes("abdominal pain") || lowered.includes("stomach pain") || lowered.includes("body ache")) {
      return "For pain without red flags, acetaminophen is usually the safest starting option, and ibuprofen can help if there is no ulcer, kidney disease, bleeding risk, or pregnancy concern. If the pain is severe, sudden, or localized with fever or vomiting, get it checked first.";
    }

    if (lowered.includes("disease") || lowered.includes("condition") || lowered.includes("illness") || lowered.includes("diagnosis") || lowered.includes("infection") || lowered.includes("stroke") || lowered.includes("diabetes") || lowered.includes("asthma") || lowered.includes("copd") || lowered.includes("sepsis") || lowered.includes("covid") || lowered.includes("flu") || lowered.includes("heart attack") || lowered.includes("kidney") || lowered.includes("liver") || lowered.includes("anemia") || lowered.includes("anaphylaxis") || lowered.includes("epilepsy") || lowered.includes("seizure") || lowered.includes("ulcer") || lowered.includes("appendicitis") || lowered.includes("pneumonia")) {
      return "For a disease question, I can usually give four things: the likely body system involved, the first-line medicine class if it is safe, what to do right now, and the warning signs that mean urgent care or emergency support. If you name the condition, I will make it specific.";
    }

    return "Medication choice depends on the symptom, disease, age, allergies, pregnancy, and other conditions. Tell me the problem in one line and I can suggest the safest first-line option and the red flags to watch for.";
  }

  if (
    lowered.includes("breathless") ||
    lowered.includes("breathl") ||
    lowered.includes("shortness of breath") ||
    lowered.includes("trouble breathing") ||
    lowered.includes("can't breathe") ||
    lowered.includes("cannot breathe")
  ) {
    return "If this is severe breathlessness, stay upright, keep calm, avoid exertion, and seek emergency help if it is worsening. I can also explain common rescue meds, oxygen support, and precautions in plain language.";
  }

  if (lowered === "hi" || lowered === "hello" || lowered === "hey") {
    return "Hi, I am REVIVE Assistant. I can summarize risk, suggest immediate priorities, and prepare a concise handoff line.";
  }

  if (lowered.includes("who are you") || lowered.includes("what can you do") || lowered.includes("help")) {
    return "I am REVIVE Assistant. I can interpret the latest vitals trend, provide immediate action priorities, and generate a short escalation-ready handoff summary.";
  }

  if (!latest) {
    return "I can help with symptoms, vitals, and next steps. Share current HR, SpO2, and movement, and I will keep it clear.";
  }

  const level = latest.status === "Critical" ? "high" : latest.status === "Warning" ? "elevated" : "low";
  if (level === "low") {
    return `Things look steady overall with HR ${latest.hr}, SpO2 ${latest.spo2}, and movement ${latest.movement}. Keep monitoring and tell me if you want a plain-English summary.`;
  }

  return `This is a ${level} risk pattern with HR ${latest.hr}, SpO2 ${latest.spo2}, movement ${latest.movement}, trend ${latest.trend ?? "stable"}. Keep a close watch and be ready to escalate if it worsens.`;
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
  const router = useRouter();
  const [points, setPoints] = useState<VitalsPoint[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [activeWsUrl, setActiveWsUrl] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<AppRole>("user");
  const [pendingUsers, setPendingUsers] = useState<PendingUser[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientsError, setPatientsError] = useState<string | null>(null);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [patientName, setPatientName] = useState("");
  const [patientAge, setPatientAge] = useState("");
  const [patientNotes, setPatientNotes] = useState("");
  const [patientSaving, setPatientSaving] = useState(false);
  const [patientSaveMessage, setPatientSaveMessage] = useState<string | null>(null);
  const [patientSaveError, setPatientSaveError] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "I’m the REVIVE assistant. Ask anything. I reply in quick clinical lines.",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [simulationChoice, setSimulationChoice] = useState<SimulationChoice>("1");
  const wsRef = useRef<WebSocket | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatScrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatMessages]);

  useEffect(() => {
    let mounted = true;

    const setSessionState = async (session: Session | null) => {
      if (!mounted) {
        return;
      }

      if (!session) {
        setAuthReady(false);
        setUserEmail(null);
        setUserRole("user");
        setPendingUsers([]);
        router.replace("/login");
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
          setUserRole("user");
          router.replace("/login");
          return;
        }

        if (!profile.is_approved) {
          const { count: approvedAdminCount, error: approvedAdminCountError } = await supabase
            .from("profiles")
            .select("id", { count: "exact", head: true })
            .eq("role", "admin")
            .eq("is_approved", true);

          if (!approvedAdminCountError && (approvedAdminCount ?? 0) === 0) {
            const { error: bootstrapError } = await supabase
              .from("profiles")
              .update({
                role: "admin",
                is_approved: true,
                approved_at: new Date().toISOString(),
                approved_by: session.user.id,
              })
              .eq("id", session.user.id);

            if (!bootstrapError) {
              setUserEmail(session.user.email ?? null);
              setUserRole("admin");
              setAuthReady(true);
              return;
            }
          }

          await supabase.auth.signOut();
          setAuthReady(false);
          setUserEmail(null);
          setUserRole("user");
          router.replace("/login?pending=1");
          return;
        }

        setUserEmail(session.user.email ?? null);
        setUserRole(profile.role === "admin" ? "admin" : "user");
        setAuthReady(true);
      } catch {
        setAuthReady(false);
        setUserEmail(null);
        setUserRole("user");
        router.replace("/login");
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
          router.replace("/login");
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
  }, [router]);

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
    if (!authReady) {
      return;
    }

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
  }, [authReady, apiBaseSignature]);

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

  useEffect(() => {
    if (!authReady || userRole !== "admin") {
      setPendingUsers([]);
      setPendingError(null);
      return;
    }

    let mounted = true;

    const loadPendingUsers = async () => {
      setPendingLoading(true);
      setPendingError(null);

      try {
        const supabase = getSupabaseClient();
        const { data, error } = await supabase
          .from("profiles")
          .select("id,email,created_at")
          .eq("is_approved", false)
          .order("created_at", { ascending: true });

        if (error) {
          throw error;
        }

        if (mounted) {
          const normalized = (data ?? []).filter(
            (row) => typeof row.id === "string" && typeof row.email === "string" && typeof row.created_at === "string",
          ) as PendingUser[];
          setPendingUsers(normalized);
        }
      } catch {
        if (mounted) {
          setPendingError("Unable to load pending users.");
        }
      } finally {
        if (mounted) {
          setPendingLoading(false);
        }
      }
    };

    void loadPendingUsers();

    return () => {
      mounted = false;
    };
  }, [authReady, userRole]);

  useEffect(() => {
    if (!authReady) {
      setPatients([]);
      setPatientsError(null);
      setSelectedPatientId("");
      return;
    }

    let mounted = true;

    const loadPatients = async () => {
      setPatientsLoading(true);
      setPatientsError(null);

      try {
        const supabase = getSupabaseClient();
        const { data, error } = await supabase
          .from("patients")
          .select("id,name,age,notes,created_at")
          .order("created_at", { ascending: false });

        if (error) {
          throw error;
        }

        if (!mounted) {
          return;
        }

        const normalized = (data ?? []).filter(
          (row) =>
            typeof row.id === "string" &&
            typeof row.name === "string" &&
            typeof row.created_at === "string",
        ) as Patient[];
        setPatients(normalized);

        if (!selectedPatientId && normalized.length > 0) {
          setSelectedPatientId(normalized[0].id);
        }
      } catch {
        if (mounted) {
          setPatientsError("Unable to load patients.");
        }
      } finally {
        if (mounted) {
          setPatientsLoading(false);
        }
      }
    };

    void loadPatients();

    return () => {
      mounted = false;
    };
  }, [authReady, selectedPatientId]);

  const handleApproveUser = async (profileId: string) => {
    setApprovingId(profileId);
    setPendingError(null);

    try {
      const supabase = getSupabaseClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();

      const { error } = await supabase
        .from("profiles")
        .update({
          is_approved: true,
          approved_at: new Date().toISOString(),
          approved_by: user?.id ?? null,
        })
        .eq("id", profileId);

      if (error) {
        throw error;
      }

      setPendingUsers((prev) => prev.filter((userRow) => userRow.id !== profileId));
    } catch {
      setPendingError("Approval failed. Please try again.");
    } finally {
      setApprovingId(null);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    router.replace("/login");
  };

  const handleCreatePatient = async () => {
    const trimmedName = patientName.trim();
    const ageNumber = patientAge.trim() === "" ? null : Number(patientAge);

    setPatientSaveMessage(null);
    setPatientSaveError(null);

    if (!trimmedName) {
      setPatientSaveError("Patient name is required.");
      return;
    }

    if (ageNumber !== null && (!Number.isInteger(ageNumber) || ageNumber < 0 || ageNumber > 130)) {
      setPatientSaveError("Age must be an integer between 0 and 130.");
      return;
    }

    setPatientSaving(true);
    try {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase
        .from("patients")
        .insert({
          name: trimmedName,
          age: ageNumber,
          notes: patientNotes.trim() || null,
        })
        .select("id,name,age,notes,created_at")
        .single();

      if (error || !data) {
        throw error ?? new Error("Insert failed");
      }

      const createdPatient = data as Patient;
      setPatients((prev) => [createdPatient, ...prev]);
      setSelectedPatientId(createdPatient.id);
      setPatientName("");
      setPatientAge("");
      setPatientNotes("");
      setPatientSaveMessage("Patient saved.");
    } catch {
      setPatientSaveError("Unable to save patient details.");
    } finally {
      setPatientSaving(false);
    }
  };

  const handleSendChatMessage = async () => {
    const message = chatInput.trim();
    setChatError(null);

    if (!message) {
      setChatError("Type a question or prompt first.");
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");
    setChatSending(true);

    const context = latest
      ? {
          hr: latest.hr,
          spo2: latest.spo2,
          movement: latest.movement,
          status: latest.status,
          trend: latest.trend ?? "stable",
          scenario: latest.scenario,
        }
      : null;

    try {
      let accepted = false;
      let reply = "";

      for (const base of apiBases) {
        try {
          const response = await fetch(`${base}/api/chat`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              message,
              context,
            }),
          });

          const payload = (await response.json()) as {
            ok?: boolean;
            reply?: string;
          };

          if (response.ok && payload.ok === true && typeof payload.reply === "string") {
            reply = payload.reply;
            accepted = true;
            break;
          }
        } catch {
          // Try the next configured API base.
        }
      }

      if (!accepted) {
        throw new Error("chat request failed");
      }

      setChatMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: reply,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch {
      setChatMessages((prev) => [
        ...prev,
        {
          id: `assistant-fallback-${Date.now()}`,
          role: "assistant",
          content: buildLocalAssistantReply(message, latest),
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatSending(false);
    }
  };

  const handlePrimeEmergencyPrompt = () => {
    if (!latest) {
      setChatError("Live vitals are required to prepare the emergency brief prompt.");
      return;
    }

    setChatError(null);
    setChatInput(
      `Emergency brief request: HR ${latest.hr}, SpO2 ${latest.spo2}, movement ${latest.movement}, status ${latest.status}, trend ${currentTrend}. Provide a 60-second checklist and a concise clinician handoff script based on emergency protocols.`,
    );
  };

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

  if (!authReady) {
    return (
      <main className="min-h-screen bg-slate-100 p-6">
        <div className="mx-auto max-w-md rounded-2xl bg-white p-6 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200">
          Checking session...
        </div>
      </main>
    );
  }

  return (
    <main
      className={`relative min-h-screen p-4 md:p-8 ${
        isCritical ? "bg-red-100" : "bg-slate-100"
      } transition-colors duration-500`}
    >
      {isCritical ? <div className="pointer-events-none absolute inset-0 animate-pulse bg-red-500/10" /> : null}
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-2xl bg-white px-5 py-4 shadow-sm ring-1 ring-slate-200 md:px-7 md:py-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">REVIVE Monitoring Dashboard</h1>
              <p className="text-sm text-slate-600">Manual patient workflow first. Simulator is optional fallback.</p>
              {userEmail ? <p className="mt-1 text-xs text-slate-500">Signed in: {userEmail}</p> : null}
            </div>
            <div className="flex flex-col gap-2 md:items-end">
              <button
                type="button"
                onClick={handleSignOut}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Sign out
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

        {userRole === "admin" ? (
          <Card className="rounded-2xl border-l-4 border-l-indigo-500 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Pending User Confirmations</CardTitle>
            </CardHeader>
            <CardContent>
              {pendingLoading ? <p className="text-sm text-slate-600">Loading pending users...</p> : null}
              {pendingError ? <p className="text-sm text-red-600">{pendingError}</p> : null}

              {!pendingLoading && pendingUsers.length === 0 ? (
                <p className="text-sm text-slate-600">No pending users.</p>
              ) : null}

              <div className="space-y-3">
                {pendingUsers.map((pendingUser) => (
                  <div
                    key={pendingUser.id}
                    className="flex flex-col gap-2 rounded-lg border border-slate-200 p-3 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <p className="text-sm font-medium text-slate-900">{pendingUser.email}</p>
                      <p className="text-xs text-slate-500">Requested: {formatClockLabel(pendingUser.created_at)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleApproveUser(pendingUser.id)}
                      disabled={approvingId === pendingUser.id}
                      className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {approvingId === pendingUser.id ? "Approving..." : "Approve user"}
                    </button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : null}

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Patient Details (Primary)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Active patient</label>
                  <select
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    value={selectedPatientId}
                    onChange={(event) => setSelectedPatientId(event.target.value)}
                    disabled={patientsLoading}
                  >
                    <option value="">No patient selected</option>
                    {patients.map((patient) => (
                      <option key={patient.id} value={patient.id}>
                        {patient.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Name</label>
                  <input
                    value={patientName}
                    onChange={(event) => setPatientName(event.target.value)}
                    placeholder="Patient name"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Age</label>
                  <input
                    value={patientAge}
                    onChange={(event) => setPatientAge(event.target.value)}
                    placeholder="e.g. 42"
                    inputMode="numeric"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Notes</label>
                  <input
                    value={patientNotes}
                    onChange={(event) => setPatientNotes(event.target.value)}
                    placeholder="Optional notes"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500"
                  />
                </div>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => void handleCreatePatient()}
                  disabled={patientSaving}
                  className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {patientSaving ? "Saving..." : "Save patient"}
                </button>
                {patientsError ? <p className="text-xs text-red-600">{patientsError}</p> : null}
                {patientSaveError ? <p className="text-xs text-red-600">{patientSaveError}</p> : null}
                {patientSaveMessage ? <p className="text-xs text-emerald-700">{patientSaveMessage}</p> : null}
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">REVIVE Assistant</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="max-h-72 space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-3">
                  {chatMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-6 shadow-sm ${
                          message.role === "user"
                            ? "bg-slate-900 text-white"
                            : "border border-slate-200 bg-white text-slate-700"
                        }`}
                      >
                        {renderChatContent(message.content, message.role === "user")}
                        <p className={`mt-1 text-[11px] ${message.role === "user" ? "text-slate-300" : "text-slate-400"}`}>
                          {formatClockLabel(message.timestamp)}
                        </p>
                      </div>
                    </div>
                  ))}
                  <div ref={chatScrollRef} />
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3">
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Ask anything
                  </label>
                  <textarea
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        void handleSendChatMessage();
                      }
                    }}
                    rows={3}
                    placeholder="Ask about the dashboard, workflow, or anything general..."
                    className="w-full resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500"
                  />
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs text-slate-500">
                      Gemini drives live RAG replies in quick format; responses include short escalation-focused guidance.
                    </p>
                    <button
                      type="button"
                      onClick={() => void handleSendChatMessage()}
                      disabled={chatSending}
                      className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {chatSending ? "Thinking..." : "Send message"}
                    </button>
                  </div>
                  {chatError ? <p className="mt-2 text-xs text-red-600">{chatError}</p> : null}
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-6 rounded-2xl bg-slate-950 p-6 shadow-sm ring-1 ring-slate-800 md:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Current Heart Rate</p>
            <p className={`font-mono text-6xl font-bold tracking-wider ${valueColorMap[hrStatus]}`}>
              {latest?.hr ?? "--"}
              <span className="ml-2 text-xl text-slate-300">BPM</span>
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Current SpO2</p>
            <p className={`font-mono text-6xl font-bold tracking-wider ${valueColorMap[spo2Status]}`}>
              {latest?.spo2 ?? "--"}
              <span className="ml-2 text-xl text-slate-300">%</span>
            </p>
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

                  <button
                    type="button"
                    onClick={handlePrimeEmergencyPrompt}
                    className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700"
                  >
                    Prepare emergency brief
                  </button>
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
    </main>
  );
}
