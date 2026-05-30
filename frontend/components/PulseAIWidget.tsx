"use client";

import React, { useState, useRef, useEffect } from "react";

interface PulseAIWidgetProps {
  isCritical: boolean;
}

export function PulseAIWidget({ isCritical }: PulseAIWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ x: 20, y: 20 });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; initialX: number; initialY: number } | null>(null);
  const widgetRef = useRef<HTMLDivElement>(null);

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

  if (!isOpen) {
    return (
      <div className="fixed bottom-6 right-6 z-50">
        <button
          onClick={() => !isCritical && setIsOpen(true)}
          disabled={isCritical}
          className={`flex items-center gap-2 rounded-full px-6 py-3 font-semibold text-white shadow-lg transition-all duration-300 hover:-translate-y-1 ${
            isCritical
              ? "cursor-not-allowed bg-slate-400 opacity-50"
              : "bg-gradient-to-r from-indigo-600 to-blue-500 hover:shadow-xl hover:from-indigo-500 hover:to-blue-400"
          }`}
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Pulse AI Diagnostics
        </button>
        {isCritical && (
          <div className="absolute -top-10 right-0 w-48 rounded bg-red-100 p-2 text-center text-xs font-semibold text-red-700 shadow-sm ring-1 ring-red-200">
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
      className={`flex h-[550px] w-[400px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 transition-opacity ${
        isCritical ? "pointer-events-none opacity-50 ring-red-500" : "ring-slate-200"
      }`}
    >
      {/* Draggable Header */}
      <div
        onMouseDown={handleMouseDown}
        className={`flex cursor-move items-center justify-between px-4 py-3 ${
          isCritical ? "bg-red-50" : "bg-gradient-to-r from-slate-900 to-slate-800"
        }`}
      >
        <div className="flex items-center gap-2">
          <svg className={`h-4 w-4 ${isCritical ? "text-red-500" : "text-blue-400"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <h3 className={`font-semibold tracking-wide ${isCritical ? "text-red-700" : "text-white"}`}>
            Pulse AI Diagnostics
          </h3>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className={`rounded-full p-1 transition-colors ${
            isCritical ? "text-red-700 hover:bg-red-100" : "text-slate-300 hover:bg-slate-700 hover:text-white"
          }`}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content Area */}
      <div className="relative flex-1 bg-slate-50">
        {isCritical ? (
          <div className="flex h-full flex-col items-center justify-center p-6 text-center">
            <svg className="mb-4 h-12 w-12 text-red-500 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-sm font-semibold text-red-700">Diagnostics Disabled</p>
            <p className="mt-2 text-xs text-red-600">
              Pulse AI is locked during an active Golden Hour emergency. Please focus on immediate triage and vitals stabilization.
            </p>
          </div>
        ) : (
          <iframe
            src="https://pulse-ai-dk.vercel.app"
            title="Pulse AI Diagnostic Tool"
            className="h-full w-full border-0"
            allow="camera; microphone"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          />
        )}
      </div>
    </div>
  );
}
