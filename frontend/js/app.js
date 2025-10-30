const gameListEl = document.getElementById("game-items");
const summaryEl = document.getElementById("insight-summary");
const subtextEl = document.getElementById("insight-subtext");
const badgesEl = document.getElementById("micro-badges");
const metricsEl = document.getElementById("insight-metrics");

let selectedGameId = null;
let refreshTimer = null;

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function formatSubtext(insight) {
  const pace = (insight.paceDeltaPct * 100).toFixed(1);
  const alignment = insight.alignment;
  const combinedPace = insight.supporting.expectedTotalNow.toFixed(1);
  return `Baseline ${combinedPace}. Pace ${pace > 0 ? "+" : ""}${pace}%. Market ${alignment}.`;
}

function renderBadges(insight) {
  badgesEl.innerHTML = "";
  const badges = [];
  if (insight.defenseContext.tempoClampRate >= 0.6 && insight.defenseContext.psi <= -5) {
    badges.push({ label: "Clamp Defense", cls: "clamp" });
  }
  if (insight.supporting.rateOfChange === "FAST") {
    badges.push({ label: "Fast Tempo", cls: "fast" });
  }
  if (insight.alignment === "above") {
    badges.push({ label: "Market High", cls: "market-high" });
  }
  badges.forEach((badge) => {
    const span = document.createElement("span");
    span.className = `micro-badge ${badge.cls}`;
    span.textContent = badge.label;
    badgesEl.appendChild(span);
  });
}

function renderMetrics(insight) {
  const fields = [
    ["Live Total", insight.supporting.liveTotal.toFixed(1)],
    ["Expected Total", insight.supporting.expectedTotalNow.toFixed(1)],
    ["Line Change", `${insight.supporting.lineChangeSinceTip.toFixed(1)}`],
    ["Rate", insight.supporting.rateOfChange ?? "--"],
    ["Quarter", insight.supporting.quarter],
    ["Clock", insight.supporting.timeRemaining],
  ];
  metricsEl.innerHTML = fields
    .map((entry) => `<dt>${entry[0]}</dt><dd>${entry[1]}</dd>`)
    .join("");
}

async function fetchInsight(gameId) {
  try {
    summaryEl.textContent = "Loading insight...";
    subtextEl.textContent = "";
    const insight = await fetchJson(`/api/games/${gameId}/insight`);
    summaryEl.textContent = insight.summary;
    subtextEl.textContent = formatSubtext(insight);
    renderBadges(insight);
    renderMetrics(insight);
  } catch (error) {
    console.error(error);
    summaryEl.textContent = "Insight unavailable. Retrying.";
    subtextEl.textContent = "";
  }
}

function scheduleRefresh(gameId) {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }
  refreshTimer = setInterval(() => {
    fetchInsight(gameId);
  }, 12000);
}

function renderGameList(games) {
  gameListEl.innerHTML = "";
  if (!games.length) {
    const empty = document.createElement("div");
    empty.className = "game-item";
    empty.textContent = "Awaiting live update.";
    gameListEl.appendChild(empty);
    return;
  }
  games.forEach((game) => {
    const item = document.createElement("div");
    item.className = "game-item";
    item.dataset.gameId = game.gameId;
    item.innerHTML = `
      <span class="label">${game.awayTeam.name} @ ${game.homeTeam.name}</span>
      <span class="meta">${game.liveTotal ? `${game.liveTotal.toFixed(1)} total` : "--"}</span>
    `;
    item.addEventListener("click", () => {
      document
        .querySelectorAll(".game-item")
        .forEach((node) => node.classList.remove("active"));
      item.classList.add("active");
      selectedGameId = game.gameId;
      fetchInsight(selectedGameId);
      scheduleRefresh(selectedGameId);
    });
    gameListEl.appendChild(item);
  });
  if (!selectedGameId && games[0]) {
    gameListEl.firstChild.classList.add("active");
    selectedGameId = games[0].gameId;
    fetchInsight(selectedGameId);
    scheduleRefresh(selectedGameId);
  }
}

async function loadGames() {
  try {
    const payload = await fetchJson("/api/games/live");
    renderGameList(payload.games ?? []);
  } catch (error) {
    console.error(error);
    summaryEl.textContent = "Insight unavailable. Retrying.";
  }
}

loadGames();
setInterval(loadGames, 15000);
