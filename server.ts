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
    price: 2024.58,
    spread: 1.2,
    account: {
      balance: 10000.00,
      equity: 10000.00,
      marginFree: 10000.00,
      floatingPL: 0.00
    },
    orders: [],
    logs: [
      { timestamp: new Date().toLocaleTimeString(), level: 'INFO', message: 'API Server Started. Waiting for MT5 connection...' }
    ]
  };

  // API Routes
  app.get("/api/state", (req, res) => {
    res.json(tradingState);
  });

  app.post("/api/update", (req, res) => {
    const { price, spread, account, orders, log } = req.body;
    
    if (price !== undefined) tradingState.price = price;
    if (spread !== undefined) tradingState.spread = spread;
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
