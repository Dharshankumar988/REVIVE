"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { X, Sparkles } from "lucide-react";

interface PulseAIWidgetProps {
  isCritical: boolean;
}

export function PulseAIWidget({ isCritical }: PulseAIWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ x: 24, y: 24 });
  const [size, setSize] = useState({ width: 500, height: 500 });
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
    edge: 'right' | 'bottom' | 'both';
  } | null>(null);
  const widgetRef = useRef<HTMLDivElement>(null);

  /* ────────────────────── Lifecycle ────────────────────── */
  useEffect(() => {
    if (typeof window !== "undefined") {
      setPosition({ x: 24, y: window.innerHeight - 500 - 24 });
      setIsInitialized(true);
    }
  }, []);

  useEffect(() => {
    if (isCritical) setIsOpen(false);
  }, [isCritical]);

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
  const handleResizeMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing || !resizeRef.current) return;
      const r = resizeRef.current;
      
      let newW = size.width;
      let newH = size.height;

      if (r.edge === 'right' || r.edge === 'both') {
        newW = Math.max(340, r.initialW + (e.clientX - r.startX));
      }
      if (r.edge === 'bottom' || r.edge === 'both') {
        newH = Math.max(400, r.initialH + (e.clientY - r.startY));
      }
      
      setSize({ width: newW, height: newH });
    },
    [isResizing, size]
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

  /* ────────────────────── Render ────────────────────── */
  if (!isInitialized) return null;

  /* ── Closed state: floating pill button ── */
  if (!isOpen) {
    return (
      <>
        {/* Hidden background iframe to perform the login securely behind the scenes */}
        <iframe
          src="https://pulse-ai-dk.vercel.app/login?email=dkb988@gmail&password=Doctor@123"
          style={{ display: "none" }}
          title="Background Auth"
        />
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
              Pulse AI
            </span>
          </button>
          {isCritical && (
            <div className="revive-fab__locked">
              Locked during Golden Hour
            </div>
          )}
        </div>
      </>
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
          <h3 className="revive-widget__title">Pulse AI</h3>
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
      <div className="revive-widget__body" style={{ padding: 0, overflow: 'hidden', position: 'relative' }}>
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
          <div style={{ width: '100%', height: '100%', position: 'relative' }}>
            {/* Iframe for Pulse AI - using login route with redirect params */}
            <iframe
              name="pulse-ai-iframe"
              src="https://pulse-ai-dk.vercel.app/login?email=dkb988@gmail&password=Doctor@123&redirect=/assistant&callbackUrl=/assistant"
              style={{ width: "100%", height: "100%", border: "none" }}
              title="Pulse AI Assistant"
              allow="clipboard-read; clipboard-write; microphone"
            />
            
            {/* Overlay if iframe is dragging/resizing to prevent iframe from swallowing mouse events */}
            {(isDragging || isResizing) && (
              <div style={{ position: 'absolute', inset: 0, zIndex: 100, background: 'transparent' }} />
            )}
          </div>
        )}
      </div>

      {/* ── Resize handles ── */}
      {!isCritical && (
        <>
          {/* Right edge handle */}
          <div
            onMouseDown={(e) => {
              e.stopPropagation();
              setIsResizing(true);
              resizeRef.current = { startX: e.clientX, startY: e.clientY, initialW: size.width, initialH: size.height, edge: 'right' };
            }}
            style={{ position: 'absolute', top: 0, right: -5, bottom: 0, width: '10px', cursor: 'ew-resize', zIndex: 9999 }}
          />
          {/* Bottom edge handle */}
          <div
            onMouseDown={(e) => {
              e.stopPropagation();
              setIsResizing(true);
              resizeRef.current = { startX: e.clientX, startY: e.clientY, initialW: size.width, initialH: size.height, edge: 'bottom' };
            }}
            style={{ position: 'absolute', bottom: -5, left: 0, right: 0, height: '10px', cursor: 'ns-resize', zIndex: 9999 }}
          />
          {/* Bottom-right corner handle */}
          <div
            onMouseDown={(e) => {
              e.stopPropagation();
              setIsResizing(true);
              resizeRef.current = { startX: e.clientX, startY: e.clientY, initialW: size.width, initialH: size.height, edge: 'both' };
            }}
            className="revive-widget__resize-handle"
            title="Drag to resize"
            style={{ position: 'absolute', bottom: -5, right: -5, zIndex: 10000, width: '20px', height: '20px', cursor: 'nwse-resize' }}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" style={{ position: 'absolute', bottom: '8px', right: '8px', pointerEvents: 'none' }}>
              <path d="M9 1L1 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M9 5L5 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M9 8L8 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
        </>
      )}
    </div>
  );
}
