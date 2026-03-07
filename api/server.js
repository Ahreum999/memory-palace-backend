const express = require('express');
const cors = require('cors');
const cron = require('node-cron');
const { exec } = require('child_process');
const path = require('path');
const { initDB, getSentences, getStats } = require('./db');

const app = express();
app.use(cors());

app.get('/', (req, res) => res.json({ status: 'ok' }));
app.get('/health', (req, res) => res.json({ status: 'ok' }));

app.get('/feed', async (req, res) => {
  try {
    const lines = await getSentences(500);
    res.json({ lines, total: lines.length });
  } catch (err) {
    res.status(500).json({ error: err.message, lines: [] });
  }
});

app.get('/stats', async (req, res) => {
  try {
    const data = await getStats();
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

function runScraper() {
  const scraperPath = path.join(__dirname, '../scraper/scrape.py');
  console.log(`Running scraper — ${new Date().toISOString()}`);

  exec(`python3 ${scraperPath}`, {
    env: {
      ...process.env,
      DATABASE_URL: process.env.DATABASE_URL
    }
  }, (error, stdout, stderr) => {
    if (error) {
      console.error(`Scraper error: ${error.message}`);
      return;
    }
    if (stderr) console.error(`Scraper stderr: ${stderr}`);
    console.log(`Scraper output:\n${stdout}`);
  });
}

setTimeout(runScraper, 5000);
cron.schedule('0 * * * *', runScraper);
console.log('Scraper scheduled: runs every hour');

const PORT = process.env.PORT || 3001;

initDB().then(() => {
  app.listen(PORT, () => console.log(`API running on port ${PORT}`));
}).catch(err => {
  console.error('DB init failed:', err.message);
  app.listen(PORT, () => console.log(`API running on port ${PORT} (no DB)`));
});