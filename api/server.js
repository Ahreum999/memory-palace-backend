const express = require('express');
const cors = require('cors');
const cron = require('node-cron');
const { exec } = require('child_process');
const path = require('path');
const { initDB, getSentences, getStats, getAllSentences } = require('./db');

const app = express();
app.use(cors());

app.get('/', (req, res) => res.json({ status: 'ok' }));
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// Feed — newest sentences first
app.get('/feed', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 500;
    const lines = await getSentences(limit);
    res.json({ lines, total: lines.length });
  } catch (err) {
    console.error('/feed error:', err.message);
    res.status(500).json({ error: err.message, lines: [] });
  }
});

// Stats
app.get('/stats', async (req, res) => {
  try {
    const data = await getStats();
    res.json(data);
  } catch (err) {
    console.error('/stats error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// Archive export — download all sentences as JSON (newest first)
app.get('/archive/export', async (req, res) => {
  try {
    const all = await getAllSentences();
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Content-Disposition',
      `attachment; filename="memory-palace-archive-${new Date().toISOString().split('T')[0]}.json"`
    );
    res.json({
      exported: new Date().toISOString(),
      total: all.length,
      sentences: all
    });
  } catch (err) {
    console.error('/archive/export error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

function runScraper() {
  const scraperPath = path.join(__dirname, '../scraper/scrape.py');
  console.log(`Running scraper — ${new Date().toISOString()}`);

  exec(`python3 ${scraperPath}`, {
    env: process.env,
    timeout: 300000
  }, (error, stdout, stderr) => {
    if (error) {
      console.error(`Scraper error: ${error.message}`);
      return;
    }
    if (stderr) console.error(`Scraper stderr: ${stderr}`);
    if (stdout) console.log(`Scraper output:\n${stdout}`);
  });
}

setTimeout(runScraper, 10000);
cron.schedule('0 * * * *', runScraper);
console.log('Scraper scheduled: runs every hour');

const PORT = process.env.PORT || 3001;

initDB().then(() => {
  app.listen(PORT, () => console.log(`API running on port ${PORT}`));
}).catch(err => {
  console.error('DB init failed:', err.message);
  app.listen(PORT, () => console.log(`API running on port ${PORT} (no DB)`));
});
