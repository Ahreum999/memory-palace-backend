const express = require('express');
const cors = require('cors');
const cron = require('node-cron');
const { exec } = require('child_process');
const path = require('path');
const https = require('https');
const {
  initDB, getSentences, getStats, getAllSentences,
  getTotal, getOldestSentences, deleteSentencesById,
  KEEP_COUNT, ARCHIVE_THRESHOLD
} = require('./db');

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

// Manual full export (still available)
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

// ── GITHUB ARCHIVE PUSH ────────────────────────────────────
async function pushToGitHub(filename, content) {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.ARCHIVE_REPO || 'memory-palace-archive';
  const owner = process.env.GITHUB_OWNER || 'Ahreum999';

  if (!token) {
    console.error('Archive: GITHUB_TOKEN not set — skipping push');
    return false;
  }

  const body = JSON.stringify({
    message: `Archive ${filename}`,
    content: Buffer.from(content).toString('base64')
  });

  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: 'api.github.com',
      path: `/repos/${owner}/${repo}/contents/archives/${filename}`,
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': 'memory-palace-backend',
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode === 201 || res.statusCode === 200) {
          console.log(`Archive: pushed ${filename} to GitHub`);
          resolve(true);
        } else {
          console.error(`Archive: GitHub push failed (${res.statusCode}): ${data}`);
          resolve(false);
        }
      });
    });
    req.on('error', (err) => {
      console.error(`Archive: GitHub push error: ${err.message}`);
      resolve(false);
    });
    req.write(body);
    req.end();
  });
}

// ── AUTO ARCHIVE ────────────────────────────────────────────
async function checkAndArchive() {
  try {
    const total = await getTotal();
    console.log(`Archive check: ${total} sentences (threshold: ${ARCHIVE_THRESHOLD})`);

    if (total <= ARCHIVE_THRESHOLD) return;

    const toArchiveCount = total - KEEP_COUNT;
    console.log(`Archiving ${toArchiveCount} oldest sentences (keeping ${KEEP_COUNT})...`);

    // Get the oldest sentences
    const oldest = await getOldestSentences(toArchiveCount);

    // Build the archive JSON
    const now = new Date();
    const timestamp = now.toISOString().replace(/[:.]/g, '-').split('T');
    const filename = `archive-${timestamp[0]}-${timestamp[1].substring(0, 8)}.json`;
    const archiveData = JSON.stringify({
      archived: now.toISOString(),
      count: oldest.length,
      dateRange: {
        oldest: oldest[0]?.added,
        newest: oldest[oldest.length - 1]?.added
      },
      sentences: oldest
    }, null, 2);

    // Push to GitHub
    const pushed = await pushToGitHub(filename, archiveData);

    if (pushed) {
      // Only delete after successful push
      const ids = oldest.map(s => s.id);
      const deleted = await deleteSentencesById(ids);
      console.log(`Archive complete: ${deleted} sentences removed, ${KEEP_COUNT} remain`);
    } else {
      console.error('Archive: skipping delete — GitHub push failed');
    }
  } catch (err) {
    console.error('Archive error:', err.message);
  }
}

// ── SCRAPER ─────────────────────────────────────────────────
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

    // After scraper finishes, check if we need to archive
    checkAndArchive();
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
