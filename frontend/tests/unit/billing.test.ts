import { afterEach, expect, it, vi } from "vitest";
import { ApiClient, decodeJSON } from "../../src/lib/api";
import { formatINR } from "../../src/lib/format";

afterEach(() => vi.unstubAllGlobals());
it("sends explicit billing dates with bearer auth and distinct preview/run paths", async () => {
  const fetcher = vi
    .fn()
    .mockImplementation(() =>
      Promise.resolve(
        new Response('{"projected_or_actual_total_paise":9223372036854775807}'),
      ),
    );
  vi.stubGlobal("fetch", fetcher);
  const client = new ApiClient("http://localhost/api/v1");
  client.setToken("synthetic-unit-token");
  const preview = await client.billingPreview("2026-10-31");
  await client.billingRun("2026-10-31");
  expect(preview.projected_or_actual_total_paise).toBe(9223372036854775807n);
  expect(fetcher.mock.calls.map((call) => call[0])).toEqual([
    "http://localhost/api/v1/billing/preview",
    "http://localhost/api/v1/billing/run",
  ]);
  for (const [, options] of fetcher.mock.calls) {
    expect(options.method).toBe("POST");
    expect(options.headers.Authorization).toBe("Bearer synthetic-unit-token");
    expect(JSON.parse(options.body)).toEqual({ as_of: "2026-10-31" });
  }
});
it("loads filtered persisted invoices and posts confirmation/cancellation without invented payment data", async () => {
  const fetcher = vi
    .fn()
    .mockImplementation(() => Promise.resolve(new Response("{}")));
  vi.stubGlobal("fetch", fetcher);
  const client = new ApiClient("http://localhost/api/v1");
  await client.invoices({
    status: "draft",
    subscription_id: 12,
    due_from: "2026-01-01",
    limit: 10,
    offset: 20,
    search: "INV-",
  });
  await client.invoice(3);
  await client.invoiceAction(3, "confirm");
  await client.invoiceAction(3, "cancel");
  expect(fetcher.mock.calls[0][0]).toContain(
    "status=draft&subscription_id=12&due_from=2026-01-01&limit=10&offset=20&search=INV-",
  );
  expect(fetcher.mock.calls.slice(1).map((call) => call[0])).toEqual([
    "http://localhost/api/v1/invoices/3",
    "http://localhost/api/v1/invoices/3/confirm",
    "http://localhost/api/v1/invoices/3/cancel",
  ]);
  expect(fetcher.mock.calls[2][1].body).toBeUndefined();
});
it("decodes nested invoice and discount paise exactly including report sums beyond SQLite range", () => {
  const value = decodeJSON(
    '{"total_paise":18446744073709551614,"lines":[{"subtotal_paise":9007199254740993,"discount_paise":1,"tax_paise":123}],"applied_discount_snapshot":{"value_paise":null,"rate_basis_points":1000}}',
  ) as {
    total_paise: bigint;
    lines: {
      subtotal_paise: bigint;
      discount_paise: bigint;
      tax_paise: bigint;
    }[];
  };
  expect(value.total_paise).toBe(18446744073709551614n);
  expect(
    value.lines[0].subtotal_paise -
      value.lines[0].discount_paise +
      value.lines[0].tax_paise,
  ).toBe(9007199254741115n);
  expect(formatINR(value.total_paise)).toBe("₹1,84,46,74,40,73,70,95,516.14");
});
