import { afterEach, expect, it, vi } from "vitest";
import { parseINR } from "../../src/lib/format";
import { ApiClient } from "../../src/lib/api";
afterEach(() => vi.unstubAllGlobals());
it("parses exact INR without binary floating point", () => {
  expect(parseINR("90071992547409.93")).toBe(9007199254740993n);
  expect(parseINR("0.1")).toBe(10n);
  expect(parseINR("1")).toBe(100n);
  for (const invalid of [
    "1.001",
    "1e4",
    "-1",
    "1,000",
    "NaN",
    "92233720368547758.08",
  ])
    expect(() => parseINR(invalid)).toThrow();
});
it("sends exact payment integers and idempotency data, without truncation", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response('{"id":1,"amount_paise":9007199254740993}'),
    );
  vi.stubGlobal("fetch", fetcher);
  const api = new ApiClient("http://localhost/api/v1");
  const result = await api.recordPayment(2, {
    amount_paise: 9007199254740993n,
    method: "upi",
    payment_date: "2026-10-31",
    reference: null,
    note: null,
    idempotency_key: "synthetic",
  });
  expect(fetcher.mock.calls[0][1].body).toContain(
    '"amount_paise":9007199254740993',
  );
  expect(result.amount_paise).toBe(9007199254740993n);
});
