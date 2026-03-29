import { type CSSProperties } from "react";

type PaginationProps = {
  currentPage: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

export default function Pagination({ currentPage, totalItems, pageSize, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(totalItems / pageSize);
  if (totalPages <= 1) return null;

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderTop: "1px solid var(--border)", background: "rgba(0,0,0,0.2)" }}>
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
        Showing {(currentPage - 1) * pageSize + 1} to {Math.min(currentPage * pageSize, totalItems)} of {totalItems} entries
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <button 
          onClick={(e) => { e.stopPropagation(); onPageChange(currentPage - 1); }} 
          disabled={currentPage === 1}
          style={btnStyle(currentPage === 1)}
        >
          Previous
        </button>
        <div style={{ display: "flex", alignItems: "center", padding: "0 12px", color: "var(--text-secondary)", fontSize: "0.85rem", fontWeight: 600 }}>
          {currentPage} / {totalPages}
        </div>
        <button 
          onClick={(e) => { e.stopPropagation(); onPageChange(currentPage + 1); }} 
          disabled={currentPage === totalPages}
          style={btnStyle(currentPage === totalPages)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

const btnStyle = (disabled: boolean): CSSProperties => ({
  background: disabled ? "transparent" : "rgba(255,255,255,0.05)",
  border: "1px solid var(--border)",
  color: disabled ? "var(--text-muted)" : "var(--text-bright)",
  padding: "6px 12px",
  borderRadius: 6,
  fontSize: "0.85rem",
  cursor: disabled ? "not-allowed" : "pointer",
  transition: "all 0.2s",
  opacity: disabled ? 0.5 : 1
});
