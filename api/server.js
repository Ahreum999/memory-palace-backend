const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const cron = require('node-cron');
const { exec } = require('child_process');

const app = express();
app.use(cors());

const DATA_DIR = path.join(__dirname, '../data');

const MIX = {
  reddit:     0.25,
  bluesky:    0.15,
  tumblr:     0.15,
  mastodon:   0.25,
  newspapers: 0.15,
  wikipedia:  0.05,
};

function loadSource(source) {
  try {
    const raw = fs.readFileSync(
      path.join(DATA_DIR, `${source}.json`), 'utf-8'
    );
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function pickRandom(arr, n) {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

// GET /feed
app.get('/feed', (req, res) => {
  const total = parseInt(req.query.count) || 500;
  const result = [];

  for (const [source, pct] of Object.entries(MIX)) {
    const sentences = loadSource(source);
    const need = Math.floor(total * pct);
    const picked = pickRandom(sentences, need);
    result.push(...picked);
  }

  const mixed = result.sort(() => Math.random() - 0.5);
  res.json({ lines: mixed, total: mixed.length });
});

// GET /stats
app.get('/stats', (req, res) => {
  const stats = {};
  let total = 0;
  for (const source of Object.keys(MIX)) {
    const count = loadSource(source).length;
    stats[source] = count;
    total += count;
  }
  res.json({ stats, total });
});

// GET /health
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// ── SCRAPER RUNNER ───────────────────────────────────────────
function runScraper() {
  const scraperPath = path.join(__dirname, '../scraper/scrape.py');
  console.log(`🔍 Running scraper — ${new Date().toISOString()}`);

  exec(`python ${scraperPath}`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Scraper error: ${error.message}`);
      return;
    }
    if (stderr) console.error(`Scraper stderr: ${stderr}`);
    console.log(`Scraper output:\n${stdout}`);
  });
}

// Run scraper immediately when server starts
runScraper();

// Then run every hour at minute 0
// Format: minute hour day month weekday
cron.schedule('0 * * * *', () => {
  runScraper();
});

console.log('⏰ Scraper scheduled: runs every hour');

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`API running on port ${PORT}`));