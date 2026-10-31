import { test, expect, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const password = process.env.SUBCADENCE_TEST_PASSWORD!;
const api = "http://127.0.0.1:8766/api/v1";
const today = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());
const future = (days: number) => {
  const date = new Date(`${today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
};
async function signIn(page: Page, email = "admin@example.com") {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", {
      name: "Executive Revenue & Billing Dashboard",
    }),
  ).toBeVisible();
}
async function screenshot(page: Page, name: string) {
  await page.waitForFunction(() => document.body.dataset.appReady === "true");
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    (document.activeElement as HTMLElement | null)?.blur();
    window.scrollTo(0, 0);
  });
  await mkdir("test-results/screenshots", { recursive: true });
  await page.screenshot({
    path: `test-results/screenshots/${name}.png`,
    fullPage: true,
  });
}

test("login, real dashboard data, search, pagination and subscription navigation", async ({
  page,
}) => {
  await page.goto("/login");
  await screenshot(page, "login-desktop");
  await page.getByLabel("Email address").fill("admin@example.com");
  await page.getByLabel("Password", { exact: true }).fill("Incorrect!password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator('.notice[role="alert"]')).toContainText(
    "Invalid email or password",
  );
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(
    page.getByRole("link", { name: "View SUB-000001" }),
  ).toBeVisible();
  await screenshot(page, "dashboard-desktop");
  await page.getByRole("link", { name: "Subscriptions", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Subscriptions", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "SUB-000001", exact: true }),
  ).toBeVisible();
  await screenshot(page, "subscriptions-desktop");
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "SUB-000021", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Search subscription list").fill("SUB-000001");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "SUB-000001", exact: true }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("link", { name: "SUB-000001", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Subscription SUB-000001", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("₹1,820.00", { exact: true }).first(),
  ).toBeVisible();
  await screenshot(page, "subscription-detail-desktop");
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 });
});

test("create and operate a real subscription through every supported lifecycle action", async ({
  page,
}) => {
  await signIn(page);
  await page
    .getByRole("banner")
    .getByRole("link", { name: "New Subscription", exact: true })
    .click();
  await page.getByRole("button", { name: "Customer", exact: true }).click();
  await page
    .getByRole("button", { name: "Alpha Industries", exact: true })
    .click();
  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await page.getByRole("button", { name: /Monthly Business ·/ }).click();
  await page
    .getByRole("button", { name: "Product for line 1", exact: true })
    .click();
  await page.getByRole("button", { name: /Business Software ·/ }).click();
  await page
    .getByRole("button", { name: "Variant for line 1", exact: true })
    .click();
  await page.getByRole("button", { name: /Brand: Odoo ·/ }).click();
  await page.getByLabel("Quantity for line 1").fill("2");
  await page.getByLabel("Expiry date", { exact: true }).fill(future(90));
  await screenshot(page, "create-subscription-desktop");
  await page.getByRole("button", { name: "Create draft subscription" }).click();
  await expect(page).toHaveURL(/\/subscriptions\/\d+$/);
  await expect(
    page.getByRole("button", { name: "Create quotation", exact: true }),
  ).toBeVisible();
  const id = Number(page.url().split("/").pop());
  for (const action of [
    "Create quotation",
    "Confirm subscription",
    "Activate subscription",
    "Pause subscription",
    "Resume subscription",
    "Renew subscription",
    "Close subscription",
  ]) {
    await page.getByRole("button", { name: action, exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByLabel("Business date (as of)")).toHaveValue(today);
    if (action === "Renew subscription")
      await dialog.getByLabel("New expiry date").fill(future(180));
    await dialog.getByRole("button", { name: action, exact: true }).click();
    await expect(dialog).not.toBeVisible();
    await expect(page.getByRole("status")).toContainText(
      `${action} completed successfully.`,
    );
  }
  await expect(page.locator(".status-closed")).toBeVisible();
  const login = await page.request.post(api + "/auth/login", {
    data: { email: "admin@example.com", password },
  });
  const token = (await login.json()).access_token;
  const record = await page.request.get(`${api}/subscriptions/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const row = await record.json();
  expect(row.status).toBe("closed");
  expect(row.next_invoice_date).toBeNull();
  expect(row.lines[0].unit_price_paise).toBe(66000);
  expect(row.expiry_date).toBe(future(180));
});

