#!/usr/bin/env node

const DEFAULT_ENDPOINT = "http://127.0.0.1:9222";
const DEFAULT_TIMEOUT_MS = 15_000;

function fail(code, message, evidence = {}) {
  const error = new Error(message);
  error.code = code;
  error.evidence = evidence;
  throw error;
}

function parseArgs(argv) {
  const result = { command: argv[0] || "help", options: {} };
  for (let index = 1; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith("--")) {
      fail("ARGUMENT_INVALID", `unexpected positional argument: ${item}`);
    }
    const key = item.slice(2);
    if (key === "browser") {
      result.options.browser = true;
      continue;
    }
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) {
      fail("ARGUMENT_VALUE_MISSING", `missing value for --${key}`);
    }
    result.options[key] = value;
    index += 1;
  }
  return result;
}

function endpointUrl(raw) {
  let value;
  try {
    value = new URL(raw || DEFAULT_ENDPOINT);
  } catch {
    fail("ENDPOINT_INVALID", "CDP endpoint must be an absolute HTTP URL");
  }
  const host = value.hostname.toLowerCase();
  if (!new Set(["127.0.0.1", "localhost", "::1"]).has(host)) {
    fail("ENDPOINT_NOT_LOOPBACK", "CDP endpoint must stay on loopback", { host });
  }
  if (!new Set(["http:", "https:"]).has(value.protocol)) {
    fail("ENDPOINT_PROTOCOL_INVALID", "CDP endpoint must use HTTP or HTTPS");
  }
  value.pathname = value.pathname.replace(/\/$/, "");
  value.search = "";
  value.hash = "";
  return value;
}

function timeoutMs(raw) {
  const value = raw === undefined ? DEFAULT_TIMEOUT_MS : Number.parseInt(raw, 10);
  if (!Number.isInteger(value) || value < 100 || value > 300_000) {
    fail("TIMEOUT_INVALID", "--timeout-ms must be an integer from 100 through 300000");
  }
  return value;
}

async function fetchJson(endpoint, path, timeout) {
  const url = new URL(path, `${endpoint.toString().replace(/\/$/, "")}/`);
  const response = await fetch(url, { signal: AbortSignal.timeout(timeout) });
  if (!response.ok) {
    fail("CDP_HTTP_ERROR", `CDP endpoint returned HTTP ${response.status}`, { url: url.toString() });
  }
  return response.json();
}

async function targets(endpoint, timeout) {
  const value = await fetchJson(endpoint, "json/list", timeout);
  if (!Array.isArray(value)) {
    fail("CDP_TARGETS_INVALID", "CDP /json/list did not return an array");
  }
  return value;
}

function selectTarget(items, options) {
  const candidates = items.filter((item) => item && typeof item === "object");
  if (options["target-id"]) {
    const found = candidates.find((item) => item.id === options["target-id"]);
    if (!found) fail("TARGET_NOT_FOUND", "no CDP target matched --target-id");
    return found;
  }
  if (options["url-contains"]) {
    const found = candidates.find((item) => String(item.url || "").includes(options["url-contains"]));
    if (!found) fail("TARGET_NOT_FOUND", "no CDP target matched --url-contains");
    return found;
  }
  const pages = candidates.filter((item) => item.type === "page");
  if (pages.length !== 1) {
    fail("TARGET_SELECTION_REQUIRED", "use --target-id or --url-contains unless exactly one page target exists", {
      pageCount: pages.length,
    });
  }
  return pages[0];
}

async function readJsonFile(path) {
  const { readFile } = await import("node:fs/promises");
  return JSON.parse(await readFile(path, "utf8"));
}

async function params(options) {
  if (options.params && options["params-file"]) {
    fail("PARAMS_AMBIGUOUS", "use only one of --params or --params-file");
  }
  if (options["params-file"]) return readJsonFile(options["params-file"]);
  if (!options.params) return {};
  try {
    return JSON.parse(options.params);
  } catch {
    fail("PARAMS_JSON_INVALID", "--params must contain one JSON object");
  }
}

