const indianInteger = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
});

export function parseINR(value: string): bigint {
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!match)
    throw new Error(
      "Enter an INR amount with at most two decimal places, without commas.",
    );
  const amount =
    BigInt(match[1]) * 100n + BigInt((match[2] || "").padEnd(2, "0"));
  if (amount > 9223372036854775807n)
    throw new Error("Amount exceeds the supported range.");
  return amount;
}

export function formatINR(paise: bigint): string {
  const amount = paise < 0n ? -paise : paise;
  return `${paise < 0n ? "−" : ""}₹${indianInteger.format(amount / 100n)}.${(amount % 100n).toString().padStart(2, "0")}`;
}

export function formatRate(basisPoints: number): string {
  const value = BigInt(basisPoints);
  const fraction = (value % 100n)
    .toString()
    .padStart(2, "0")
    .replace(/0+$/, "");
  return `${value / 100n}${fraction ? `.${fraction}` : ""}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  // Billing dates are calendar dates, independent of the browser's timezone.
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00Z`));
}

export function todayInIndia(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
export function initials(value: string): string {
  return value
    .split(/[\s@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