test("customer navigation, ownership isolation, and backend-enforced role restrictions", async ({
  page,
}) => {
  await signIn(page, "buyer@example.com");
  await expect(page.getByRole("link", { name: "Billing Center" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("link", { name: "New Subscription", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Subscriptions", exact: true }).click();
  await page.getByLabel("Search subscription list").fill("SUB-000024");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No matching subscriptions" }),
  ).toBeVisible();
  const login = await page.request.post(api + "/auth/login", {
    data: { email: "buyer@example.com", password },
  });
  const token = (await login.json()).access_token;
  const headers = { Authorization: `Bearer ${token}` };
  expect(
    (await page.request.get(api + "/subscriptions/24", { headers })).status(),
  ).toBe(404);
  expect(
    (
      await page.request.post(api + "/subscriptions/1/pause", {
        headers,
        data: { as_of: today },
      })
    ).status(),
  ).toBe(403);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/login/);
  expect((await page.request.get(api + "/auth/me", { headers })).status()).toBe(
    401,
  );
});

test("staff previews and executes real billing, views invoices, confirms and cancels without duplicate periods", async ({
  page,
}) => {
  const paymentRequests: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/v1\/payments/.test(request.url()))
      paymentRequests.push(request.url());
  });
  await signIn(page, "staff@example.com");
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Billing Center", exact: false })
    .click();
  await expect(
    page.getByRole("button", { name: "Execute billing", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Run billing as of date").fill(today);
  await page.getByRole("button", { name: "Preview dry run" }).click();
  await expect(page.getByText("Not persisted", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Synthetic launch discount", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Execute billing", exact: true }),
  ).toBeEnabled();
  await screenshot(page, "billing-center-desktop");
  await page
    .getByRole("button", { name: "Execute billing", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm execution", exact: true })
    .click();
  await expect(page.locator(".notice-success")).toContainText(
    "1 invoices generated; 0 subscriptions failed",
  );
  await expect(
    page.getByRole("link", { name: "INV-000001", exact: true }),
  ).toBeVisible();
  await screenshot(page, "billing-executed-desktop");
  await page.getByRole("link", { name: "Invoices", exact: false }).click();
  await expect(
    page.getByRole("link", { name: "INV-000001", exact: true }),
  ).toBeVisible();
  await screenshot(page, "invoice-list-desktop");
  await page.getByRole("link", { name: "INV-000001", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "INV-000001", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Record Payment", exact: true }).first(),
  ).toBeDisabled();
  await screenshot(page, "invoice-detail-desktop");
  await expect(
    page.getByRole("cell", { name: /Business Software · Brand: Odoo/ }),
  ).toBeVisible();
  await expect(
    page.getByText("₹1,851.84", { exact: true }).last(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm invoice", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm now", exact: true }).click();
  await expect(page.locator(".notice-success")).toContainText("confirmed");
  await page
    .getByRole("button", { name: "Cancel invoice", exact: true })
    .click();
  await page.getByRole("button", { name: "Cancel now", exact: true }).click();
  await expect(page.locator(".notice-success")).toContainText("cancelled");
  expect(paymentRequests).toEqual([]);
  const login = await page.request.post(api + "/auth/login", {
    data: { email: "staff@example.com", password },
  });
  const headers = {
    Authorization: `Bearer ${(await login.json()).access_token}`,
  };
  const repeated = await page.request.post(api + "/billing/run", {
    headers,
    data: { as_of: today },
  });
  expect(repeated.status()).toBe(200);
  expect((await repeated.json()).generated_or_proposed_invoice_count).toBe(0);
  expect(
    (await (await page.request.get(api + "/discounts/1", { headers })).json())
      .times_used,
  ).toBe(1);
  await page
    .getByRole("banner")
    .getByRole("link", { name: "Run Billing", exact: true })
    .click();
  await page.getByRole("button", { name: "Preview dry run" }).click();
  await expect(
    page.getByRole("heading", { name: "No new invoice periods" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Execute billing", exact: true }),
  ).toBeDisabled();
  expect(
    (
      await page.request.post(api + "/users/staff", {
        headers: {
          ...headers,
        },
        data: { email: "denied@example.com", password },
      })
    ).status(),
  ).toBe(403);
});

test("network/server errors, empty state, and revoked sessions are handled", async ({
  page,
}) => {
  await signIn(page);
  await page.route("**/api/v1/subscriptions?**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Database unavailable"}',
    }),
  );
  await page.getByRole("link", { name: "Subscriptions", exact: true }).click();
  await expect(page.getByRole("alert").first()).toContainText(
    "Database unavailable",
  );
  await page.unroute("**/api/v1/subscriptions?**");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "SUB-000001", exact: true }),
  ).toBeVisible();
  const login = await page.request.post(api + "/auth/login", {
    data: { email: "admin@example.com", password },
  });
  await page.request.post(api + "/auth/logout", {
    headers: { Authorization: `Bearer ${(await login.json()).access_token}` },
  });
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await expect(page).toHaveURL(/login/);
  await expect(page.getByRole("status")).toContainText(
    "expired or been revoked",
  );
});

test("customers see only owned invoices and cannot run billing or confirm invoices", async ({
  page,
}) => {
  await signIn(page, "buyer@example.com");
  await page.getByRole("link", { name: "Invoices", exact: true }).click();
  await page.getByRole("link", { name: "INV-000001", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "INV-000001", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Confirm invoice", exact: true }),
  ).toHaveCount(0);
  const login = await page.request.post(api + "/auth/login", {
    data: { email: "buyer@example.com", password },
  });
  const headers = {
    Authorization: `Bearer ${(await login.json()).access_token}`,
  };
  expect(
    (
      await page.request.post(api + "/billing/run", {
        headers,
        data: { as_of: today },
      })
    ).status(),
  ).toBe(403);
  expect(
    (
      await page.request.post(api + "/invoices/1/confirm", { headers })
    ).status(),
  ).toBe(403);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, "other@example.com");
  await page.getByRole("link", { name: "Invoices", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No invoices found" }),
  ).toBeVisible();
  const other = await page.request.post(api + "/auth/login", {
    data: { email: "other@example.com", password },
  });
  expect(
    (
      await page.request.get(api + "/invoices/1", {
        headers: {
          Authorization: `Bearer ${(await other.json()).access_token}`,
        },
      })
    ).status(),
  ).toBe(404);
});

test("billing failures never show fictional success and a changed date requires a fresh preview", async ({
  page,
}) => {
  await signIn(page);
  await page
    .getByRole("banner")
    .getByRole("link", { name: "Run Billing", exact: true })
    .click();
  await page.route("**/api/v1/billing/preview", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Synthetic billing outage"}',
    }),
  );
  await page.getByRole("button", { name: "Preview dry run" }).click();
  await expect(page.locator(".notice-error")).toContainText(
    "Synthetic billing outage",
  );
  await expect(page.locator(".notice-success")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Execute billing", exact: true }),
  ).toBeDisabled();
  await page.unroute("**/api/v1/billing/preview");
  await page.getByLabel("Run billing as of date").fill(future(32));
  await page.getByRole("button", { name: "Preview dry run" }).click();
  await expect(
    page.getByRole("button", { name: "Execute billing", exact: true }),
  ).toBeEnabled();
  await page.route("**/api/v1/billing/run", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Synthetic execution outage"}',
    }),
  );
  await page
    .getByRole("button", { name: "Execute billing", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm execution", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "Synthetic execution outage",
  );
  await expect(page.locator(".notice-success")).toHaveCount(0);
  await page.getByRole("button", { name: "Go back", exact: true }).click();
  await page.getByLabel("Run billing as of date").fill(future(33));
  await expect(
    page.getByRole("button", { name: "Execute billing", exact: true }),
  ).toBeDisabled();
});

test("mobile navigation, horizontal table containment, and keyboard dialog cancellation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeVisible();
  await screenshot(page, "dashboard-mobile");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Subscriptions", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "SUB-000001", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await screenshot(page, "subscriptions-mobile");
  await page.getByRole("link", { name: "SUB-000001", exact: true }).click();
  await page
    .getByRole("button", { name: "Pause subscription", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  for (let index = 0; index < 8; index++) {
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate(() =>
        document.querySelector("dialog")?.contains(document.activeElement),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Pause subscription", exact: true }),
  ).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await screenshot(page, "subscription-detail-mobile");
  await page
    .getByRole("banner")
    .getByRole("link", { name: "New Subscription", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Create Subscription", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await screenshot(page, "create-subscription-mobile");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Billing Center", exact: false })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Automated Billing Center",
      exact: true,
    }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await screenshot(page, "billing-center-mobile");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Invoices", exact: false })
    .click();
  await page.getByRole("link", { name: "INV-000001", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "INV-000001", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await screenshot(page, "invoice-detail-mobile");
  await page.reload();
  await expect(page).toHaveURL(/login/);
});
