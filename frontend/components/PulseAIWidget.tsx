"use client";

import React, { useState, useRef, useEffect } from "react";

interface PulseAIWidgetProps {
  isCritical: boolean;
}

export function PulseAIWidget({ isCritical }: PulseAIWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ x: 24, y: 24 });
  const [isDragging, setIsDragging] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; initialX: number; initialY: number } | null>(null);
  const widgetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initialize Y position to bottom left
    if (typeof window !== "undefined") {
      setPosition({ x: 24, y: window.innerHeight - 550 - 24 });
      setIsInitialized(true);
    }
  }, []);

  // Auto-close and lock if critical
  useEffect(() => {
    if (isCritical) {
      setIsOpen(false);
    }
  }, [isCritical]);

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isCritical) return;
    setIsDragging(true);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: position.x,
      initialY: position.y,
    };
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging || !dragRef.current) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    setPosition({
      x: dragRef.current.initialX + dx,
      y: dragRef.current.initialY + dy,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    dragRef.current = null;
  };

  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    } else {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    }
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, handleMouseMove]);

  if (!isInitialized) return null;

  if (!isOpen) {
    return (
      <div className="fixed bottom-6 left-6 z-50">
        <button
          onClick={() => !isCritical && setIsOpen(true)}
          disabled={isCritical}
          className={`flex items-center gap-2 rounded-full px-6 py-3 font-semibold text-slate-800 shadow-xl backdrop-blur-xl border border-white/40 transition-all duration-500 hover:-translate-y-1 hover:shadow-2xl ${
            isCritical
              ? "cursor-not-allowed bg-white/30 opacity-60"
              : "bg-white/40 hover:bg-white/60"
          }`}
        >
          <svg className="h-5 w-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          REVIVE Assistant
        </button>
        {isCritical && (
          <div className="absolute -top-12 left-0 w-48 rounded-xl bg-red-500/20 backdrop-blur-md p-2 text-center text-xs font-semibold text-red-900 shadow-sm border border-red-500/30">
            Locked during Golden Hour
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      ref={widgetRef}
      style={{
        position: "fixed",
        left: `${position.x}px`,
        top: `${position.y}px`,
        zIndex: 50,
      }}
      className={`flex h-[550px] w-[400px] flex-col overflow-hidden rounded-3xl shadow-2xl backdrop-blur-2xl transition-opacity ${
        isCritical ? "pointer-events-none opacity-50 bg-red-500/10 border border-red-500/30 shadow-glow-red" : "bg-white/20 border border-white/40"
      }`}
    >
      {/* Draggable Header */}
      <div
        onMouseDown={handleMouseDown}
        className={`flex cursor-move items-center justify-between px-5 py-4 ${
          isCritical ? "bg-red-500/20 border-b border-red-500/30" : "bg-white/30 border-b border-white/40 shadow-sm"
        }`}
      >
        <div className="flex items-center gap-3">
          <div className={`p-1.5 rounded-full ${isCritical ? "bg-red-500/30" : "bg-white/50 backdrop-blur-sm"}`}>
            <svg className={`h-4 w-4 ${isCritical ? "text-red-900" : "text-indigo-700"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h3 className={`font-semibold tracking-wide ${isCritical ? "text-red-950" : "text-slate-800"}`}>
            REVIVE Assistant
          </h3>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className={`rounded-full p-2 transition-colors ${
            isCritical ? "text-red-900 hover:bg-red-500/30" : "text-slate-600 hover:bg-white/50 hover:text-slate-900"
          }`}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content Area */}
      <div className="relative flex-1 bg-white/40 backdrop-blur-md">
        {isCritical ? (
          <div className="flex h-full flex-col items-center justify-center p-8 text-center">
            <div className="rounded-full bg-red-500/20 p-4 mb-4 border border-red-500/30">
              <svg className="h-10 w-10 text-red-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-lg font-bold text-red-950">Assistant Locked</p>
            <p className="mt-2 text-sm text-red-900/80 leading-relaxed">
              REVIVE Assistant is disabled during an active Golden Hour emergency to ensure focus on immediate triage and vitals stabilization.
            </p>
          </div>
        ) : (
          <iframe
            src="https://pulse-ai-dk.vercel.app"
            title="REVIVE Assistant Diagnostic Tool"
            className="h-full w-full border-0 bg-transparent"
            allow="camera; microphone"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          />
        )}
      </div>
    </div>
  );
}
