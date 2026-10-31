export function Brand({ large = false }: { large?: boolean }) {
  return (
    <div className={`brand ${large ? "brand-large" : ""}`}>
      <svg
        role="img"
        aria-label="SubCadence brand mark"
        width="36"
        height="36"
        viewBox="0 0 36 36"
        fill="none"
      >
        <rect x="1" y="1" width="34" height="34" rx="9" fill="#4f46e5" />
        <path
          d="M26 11H16a5 5 0 0 0 0 10h4a3 3 0 0 1 0 6H10M10 25h10a5 5 0 0 0 0-10h-4a3 3 0 0 1 0-6h10"
          stroke="#e2dfff"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="m24 7 3 2-3 2M12 25l-3 2 3 2"
          stroke="#4cd7f6"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div>
        <strong>SubCadence</strong>
        <span>SUBSCRIPTION WORKSPACE</span>
      </div>
    </div>
  );
}
