import { type ReactNode, useEffect } from "react";

type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
};

export default function Modal({ isOpen, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => { document.body.style.overflow = "unset"; };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.7)", padding: 24,
        backdropFilter: "blur(6px)",
        animation: "fadeIn 0.2s ease",
      }}
      onClick={onClose}
    >
      <div
        className="panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%", maxWidth: 900, maxHeight: "90vh",
          overflowY: "auto", position: "relative",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
          background: "var(--bg-secondary)",
          animation: "slideUp 0.25s ease",
        }}
      >
        <div style={{
          position: "sticky", top: 0, zIndex: 10,
          background: "var(--bg-secondary)",
          padding: "18px 24px",
          borderBottom: "1px solid var(--border)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "var(--text-bright)" }}>{title}</h2>
          <button
            onClick={onClose}
            style={{
              background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)",
              color: "var(--text-muted)", cursor: "pointer",
              width: 32, height: 32, borderRadius: "var(--radius-sm)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "1.1rem", lineHeight: 1, transition: "all 0.15s",
            }}
          >
            &times;
          </button>
        </div>
        <div style={{ padding: 24 }}>
          {children}
        </div>
      </div>
    </div>
  );
}
