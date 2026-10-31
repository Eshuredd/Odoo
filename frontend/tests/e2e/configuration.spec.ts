import { test, expect, type Page } from "@playwright/test";
const password = process.env.SUBCADENCE_TEST_PASSWORD!;
const api = "http://127.0.0.1:8766/api/v1";
const today = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());
const future = () => {
  const d = new Date(today + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + 60);
  return d.toISOString().slice(0, 10);
};
async function login(
  page: Page,
  email = "admin@example.com",
  credential = password,
) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(credential);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
}
test("configuration create/edit, variants, staff customer creation and template quotation", async ({
  page,
}) => {
  await login(page);
  const response = await page.request.post(api + "/auth/login", {
    data: { email: "admin@example.com", password },
  });
  const headers = {
    Authorization: `Bearer ${(await response.json()).access_token}`,
  };
  async function create(
    resource: string,
    title: string,
    fields: Record<string, string>,
  ) {
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", {
        name: (
          {
            customers: "Customers",
            products: "Products",
            taxes: "Taxes",
            plans: "Plans",
            discounts: "Discounts",
          } as Record<string, string>
        )[resource],
        exact: true,
      })
      .click();
    await page
      .getByRole("button", { name: `Create ${title}`, exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    for (const [label, value] of Object.entries(fields)) {
      const input = dialog.getByLabel(label, { exact: true });
      if ((await input.evaluate((el) => el.tagName)) === "SELECT")
        await input.selectOption(value);
      else await input.fill(value);
    }
    await dialog
      .getByRole("button", { name: "Save record", exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    await expect(page.locator(".notice-success")).toContainText("saved");
    if (resource === "customers") return { id: 0 };
    return (
      await (
        await page.request.get(
          api +
            `/${resource}?search=${encodeURIComponent(fields.Name || fields["Company name"] || "")}`,
          { headers },
        )
      ).json()
    ).items[0];
  }
  const tax = await create("taxes", "Taxes", {
    Name: "UI Synthetic GST",
    "Tax rate (%)": "18",
  });
  await page.getByLabel("Rows per page", { exact: true }).selectOption("10");
  await expect(page.getByLabel("Rows per page", { exact: true })).toHaveValue(
    "10",
  );
  await page
    .getByRole("button", { name: `Edit #${tax.id}`, exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByLabel("Name", { exact: true })
    .fill("UI Synthetic GST Updated");
  await page.getByRole("button", { name: "Save record", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const product = await create("products", "Products", {
    Name: "UI Synthetic Product",
    "Sales price (INR)": "120.00",
    "Tax ID (from Taxes)": String(tax.id),
  });
  await page
    .getByRole("link", { name: `Variants #${product.id}`, exact: true })
    .click();
  await page
    .getByRole("button", {
      name: `Create Product #${product.id} Variants`,
      exact: true,
    })
    .click();
  await page.getByLabel("Attribute", { exact: true }).fill("Tier");
  await page.getByLabel("Value", { exact: true }).fill("Basic");
  await page.getByLabel("Extra price (INR)").fill("10.00");
  await page.getByRole("button", { name: "Save record", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const plan = await create("plans", "Subscription Plans", {
    Name: "UI Synthetic Plan",
    "Base price (INR)": "50.00",
    "Valid to": future(),
  });
  await create("discounts", "Discounts", {
    Name: "UI Synthetic Discount",
    "Percentage (%; percentage type only)": "5",
    "Valid to": future(),
  });
  await page
    .getByRole("link", { name: "Quotation Templates", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create Quotation Templates", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Name", { exact: true })
    .fill("UI Synthetic Template");
  await dialog.getByLabel("Plan ID (from Plans)").fill(String(plan.id));
  await dialog.getByRole("button", { name: "Add template line" }).click();
  await dialog
    .getByLabel("product id", { exact: true })
    .fill(String(product.id));
  await dialog
    .getByRole("button", { name: "Save record", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "staff@example.com");
  await create("customers", "Customers", {
    "Company name": "UI Synthetic Customer",
    "Contact name": "UI Buyer",
    Email: "ui-buyer@example.com",
    "Initial password": password,
  });
  await page.getByRole("link", { name: "Taxes", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Create Taxes", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("banner")
    .getByRole("link", { name: "New Subscription", exact: true })
    .click();
  await page.getByRole("link", { name: "Use quotation template" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Create from Quotation Template",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Customer", exact: true }).click();
  await page
    .getByRole("button", { name: "UI Synthetic Customer", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Customer", exact: true }),
  ).toContainText("UI Synthetic Customer");
  await page
    .getByRole("button", { name: "Quotation template", exact: true })
    .click();
  await page.getByRole("button", { name: /UI Synthetic Template/ }).click();
  await expect(
    page.getByRole("button", { name: "Customer", exact: true }),
  ).toContainText("UI Synthetic Customer");
  await page.getByLabel("Expiry date", { exact: true }).fill(future());
  await page
    .getByRole("button", {
      name: "Create quotation from template",
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(/\/subscriptions\/\d+$/);
  await expect(
    page.getByRole("button", { name: "Confirm subscription", exact: true }),
  ).toBeVisible();
});

test("public signup, offline password reset and customer profile", async ({
  page,
}) => {
  await page.goto("/signup");
  await page.getByLabel("Email address").fill("ui-signup@example.com");
  await page.getByLabel("Company name").fill("UI Signup Synthetic");
  await page.getByLabel("Contact name").fill("Signup Buyer");
  await page.getByLabel("New password").fill(password);
  await page
    .getByRole("button", { name: "Create customer account", exact: true })
    .click();
  await expect(page.locator(".notice-success")).toContainText("created");
  await page.goto("/forgot-password");
  await page.getByLabel("Email address").fill("ui-signup@example.com");
  await page
    .getByRole("button", { name: "Request password reset", exact: true })
    .click();
  await expect(page.locator(".notice-success")).toBeVisible();
  const response = await page.request.post(api + "/auth/login", {
    data: { email: "admin@example.com", password },
  });
  const headers = {
    Authorization: `Bearer ${(await response.json()).access_token}`,
  };
  const outbox = await (
    await page.request.get(api + "/dev/email-outbox?limit=100", { headers })
  ).json();
  const message = outbox.items.find(
    (row: { recipient_email: string }) =>
      row.recipient_email === "ui-signup@example.com",
  );
  const token = /[?&]token=([^\s]+)/.exec(message.body)![1];
  await page.goto("/reset-password?token=" + encodeURIComponent(token));
  await expect(page).toHaveURL(/\/reset-password$/);
  const updated = password + "A!";
  await page.getByLabel("New password").fill(updated);
  await page
    .getByRole("button", { name: "Reset password", exact: true })
    .click();
  await expect(page.locator(".notice-success")).toBeVisible();
  await login(page, "ui-signup@example.com", updated);
  await page.getByRole("link", { name: "My Profile", exact: true }).click();
  await page.getByLabel("Company name").fill("UI Updated Profile");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(page.locator(".notice-success")).toContainText("saved");
  await page.getByRole("link", { name: "Payments", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No payments recorded" }),
  ).toBeVisible();
});
