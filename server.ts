import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // In-memory state for the trading dashboard
  let tradingState = {
    price: 0,
    spread: 0,
    rangeHigh: 0,
    rangeLow: 0,
    systemStatus: 'ENGAGED', // 'ENGAGED' or 'HALTED'
    riskSettings: {
      fixedLot: 0,
      slPoints: 0,
      tpPoints: 0,
      trailingStop: 0,
      lookback: 0
    },
    account: {
      balance: 0,
      equity: 0,
      marginFree: 0,
      floatingPL: 0
    },
    orders: [],
    logs: [
      { timestamp: new Date().toLocaleTimeString(), level: 'INFO', message: 'API Server Started. Waiting for MT5 connection...' }
    ],
    commands: [] as string[]
  };

  // API Routes
  app.get("/api/state", (req, res) => {
    console.log("GET /api/state requested");
    res.json(tradingState);
  });

  app.post("/api/command", (req, res) => {
    const { command } = req.body;
    console.log(`POST /api/command: ${command}`);
    if (command) {
      tradingState.commands.push(command);
      if (command === 'HALT') tradingState.systemStatus = 'HALTED';
      if (command === 'RESUME') tradingState.systemStatus = 'ENGAGED';
      
      tradingState.logs.push({
        timestamp: new Date().toLocaleTimeString(),
        level: 'INFO',
        message: `UI Command Received: ${command}`
      });
      res.json({ status: "ok" });
    } else {
      res.status(400).json({ error: "No command provided" });
    }
  });

  app.get("/api/commands", (req, res) => {
    const commands = [...tradingState.commands];
    tradingState.commands = []; // Clear after fetching
    res.json({ commands });
  });

  app.post("/api/update", (req, res) => {
    const { price, spread, rangeHigh, rangeLow, riskSettings, account, orders, log } = req.body;
    
    if (price !== undefined) tradingState.price = price;
    if (spread !== undefined) tradingState.spread = spread;
    if (rangeHigh !== undefined) tradingState.rangeHigh = rangeHigh;
    if (rangeLow !== undefined) tradingState.rangeLow = rangeLow;
    if (riskSettings) tradingState.riskSettings = riskSettings;
    if (account) tradingState.account = account;
    if (orders) tradingState.orders = orders;
    if (log) {
      tradingState.logs.push({
        timestamp: new Date().toLocaleTimeString(),
        ...log
      });
      // Keep last 100 logs
      if (tradingState.logs.length > 100) {
        tradingState.logs.shift();
      }
    }
    
    res.json({ status: "ok" });
  });

  // Catch-all for /api routes to prevent falling through to SPA fallback
  app.all("/api/*", (req, res) => {
    res.status(404).json({ error: `API route not found: ${req.method} ${req.url}` });
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
