import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, decodeJSON } from "../../src/lib/api";
import { formatDate, formatINR, formatRate } from "../../src/lib/format";
import { allowedActions } from "../../src/lib/lifecycle";
import { chargesBeforeTax } from "../../src/components/subscription-data";
import type { Subscription } from "../../src/lib/types";

afterEach(() => vi.unstubAllGlobals());
describe("Exact financial values", () => {
  it.each([
    [0n, "₹0.00"],
    [1n, "₹0.01"],
    [123456789n, "₹12,34,567.89"],
    [9223372036854775807n, "₹92,23,37,20,36,85,47,758.07"],
  ])("formats %s paise without floats", (value, expected) => {
    expect(formatINR(value)).toBe(expected);
  });
  it("decodes the full SQLite integer range losslessly", () => {
    expect(
      decodeJSON(
        '{"id":1,"price_paise":9223372036854775807,"quantity":2,"amount_paise":1}',
      ),
    ).toEqual({
      id: 1,
      price_paise: 9223372036854775807n,
      quantity: 2,
      amount_paise: 1n,
    });
  });
  it("does not reinterpret text or truncate oversized IDs", () => {
    expect(decodeJSON('{"notes":"price_paise: 9223372036854775807"}')).toEqual({
      notes: "price_paise: 9223372036854775807",
    });
    expect(() => decodeJSON('{"id":9223372036854775807}')).toThrow(
      /identifier/,
    );
    expect(() => decodeJSON('{"amount_paise":1.5}')).toThrow(/non-integer/);
  });
  it("shows rates and calendar dates exactly", () => {
    expect(formatRate(1800)).toBe("18%");
    expect(formatRate(125)).toBe("1.25%");
    expect(formatDate("2026-01-01")).toBe("01 Jan 2026");
    expect(formatDate(null)).toBe("—");
  });
  it("sums base and line amounts as integers", () => {
    expect(
      chargesBeforeTax({
        recurring_base_price_paise: 9007199254740993n,
        lines: [{ amount_paise: 9n }],
      } as Subscription),
    ).toBe(9007199254741002n);
  });
});
describe("Fetch API client", () => {
  it("sends bearer authentication and exact action bodies", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response('{"id":1}', { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    const api = new ApiClient("http://localhost:8000/api/v1/");
    api.setToken("synthetic-test-token");
    await api.action(1, "quotation", {
      as_of: "2026-01-15",
      validity_days: 14,
    });
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/subscriptions/1/quotation");
    expect(options.headers.Authorization).toBe("Bearer synthetic-test-token");
    expect(JSON.parse(options.body)).toEqual({
      as_of: "2026-01-15",
      validity_days: 14,
    });
    expect(options.credentials).toBe("omit");
  });
  it("encodes actual server pagination and filters", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response('{"items":[],"total":0,"limit":20,"offset":20}'),
      );
    vi.stubGlobal("fetch", fetcher);
    await new ApiClient("http://localhost/api/v1").subscriptions({
      status: "active",
      search: "SUB-000001",
      limit: 20,
      offset: 20,
    });
    expect(fetcher.mock.calls[0][0]).toContain(
      "status=active&search=SUB-000001&limit=20&offset=20",
    );
  });
  it("expires protected sessions on 401, without expiring failed public login", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockImplementation(() =>
          Promise.resolve(
            new Response('{"detail":"Invalid credentials"}', { status: 401 }),
          ),
        ),
    );
    const api = new ApiClient("http://localhost/api/v1");
    const expire = vi.fn();
    api.setUnauthorizedHandler(expire);
    await expect(
      api.login("test@example.com", "synthetic-password"),
    ).rejects.toBeInstanceOf(ApiError);
    expect(expire).not.toHaveBeenCalled();
    await expect(api.me()).rejects.toMatchObject({ status: 401 });
    expect(expire).toHaveBeenCalledOnce();
  });
  it("surfaces validation errors and network failures without claiming success", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            '{"detail":[{"loc":["body","lines",0,"quantity"],"msg":"Must be positive"}]}',
            { status: 422 },
          ),
        ),
    );
    const api = new ApiClient("http://localhost/api/v1");
    await expect(api.me()).rejects.toThrow(
      "lines.0.quantity: Must be positive",
    );
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(api.me()).rejects.toMatchObject({ status: 0 });
  });
});
describe("Lifecycle permissions", () => {
  const active = {
    status: "active",
    is_paused: false,
    commercial_snapshot: {
      plan: { pausable: true, closable: true, renewable: true },
    },
  } as Subscription;
  it("uses accepted flags and never grants customer actions", () => {
    expect(allowedActions(active, "admin")).toEqual([
      "pause",
      "renew",
      "close",
    ]);
    expect(allowedActions({ ...active, is_paused: true }, "staff")).toEqual([
      "resume",
      "renew",
      "close",
    ]);
    expect(allowedActions(active, "customer")).toEqual([]);
  });
  it("does not offer unsupported jumps or closed renewals", () => {
    expect(allowedActions({ ...active, status: "draft" }, "staff")).toEqual([
      "quotation",
    ]);
    expect(allowedActions({ ...active, status: "quotation" }, "admin")).toEqual(
      ["confirm"],
    );
    expect(allowedActions({ ...active, status: "confirmed" }, "admin")).toEqual(
      ["activate"],
    );
    expect(allowedActions({ ...active, status: "closed" }, "admin")).toEqual(
      [],
    );
  });
  it("does not infer permission from missing flags", () => {
    expect(
      allowedActions({ ...active, commercial_snapshot: null }, "admin"),
    ).toEqual([]);
  });
});
