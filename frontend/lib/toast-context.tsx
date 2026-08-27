"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

const TOAST_LIFETIME_MS = 3600;

const ICONS: Record<ToastType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

const COLOR_VAR: Record<ToastType, string> = {
  success: "var(--toast-success)",
  error: "var(--toast-error)",
  info: "var(--toast-info)",
};

const ToastContext = createContext<{ push: (type: ToastType, message: string) => void } | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  function push(type: ToastType, message: string) {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), TOAST_LIFETIME_MS);
  }

  function dismiss(id: string) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-5 right-5 z-[60] flex w-80 flex-col-reverse gap-2.5">
        {toasts.map((t) => {
          const Icon = ICONS[t.type];
          const color = COLOR_VAR[t.type];
          return (
            <div
              key={t.id}
              className="flex items-start gap-2.5 rounded-[10px] border bg-surface p-3 shadow-[0_10px_30px_rgba(0,0,0,0.25)]"
              style={{ borderColor: color, borderLeftWidth: 3, animation: "toastIn 0.25s cubic-bezier(.2,.8,.2,1)" }}
            >
              <Icon size={16} className="mt-0.5 flex-shrink-0" style={{ color }} />
              <div className="flex-1 text-[13px] font-semibold">{t.message}</div>
              <button
                onClick={() => dismiss(t.id)}
                className="flex h-4 w-4 flex-shrink-0 items-center justify-center text-muted"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
