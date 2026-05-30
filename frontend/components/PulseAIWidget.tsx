"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, Image as ImageIcon, Loader2, X, Plus, Sparkles, GripVertical, Paperclip, Trash2 } from "lucide-react";

interface PulseAIWidgetProps {
  isCritical: boolean;
}

type Message = {
  role: "user" | "assistant";
  content: string;
  imageUrl?: string;
};

const HF_TOKEN = process.env.NEXT_PUBLIC_HF_TOKEN || "";
const MODEL_URL =
  "https://api-inference.huggingface.co/models/meta-llama/Llama-3.2-11B-Vision-Instruct/v1/chat/completions";

export function PulseAIWidget({ isCritical }: PulseAIWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ x: 24, y: 24 });
  const [size, setSize] = useState({ width: 420, height: 560 });
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  const dragRef = useRef<{
    startX: number;
    startY: number;
    initialX: number;
    initialY: number;
  } | null>(null);
  const resizeRef = useRef<{
    startX: number;
    startY: number;
    initialW: number;
    initialH: number;
  } | null>(null);
  const widgetRef = useRef<HTMLDivElement>(null);

  // Chat state
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm the REVIVE diagnostic assistant powered by Pulse AI. Describe your symptoms, ask medical questions, or upload an image for analysis.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ────────────────────── Lifecycle ────────────────────── */
  useEffect(() => {
    if (typeof window !== "undefined") {
      setPosition({ x: 24, y: window.innerHeight - 560 - 24 });
      setIsInitialized(true);
    }
  }, []);

  useEffect(() => {
    if (isCritical) setIsOpen(false);
  }, [isCritical]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ────────────────────── Drag ────────────────────── */
  const handleDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isCritical) return;
    setIsDragging(true);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: position.x,
      initialY: position.y,
    };
  };

  const handleDragMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging || !dragRef.current) return;
      setPosition({
        x: dragRef.current.initialX + (e.clientX - dragRef.current.startX),
        y: dragRef.current.initialY + (e.clientY - dragRef.current.startY),
      });
    },
    [isDragging]
  );

  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
    dragRef.current = null;
  }, []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", handleDragMove);
      window.addEventListener("mouseup", handleDragEnd);
    }
    return () => {
      window.removeEventListener("mousemove", handleDragMove);
      window.removeEventListener("mouseup", handleDragEnd);
    };
  }, [isDragging, handleDragMove, handleDragEnd]);

  /* ────────────────────── Resize ────────────────────── */
  const handleResizeStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setIsResizing(true);
    resizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialW: size.width,
      initialH: size.height,
    };
  };

  const handleResizeMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing || !resizeRef.current) return;
      const newW = Math.max(
        340,
        resizeRef.current.initialW + (e.clientX - resizeRef.current.startX)
      );
      const newH = Math.max(
        400,
        resizeRef.current.initialH + (e.clientY - resizeRef.current.startY)
      );
      setSize({ width: newW, height: newH });
    },
    [isResizing]
  );

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false);
    resizeRef.current = null;
  }, []);

  useEffect(() => {
    if (isResizing) {
      window.addEventListener("mousemove", handleResizeMove);
      window.addEventListener("mouseup", handleResizeEnd);
    }
    return () => {
      window.removeEventListener("mousemove", handleResizeMove);
      window.removeEventListener("mouseup", handleResizeEnd);
    };
  }, [isResizing, handleResizeMove, handleResizeEnd]);

  /* ────────────────────── Image Upload ────────────────────── */
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedImage(file);
    const reader = new FileReader();
    reader.onloadend = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const clearImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  /* ────────────────────── Chat ────────────────────── */
  const sendMessage = async () => {
    if ((!input.trim() && !selectedImage) || isLoading) return;

    const userContent = input.trim() || (selectedImage ? "Analyze this image" : "");
    setInput("");
    const userMsg: Message = {
      role: "user",
      content: userContent,
      imageUrl: imagePreview || undefined,
    };

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setIsLoading(true);

    // Build the HF API messages payload
    const apiMessages = newMessages.map((m) => {
      if (m.imageUrl) {
        return {
          role: m.role,
          content: [
            { type: "text" as const, text: m.content },
            { type: "image_url" as const, image_url: { url: m.imageUrl } },
          ],
        };
      }
      return { role: m.role, content: m.content };
    });

    clearImage();

    try {
      const response = await fetch(MODEL_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${HF_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "meta-llama/Llama-3.2-11B-Vision-Instruct",
          messages: apiMessages,
          max_tokens: 600,
          stream: false,
        }),
      });

      if (!response.ok) throw new Error("API request failed");

      const data = await response.json();
      const reply =
        data.choices?.[0]?.message?.content || "No response generated.";

      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "⚠️ Unable to reach the AI model right now. Please check your connection and try again.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  /* ────────────────────── Render ────────────────────── */
  if (!isInitialized) return null;

  /* ── Closed state: floating pill button ── */
  if (!isOpen) {
    return (
      <div className="fixed bottom-6 left-6 z-50 group">
        <button
          onClick={() => !isCritical && setIsOpen(true)}
          disabled={isCritical}
          className="revive-fab"
          style={{
            opacity: isCritical ? 0.5 : 1,
            cursor: isCritical ? "not-allowed" : "pointer",
          }}
        >
          <span className="revive-fab__glow" />
          <Sparkles className="h-5 w-5 relative z-10" />
          <span className="relative z-10 font-semibold tracking-wide">
            REVIVE Assistant
          </span>
        </button>
        {isCritical && (
          <div className="revive-fab__locked">
            Locked during Golden Hour
          </div>
        )}
      </div>
    );
  }

  /* ── Open state: full widget ── */
  return (
    <div
      ref={widgetRef}
      className={`revive-widget ${isCritical ? "revive-widget--critical" : ""}`}
      style={{
        position: "fixed",
        left: `${position.x}px`,
        top: `${position.y}px`,
        zIndex: 9999,
        width: `${size.width}px`,
        height: `${size.height}px`,
      }}
    >
      {/* ── Glass layers ── */}
      <div className="revive-widget__glass" />
      <div className="revive-widget__noise" />

      {/* ── Header / drag handle ── */}
      <div
        onMouseDown={handleDragStart}
        className={`revive-widget__header ${isCritical ? "revive-widget__header--critical" : ""}`}
      >
        <div className="revive-widget__header-left">
          <div className="revive-widget__logo">
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </div>
          <h3 className="revive-widget__title">REVIVE Assistant</h3>
          <span className="revive-widget__badge">AI</span>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="revive-widget__close"
        >
          <X className="h-4 w-4" strokeWidth={2.5} />
        </button>
      </div>

      {/* ── Body ── */}
      <div className="revive-widget__body">
        {isCritical ? (
          <div className="revive-widget__locked-body">
            <div className="revive-widget__locked-icon">
              <X className="h-10 w-10" strokeWidth={2} />
            </div>
            <p className="revive-widget__locked-title">Assistant Locked</p>
            <p className="revive-widget__locked-desc">
              REVIVE Assistant is disabled during an active Golden Hour
              emergency to ensure focus on immediate triage and vitals
              stabilization.
            </p>
          </div>
        ) : (
          <>
            {/* Chat Messages */}
            <div className="revive-widget__messages">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`revive-msg ${msg.role === "user" ? "revive-msg--user" : "revive-msg--assistant"}`}
                  style={{ animationDelay: `${i * 0.05}s` }}
                >
                  <div
                    className={`revive-msg__bubble ${msg.role === "user" ? "revive-msg__bubble--user" : "revive-msg__bubble--assistant"}`}
                  >
                    {msg.imageUrl && (
                      <img
                        src={msg.imageUrl}
                        alt="Uploaded"
                        className="revive-msg__image"
                      />
                    )}
                    <span className="revive-msg__text">{msg.content}</span>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="revive-msg revive-msg--assistant">
                  <div className="revive-msg__bubble revive-msg__bubble--assistant revive-msg__typing">
                    <span className="revive-msg__dot" />
                    <span className="revive-msg__dot" />
                    <span className="revive-msg__dot" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Image preview */}
            {imagePreview && (
              <div className="revive-widget__img-preview">
                <img src={imagePreview} alt="Preview" />
                <button onClick={clearImage} className="revive-widget__img-remove">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            )}

            {/* Input Area */}
            <div className="revive-widget__input-area">
              <div className="revive-widget__input-row">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageSelect}
                  className="hidden"
                  style={{ display: "none" }}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="revive-widget__attach"
                  title="Attach image"
                >
                  <Paperclip className="h-4 w-4" />
                </button>
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                  placeholder="Describe symptoms or ask a question…"
                  className="revive-widget__text-input"
                />
                <button
                  onClick={sendMessage}
                  disabled={isLoading || (!input.trim() && !selectedImage)}
                  className="revive-widget__send"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── Resize handle ── */}
      {!isCritical && (
        <div
          onMouseDown={handleResizeStart}
          className="revive-widget__resize-handle"
          title="Drag to resize"
        >
          <svg width="10" height="10" viewBox="0 0 10 10">
            <path d="M9 1L1 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M9 5L5 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M9 8L8 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
      )}
    </div>
  );
}
