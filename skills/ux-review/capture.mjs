#!/usr/bin/env node
// The "eyes" for ux-review: screenshot a running front-end across viewport x theme
// using the system Chrome, driven by puppeteer-core bootstrapped into a stable cache
// dir. Never added to the target repo.
//
// Usage:
//   node capture.mjs <baseUrl> <route...> [--out DIR] [--viewports mobile,desktop,ultrawide]
//                    [--themes light,dark] [--theme-key theme] [--fold]
// Example:
//   node capture.mjs http://localhost:3000 /today /programmes --out /tmp/ux
//
// --fold shoots only the viewport (no fullPage scroll) — use it for a tall page where
// fullPage downscales past the point of judging craft (focus rings, alignment, seams).
//
// Prints one absolute PNG path per line for the caller to Read.

import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import { mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const CACHE = join(process.env.HOME, '.cache', 'ux-review');

const argv = process.argv.slice(2);
const opts = {
  viewports: 'mobile,desktop',
  themes: 'light,dark',
  out: join(CACHE, 'shots'),
  themeKey: 'theme',
};
const positional = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--out') opts.out = argv[++i];
  else if (a === '--viewports') opts.viewports = argv[++i];
  else if (a === '--themes') opts.themes = argv[++i];
  else if (a === '--theme-key') opts.themeKey = argv[++i];
  else if (a === '--fold') opts.fold = true;
  else positional.push(a);
}
const [baseUrl, ...routes] = positional;
if (!baseUrl || routes.length === 0) {
  console.error('usage: node capture.mjs <baseUrl> <route...> [--out DIR] [--viewports m,d] [--themes l,d]');
  process.exit(2);
}

const VIEWPORTS = {
  mobile: { width: 390, height: 844, deviceScaleFactor: 2 },
  desktop: { width: 1440, height: 900, deviceScaleFactor: 2 },
  // 21:9 monitor. DPR 1 keeps the PNG readable when it is downscaled for review.
  ultrawide: { width: 3440, height: 1440, deviceScaleFactor: 1 },
};

function findChrome() {
  for (const bin of ['google-chrome-stable', 'google-chrome', 'chromium', 'chromium-browser']) {
    try {
      const p = execSync(`command -v ${bin}`, { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
      if (p) return p;
    } catch {}
  }
  throw new Error('no system Chrome/Chromium found');
}

function ensurePuppeteer() {
  const require = createRequire(join(CACHE, 'anchor.cjs'));
  try {
    return require('puppeteer-core');
  } catch {
    mkdirSync(CACHE, { recursive: true });
    console.error('bootstrapping puppeteer-core into', CACHE, '(one-time)…');
    execSync(`npm install puppeteer-core --prefix ${CACHE} --no-audit --no-fund --loglevel=error`, {
      stdio: 'inherit',
    });
    return require('puppeteer-core');
  }
}

const safe = (s) => s.replace(/^https?:\/\//, '').replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'root';

// Seeded BEFORE any page script: the stored preference only. A theme provider
// (next-themes et al) reads this in its own blocking inline script and sets the class
// itself, so the first paint is already right. Deliberately touches no DOM -- writing
// attributes on <html> pre-hydration is itself a server/client mismatch, which trips
// React's hydration warning and puts a dev-overlay "1 Issue" badge in the screenshot.
function themeSeed(theme, storageKey) {
  return `try { localStorage.setItem(${JSON.stringify(storageKey)}, ${JSON.stringify(theme)}); } catch {}`;
}

// Applied AFTER load, for apps with no theme provider that read an attribute or class
// directly. By this point hydration is done, so setting them is safe.
function themeApply(theme) {
  return `(() => {
    const el = document.documentElement;
    if (!el) return;
    try {
      el.setAttribute('data-theme', ${JSON.stringify(theme)});
      if (!el.classList.contains(${JSON.stringify(theme)})) {
        el.classList.remove('light', 'dark');
        el.classList.add(${JSON.stringify(theme)});
      }
    } catch {}
  })()`;
}

const puppeteer = ensurePuppeteer();
mkdirSync(opts.out, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: findChrome(),
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-color-profile=srgb', '--hide-scrollbars'],
});

const written = [];
try {
  for (const route of routes) {
    const url = new URL(route, baseUrl).href;
    for (const vp of opts.viewports.split(',').map((s) => s.trim()).filter(Boolean)) {
      for (const theme of opts.themes.split(',').map((s) => s.trim()).filter(Boolean)) {
        const page = await browser.newPage();
        await page.setViewport(VIEWPORTS[vp] ?? VIEWPORTS.desktop);
        await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: theme }]);
        await page.evaluateOnNewDocument(themeSeed(theme, opts.themeKey));
        try {
          await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
        } catch {
          await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
        }
        await page.evaluate(themeApply(theme)).catch(() => {});
        // Next's dev overlay ("N" badge, "1 Issue", a build-error modal for ANY route in the app) is not the design under review.
        await page.addStyleTag({ content: 'nextjs-portal{display:none!important}' }).catch(() => {});
        await new Promise((r) => setTimeout(r, 400)); // let fonts/transitions settle
        const suffix = opts.fold ? '__fold' : '';
        const file = join(opts.out, `${safe(route)}__${vp}__${theme}${suffix}.png`);
        await page.screenshot({ path: file, fullPage: !opts.fold });
        written.push(file);
        await page.close();
      }
    }
  }
} finally {
  await browser.close();
}

for (const f of written) console.log(f);