async function expression(options) {
  if (options.expression && options["expression-file"]) {
    fail("EXPRESSION_AMBIGUOUS", "use only one of --expression or --expression-file");
  }
  if (options["expression-file"]) {
    const { readFile } = await import("node:fs/promises");
    return readFile(options["expression-file"], "utf8");
  }
  if (options.expression === undefined) fail("EXPRESSION_REQUIRED", "eval requires --expression or --expression-file");
  return options.expression;
}

async function sendCdp(webSocketUrl, method, methodParams, timeout) {
  if (typeof WebSocket !== "function") {
    fail("WEBSOCKET_UNAVAILABLE", "this Node runtime does not expose the standard WebSocket client");
  }
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(webSocketUrl);
    const timer = setTimeout(() => {
      socket.close();
      const error = new Error(`CDP WebSocket response timed out after ${timeout}ms`);
      error.code = "CDP_WEBSOCKET_TIMEOUT";
      reject(error);
    }, timeout);
    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ id: 1, method, params: methodParams }));
    });
    socket.addEventListener("message", (event) => {
      let payload;
      try {
        payload = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (payload.id !== 1) return;
      clearTimeout(timer);
      socket.close();
      if (payload.error) {
        const error = new Error(payload.error.message || "CDP command failed");
        error.code = "CDP_COMMAND_FAILED";
        error.evidence = payload.error;
        reject(error);
      } else {
        resolve(payload.result ?? {});
      }
    });
    socket.addEventListener("error", () => {
      clearTimeout(timer);
      const error = new Error("CDP WebSocket connection failed");
      error.code = "CDP_WEBSOCKET_ERROR";
      reject(error);
    });
  });
}

function usage() {
  return `Usage:
  chatgpt_chrome_cdp.mjs version [--endpoint http://127.0.0.1:PORT]
  chatgpt_chrome_cdp.mjs list [--endpoint http://127.0.0.1:PORT]
  chatgpt_chrome_cdp.mjs eval [target selector] (--expression JS | --expression-file PATH)
  chatgpt_chrome_cdp.mjs call [target selector | --browser] --method CDP.METHOD [--params JSON | --params-file PATH]

Target selectors: --target-id ID | --url-contains TEXT
Common options: --endpoint URL --timeout-ms N
The endpoint is intentionally restricted to loopback Chrome DevTools Protocol instances.`;
}

async function main(argv) {
  const { command, options } = parseArgs(argv);
  if (command === "help" || command === "--help" || command === "-h") {
    process.stdout.write(`${usage()}\n`);
    return;
  }
  const endpoint = endpointUrl(options.endpoint);
  const timeout = timeoutMs(options["timeout-ms"]);
  if (command === "version") {
    process.stdout.write(`${JSON.stringify(await fetchJson(endpoint, "json/version", timeout), null, 2)}\n`);
    return;
  }
  if (command === "list") {
    process.stdout.write(`${JSON.stringify(await targets(endpoint, timeout), null, 2)}\n`);
    return;
  }
  let webSocketUrl;
  if (options.browser) {
    const version = await fetchJson(endpoint, "json/version", timeout);
    webSocketUrl = version.webSocketDebuggerUrl;
  } else {
    webSocketUrl = selectTarget(await targets(endpoint, timeout), options).webSocketDebuggerUrl;
  }
  if (!webSocketUrl) fail("WEBSOCKET_URL_MISSING", "selected CDP endpoint or target has no WebSocket URL");
  if (command === "eval") {
    const result = await sendCdp(webSocketUrl, "Runtime.evaluate", {
      expression: await expression(options),
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    }, timeout);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }
  if (command === "call") {
    if (!options.method) fail("METHOD_REQUIRED", "call requires --method");
    const result = await sendCdp(webSocketUrl, options.method, await params(options), timeout);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }
  fail("COMMAND_UNSUPPORTED", `unsupported command: ${command}`);
}

main(process.argv.slice(2)).catch((error) => {
  process.stderr.write(`${JSON.stringify({
    ok: false,
    error: {
      code: error.code || "CDP_CLI_FAILED",
      message: error.message || String(error),
      evidence: error.evidence || {},
    },
  })}\n`);
  process.exitCode = 1;
});
