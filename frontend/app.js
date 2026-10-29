const $ = (id) => document.getElementById(id);
const button = $("buy");
const message = $("message");

const userId = (() => {
  try {
    let id = localStorage.getItem("flash-user");
    if (!id) localStorage.setItem("flash-user", (id = crypto.randomUUID()));
    return id;
  } catch {
    return crypto.randomUUID();
  }
})();

let startsAt = 0;
let clockOffset = 0;
let busy = false;
let finished = false;
let soldOut = false;

const now = () => Date.now() + clockOffset;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function say(text, kind = "") {
  message.textContent = text;
  message.className = "message " + kind;
}

function setButton(text, enabled, done = false) {
  button.textContent = text;
  button.disabled = !enabled;
  button.classList.toggle("done", done);
}

async function api(path, options) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  return { code: res.status, status: body.status };
}

async function loadSale() {
  const res = await fetch("/api/sale");
  const sale = await res.json();
  clockOffset = Date.parse(sale.server_time) - Date.now();
  startsAt = Date.parse(sale.starts_at);
  showStock(sale.stock_left);
}

function showStock(left) {
  const el = $("stock");
  el.hidden = now() < startsAt;
  el.textContent = left > 0 ? `Only ${left} left!` : "All units sold";
  if (left === 0 && !finished && !busy) {
    soldOut = true;
    setButton("Sold out", false);
  }
}

function tick() {
  const ms = startsAt - now();
  if (ms <= 0) {
    $("countdown").hidden = true;
    if (!busy && !finished && !soldOut && button.disabled) {
      setButton("Buy now", true);
    }
    return;
  }
  const s = Math.ceil(ms / 1000);
  const pad = (n) => String(n).padStart(2, "0");
  $("timer").textContent = `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
  setButton("Starts soon", false);
}

function finish(status) {
  finished = true;
  if (status === "CONFIRMED") {
    setButton("Order confirmed", false, true);
    say("It's yours! We'll email you the delivery details.", "ok");
  } else if (status === "SOLD_OUT") {
    setButton("Sold out", false);
    say("Sorry, every unit has been claimed.", "bad");
  } else {
    setButton("Couldn't complete", false);
    say("Something went wrong with your order. You haven't been charged.", "bad");
  }
}

async function waitForOrder() {
  setButton("Confirming…", false);
  say("You got one! Confirming your order…", "ok");
  let delay = 1000;
  for (;;) {
    await sleep(delay);
    try {
      const { status } = await api("/checkout/" + userId);
      if (status && status !== "PENDING") return finish(status);
    } catch {
    }
    delay = Math.min(delay * 1.5, 5000);
  }
}

async function buy() {
  if (busy || finished) return;
  busy = true;
  setButton("Placing order…", false);
  say("");

  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const { code, status } = await api("/checkout", {
        method: "POST",
        body: JSON.stringify({ user_id: userId }),
      });
      if (status === "PENDING") return waitForOrder();
      if (status === "NOT_STARTED") {
        await loadSale();
        break;
      }
      if (status && code < 500 && code !== 429) return finish(status);
    } catch {
    }
    say("Lots of people are buying right now, retrying…");
    await sleep(500 * 2 ** attempt + Math.random() * 500);
  }

  busy = false;
  setButton("Buy now", now() >= startsAt);
  say("We couldn't reach the store. Please tap Buy now again.", "bad");
}

button.addEventListener("click", buy);

async function init() {
  try {
    await loadSale();
  } catch {
    say("Can't reach the store right now. Refresh in a moment.", "bad");
    return;
  }
  tick();
  setInterval(tick, 1000);

  const { status } = await api("/checkout/" + userId).catch(() => ({}));
  if (status === "PENDING") {
    busy = true;
    waitForOrder();
  } else if (status === "CONFIRMED" || status === "FAILED") {
    finish(status);
  }

  setInterval(async () => {
    if (now() < startsAt || finished) return;
    try {
      const res = await fetch("/api/sale");
      showStock((await res.json()).stock_left);
    } catch {}
  }, 4000);
}

init();
