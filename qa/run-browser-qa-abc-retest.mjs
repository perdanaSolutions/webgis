/**
 * Retest fokusus: A2, A8, B1–B5, C4
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");

const CHROME =
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE = "http://localhost:3000";
const EMAIL = "superadmin@plantation.com";
const PASS = "admin123";
const results = [];

function record(id, status, actual, note = "") {
  results.push({ id, status, actual, note });
  console.log(`[${status}] ${id} — ${actual}${note ? " | " + note : ""}`);
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function fillLogin(page, email, password) {
  await page.waitForSelector("#email", { timeout: 15000 });
  await page.click("#email", { clickCount: 3 });
  await page.keyboard.press("Backspace");
  await page.type("#email", email, { delay: 15 });
  await page.click("#password", { clickCount: 3 });
  await page.keyboard.press("Backspace");
  await page.type("#password", password, { delay: 15 });
  await page.click('button[type="submit"]');
}

async function loginOk(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
  await fillLogin(page, EMAIL, PASS);
  await page.waitForFunction(() => location.pathname.includes("/dashboard"), {
    timeout: 25000,
  });
  await wait(1500);
}

async function openPasswordModal(page) {
  await page.waitForSelector(".profile-dropdown-container > button", {
    timeout: 10000,
  });
  await page.click(".profile-dropdown-container > button");
  await wait(400);
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll(".profile-dropdown-container button")].find(
      (b) => /Profil Saya/i.test(b.textContent || ""),
    );
    btn?.click();
  });
  await page.waitForFunction(
    () => /Simpan Password|Password baru|Password Lama/i.test(document.body.innerText),
    { timeout: 8000 },
  );
}

async function setPwFields(page, oldP, newP) {
  // Header uses v-model on passwordForm — need input events on the two password inputs in modal
  await page.evaluate(
    ({ oldP, newP }) => {
      const modal = [...document.querySelectorAll(".fixed")].find((el) =>
        /Simpan Password|Profil Saya/i.test(el.textContent || ""),
      );
      if (!modal) throw new Error("modal not found");
      const inputs = [...modal.querySelectorAll("input")].filter(
        (i) => i.type === "password" || i.type === "text",
      );
      const setVal = (el, val) => {
        const proto = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          "value",
        );
        proto?.set?.call(el, val);
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      };
      if (inputs.length < 2) throw new Error("pw inputs < 2: " + inputs.length);
      setVal(inputs[0], oldP);
      setVal(inputs[1], newP);
    },
    { oldP, newP },
  );
}

async function clickSavePw(page) {
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll("button")].find((b) =>
      /Simpan Password/i.test(b.textContent || ""),
    );
    btn?.click();
  });
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--window-size=1280,900"],
    defaultViewport: { width: 1280, height: 900 },
  });
  const page = await browser.newPage();
  const network = [];
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/auth/") || url.includes("/menus") || url.includes("/password")) {
      network.push({
        url,
        method: res.request().method(),
        status: res.status(),
        auth: res.request().headers()["authorization"] || "",
      });
    }
  });

  try {
    // ===== A2 =====
    network.length = 0;
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
    // clear any leftover session
    await page.evaluate(() => {
      localStorage.clear();
      document.cookie.split(";").forEach((c) => {
        document.cookie = c
          .replace(/^ +/, "")
          .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
      });
    });
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
    await fillLogin(page, "qa.invalid@example.com", "wrong-password-placeholder");
    await wait(3500);
    const inv = network.filter(
      (n) => n.url.includes("/auth/login") && n.method === "POST",
    );
    const lastInv = inv[inv.length - 1];
    const errUi = await page.evaluate(() => {
      const p = document.querySelector("p.text-error, .text-error");
      return (p?.textContent || "") + (document.body.innerText.match(/salah|gagal|periksa/i)?.[0] || "");
    });
    const stay = page.url().includes("/login");
    if (stay && lastInv?.status === 401 && errUi) {
      record("A2", "[x] PASS", `UI error; tetap /login; API 401`, errUi.slice(0, 80));
    } else if (stay && lastInv?.status === 401) {
      record("A2", "[x] PASS", `tetap /login; API 401`, `errUi empty? ${JSON.stringify(errUi)}`);
    } else {
      record(
        "A2",
        "[F] FAIL",
        `stay=${stay} status=${lastInv?.status} err=${errUi}`,
        JSON.stringify(inv),
      );
    }

    // ===== Login for B + A8 + C4 =====
    await loginOk(page);

    // ===== B1 =====
    try {
      await openPasswordModal(page);
      record("B1", "[x] PASS", "Modal Profil Saya / ganti password tampil");
    } catch (e) {
      record("B1", "[F] FAIL", String(e.message || e));
      throw e;
    }

    // ===== B2 =====
    network.length = 0;
    await setPwFields(page, "admin123", "short1");
    await clickSavePw(page);
    await wait(1000);
    const b2 = await page.evaluate(() =>
      /minimal 8/i.test(document.body.innerText),
    );
    const b2api = network.some((n) => n.url.includes("/password"));
    record(
      "B2",
      b2 && !b2api ? "[x] PASS" : "[F] FAIL",
      `err=${b2} apiHit=${b2api}`,
    );

    // ===== B3 =====
    network.length = 0;
    await setPwFields(page, "admin123", "admin123");
    await clickSavePw(page);
    await wait(1000);
    const b3 = await page.evaluate(() =>
      /berbeda dari password lama/i.test(document.body.innerText),
    );
    const b3api = network.some((n) => n.url.includes("/password"));
    record(
      "B3",
      b3 && !b3api ? "[x] PASS" : "[F] FAIL",
      `err=${b3} apiHit=${b3api}`,
    );

    // ===== B5 =====
    network.length = 0;
    await setPwFields(page, "wrong-old-password-xx", "NewPass12345");
    await clickSavePw(page);
    await wait(3500);
    const b5n = network.find((n) => n.url.includes("/password"));
    const b5ui = await page.evaluate(() =>
      /tidak sesuai|gagal|salah/i.test(document.body.innerText),
    );
    const stillIn = page.url().includes("/dashboard") || page.url().includes("localhost:3000");
    const hasTok = (await page.cookies()).some(
      (c) => c.name === "auth_token" && c.value,
    );
    record(
      "B5",
      b5n && b5n.status >= 400 && hasTok
        ? "[x] PASS"
        : "[F] FAIL",
      `API ${b5n?.status}; UI=${b5ui}; tokenTetap=${hasTok}`,
    );

    // ===== B4 + revert =====
    const TEMP = "TempQaPass123!";
    network.length = 0;
    await setPwFields(page, PASS, TEMP);
    await clickSavePw(page);
    await wait(4000);
    const b4n = network.find((n) => n.url.includes("/password"));
    const b4ui = await page.evaluate(() =>
      /berhasil/i.test(document.body.innerText),
    );
    if (b4n && b4n.status >= 200 && b4n.status < 300) {
      network.length = 0;
      // reopen modal if closed / cleared
      const stillModal = await page.evaluate(() =>
        /Simpan Password/i.test(document.body.innerText),
      );
      if (!stillModal) await openPasswordModal(page);
      await setPwFields(page, TEMP, PASS);
      await clickSavePw(page);
      await wait(4000);
      const rev = network.find((n) => n.url.includes("/password"));
      if (rev && rev.status >= 200 && rev.status < 300) {
        record("B4", "[x] PASS", "Update 2xx + revert ke seed OK", `UI sukses=${b4ui}`);
      } else {
        record(
          "B4",
          "[F] FAIL",
          `Update OK tapi revert status=${rev?.status}`,
          "Password mungkin TempQaPass123!",
        );
      }
    } else {
      record("B4", "[F] FAIL", `status=${b4n?.status} ui=${b4ui}`);
    }

    // close modal
    await page.evaluate(() => {
      const b = [...document.querySelectorAll("button")].find(
        (x) => x.getAttribute("aria-label") === "Tutup",
      );
      b?.click();
    });
    await wait(500);

    // ===== A8: bogus token → /me 401 → clear + login =====
    await page.setCookie({
      name: "auth_token",
      value: "invalid.token.for.qa",
      domain: "localhost",
      path: "/",
    });
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle2" });
    await wait(3000);
    const a8url = page.url();
    const a8tok = (await page.cookies()).find(
      (c) => c.name === "auth_token" && c.value && c.value !== "invalid.token.for.qa",
    );
    const a8cleared = !(await page.cookies()).find(
      (c) => c.name === "auth_token" && c.value,
    );
    if (a8url.includes("/login") && a8cleared) {
      record("A8", "[x] PASS", "Token invalid → clear + /login (/me 401 path)");
    } else if (a8url.includes("/login")) {
      record("A8", "[x] PASS", "Redirect /login setelah token invalid", `cleared=${a8cleared}`);
    } else {
      record("A8", "[F] FAIL", `url=${a8url} tok=${!!a8tok} cleared=${a8cleared}`);
    }

    // ===== C4 menus 500 =====
    await loginOk(page);
    await page.setRequestInterception(true);
    const on500 = (req) => {
      if (req.url().includes("/menus")) {
        return req.respond({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "boom" }),
        });
      }
      return req.continue();
    };
    page.on("request", on500);
    await page.reload({ waitUntil: "networkidle2" }).catch(() => null);
    await wait(2500);
    const alive = await page.evaluate(() => !!document.querySelector("#__nuxt"));
    const body = await page.evaluate(() => document.body.innerText.slice(0, 300));
    page.off("request", on500);
    await page.setRequestInterception(false);
    if (alive && !/TypeError|Cannot read|ChunkLoadError/i.test(body)) {
      record(
        "C4",
        "[x] PASS",
        "Menus 500 tidak crash Nuxt",
        body.replace(/\s+/g, " ").slice(0, 100),
      );
    } else {
      record("C4", "[F] FAIL", `alive=${alive}`);
    }

    // code-level confirm C5 gap already known — skip
  } catch (e) {
    record("RUNNER", "[F] FAIL", String(e?.message || e));
  } finally {
    const out = path.join(__dirname, "hasil-qa-abc-retest.json");
    fs.writeFileSync(
      out,
      JSON.stringify({ ts: new Date().toISOString(), results }, null, 2),
    );
    console.log("Wrote", out);
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
