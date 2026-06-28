"use strict";
/* q20 league UI — pure client-side. Reads the canonical SDK logs:
 *   league: { standings:{group:pts}, ranking:[group], rounds:[{judge,player,outcome,scores,guess,correct}] }
 *   round : { public_view:{hint,chain}, questions:[{text,options,chosen}], guess, truth, outcome, scores, models }
 * No build step, no deps. Served by scripts/ui_server.py (no-cache) so artifacts/ are fetchable. */

const $ = (id) => document.getElementById(id);
const MEDALS = ["\u{1F947}", "\u{1F948}", "\u{1F949}"];

/* Rank -> grade: 1st ~100, last ~70, linear. Mirrors the brief's grade mapping. */
function gradeFor(rank, total) {
  if (total <= 1) return 100;
  return Math.round(100 - (30 * rank) / (total - 1));
}

function setTab(name) {
  for (const t of ["standings", "replay"]) {
    $("tab-" + t).classList.toggle("active", t === name);
    $("view-" + t).classList.toggle("active", t === name);
  }
}

/* ---- League standings ---- */
function renderLeague(data) {
  const ranking = data.ranking || Object.keys(data.standings || {});
  const standings = data.standings || {};
  const body = $("standings-body");
  body.innerHTML = "";
  const max = Math.max(1, ...Object.values(standings));
  ranking.forEach((g, i) => {
    const pts = standings[g] ?? 0;
    const tr = document.createElement("tr");
    if (i === 0) tr.className = "rank-1";
    const medal = i < 3 ? `<span class="medal">${MEDALS[i]}</span>` : "";
    tr.innerHTML =
      `<td>${i + 1}</td><td>${medal}${esc(g)}</td><td class="pts">${pts}</td>` +
      `<td><div class="bar" style="width:${Math.round((100 * pts) / max)}%"></div></td>` +
      `<td class="grade">${gradeFor(i, ranking.length)}</td>`;
    body.appendChild(tr);
  });
  $("standings-empty").style.display = ranking.length ? "none" : "";

  const rb = $("rounds-body");
  rb.innerHTML = "";
  for (const r of data.rounds || []) {
    const tr = document.createElement("tr");
    const oc = (r.outcome || "").toLowerCase();
    const guessed = r.correct ? '<span class="ok">✔</span>' : '<span class="bad">✗</span>';
    tr.innerHTML =
      `<td>${esc(r.judge)}</td><td>${esc(r.player)}</td>` +
      `<td><span class="chip ${oc}">${esc(r.outcome)}</span></td>` +
      `<td class="pts">${r.scores?.player ?? "-"}</td><td class="pts">${r.scores?.judge ?? "-"}</td>` +
      `<td>${guessed}</td>`;
    rb.appendChild(tr);
  }
}

/* ---- Single-round replay ---- */
function renderRound(d) {
  $("replay-empty").style.display = "none";
  const models = d.models || {};
  $("r-judge").textContent = "JUDGE · " + (models.judge || "?");
  $("r-player").textContent = "PLAYER · " + (models.player || "?");
  const oc = (d.outcome || "").toLowerCase();
  const ochip = $("r-outcome");
  ochip.textContent = (d.outcome || "?").toUpperCase();
  ochip.className = "chip " + oc;

  const pv = d.public_view || {};
  $("r-hint").textContent = pv.hint || "—";
  const chain = $("r-chain");
  chain.innerHTML = "";
  (pv.chain || []).forEach((w, i) => {
    if (i) chain.insertAdjacentHTML("beforeend", '<span class="arrow">→</span>');
    const s = document.createElement("span");
    s.className = "link";
    s.textContent = w;
    chain.appendChild(s);
  });

  const list = $("qa-list");
  list.innerHTML = "";
  (d.questions || []).forEach((q, i) => {
    const li = document.createElement("li");
    li.className = "qa";
    const opts = (q.options || [])
      .map((o, j) => `<span class="opt ${j === q.chosen ? "chosen" : ""}">${esc(o)}</span>`)
      .join("");
    li.innerHTML = `<p class="q"><span class="n">${i + 1}.</span>${esc(q.text)}</p><div class="opts">${opts}</div>`;
    list.appendChild(li);
  });

  const guess = d.guess || {}, truth = d.truth || {};
  fill("g-sentence", guess.opening_sentence, truth.opening_sentence);
  fill("t-sentence", truth.opening_sentence);
  fill("g-word", guess.associative_word, truth.associative_word);
  fill("t-word", truth.associative_word);
  const wordOk = norm(guess.associative_word) === norm(truth.associative_word);
  $("word-mark").innerHTML = wordOk ? '<span class="ok">✔ match</span>' : '<span class="bad">✗ miss</span>';

  const sc = d.scores || {};
  $("s-judge").textContent = sc.judge ?? 0;
  $("s-player").textContent = sc.player ?? 0;
  $("m-judge").textContent = models.judge || "";
  $("m-player").textContent = models.player || "";
}

function fill(id, val, truth) {
  const el = $(id);
  el.textContent = val || "—";
  if (truth !== undefined) el.className = norm(val) === norm(truth) ? "ok" : "bad";
}
const norm = (s) => (s || "").toLowerCase().replace(/[^a-z0-9֐-׿ ]/g, "").trim();
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---- Loading ---- */
async function fetchJson(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(r.status + " " + path);
  return r.json();
}
async function reload() {
  let any = false;
  try { renderLeague(await fetchJson("../artifacts/league.json")); any = true; } catch (e) { /* none yet */ }
  try { renderRound(await fetchJson("../artifacts/round_log.json")); any = true; } catch (e) { /* none yet */ }
  if (!any) try { renderRound(await fetchJson("sample_round.json")); } catch (e) { /* bundled fallback */ }
  $("src").textContent = any ? "loaded from artifacts/" : "no artifacts yet — run q20 first, or use Load buttons";
}
function loadFile(input, render) {
  const f = input.files[0];
  if (!f) return;
  const fr = new FileReader();
  fr.onload = () => { try { render(JSON.parse(fr.result)); $("src").textContent = "loaded " + f.name; } catch (e) { alert("Bad JSON: " + e); } };
  fr.readAsText(f);
}

$("tab-standings").onclick = () => setTab("standings");
$("tab-replay").onclick = () => setTab("replay");
$("btn-reload").onclick = reload;
$("file-league").onchange = (e) => loadFile(e.target, (d) => { renderLeague(d); setTab("standings"); });
$("file-round").onchange = (e) => loadFile(e.target, (d) => { renderRound(d); setTab("replay"); });
reload();
