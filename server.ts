import express from "express";
import cors from "cors";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import { initializeApp } from "firebase/app";
import { initializeFirestore, doc, getDoc, setDoc, updateDoc, collection, addDoc, query, orderBy, limit, getDocs, onSnapshot } from "firebase/firestore";
import fs from "fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Firebase Setup
const firebaseConfig = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'firebase-applet-config.json'), 'utf8'));
const firebaseApp = initializeApp(firebaseConfig);
const db = initializeFirestore(firebaseApp, {
  experimentalForceLongPolling: true,
}, firebaseConfig.firestoreDatabaseId);

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(cors());
  app.use(express.json({ limit: '1mb' }));

  app.use((req, res, next) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url} - ${req.ip}`);
    next();
  });

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
    brokers: [] as any[],
    orders: [],
    history: [] as any[],
    logs: [
      { timestamp: new Date().toLocaleTimeString(), level: 'INFO', message: 'API Server Started. Waiting for MT5 connection...' }
    ],
    backtestResult: null as any,
    lastHeartbeat: 0,
    commands: [] as string[]
  };

  // Initialize state from Firestore
  try {
    const stateDoc = await getDoc(doc(db, "system", "state"));
    if (stateDoc.exists()) {
      const data = stateDoc.data();
      tradingState = { ...tradingState, ...data };
      console.log("✅ Trading state restored from Firestore");
    }

    const backtestDoc = await getDoc(doc(db, "system", "backtest"));
    if (backtestDoc.exists()) {
      tradingState.backtestResult = backtestDoc.data();
    }

    // Load recent logs
    const logsSnap = await getDocs(query(collection(db, "logs"), orderBy("timestamp", "desc"), limit(50)));
    tradingState.logs = logsSnap.docs.map(d => d.data() as any).reverse();

    // Load recent history (simulated from logs or separate collection if you want)
    // For now we keep history in memory or load if we added a collection
  } catch (err) {
    console.error("❌ Failed to initialize from Firebase:", err);
  }

  // API Routes
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", timestamp: new Date().toISOString() });
  });

  app.get("/api/state", (req, res) => {
    try {
      const now = Date.now();
      const isBridgeActive = (now - tradingState.lastHeartbeat) < 30000; // 30s timeout
      res.json({ 
        ...tradingState, 
        bridgeActive: isBridgeActive && tradingState.lastHeartbeat > 0 
      });
    } catch (err) {
      console.error("Error serving /api/state:", err);
      res.status(500).json({ error: "Internal server error" });
    }
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

  app.post("/api/update", async (req, res) => {
    const { price, spread, rangeHigh, rangeLow, riskSettings, account, brokers, orders, history, log, backtest } = req.body;
    
    tradingState.lastHeartbeat = Date.now();

    const stateUpdate: any = { lastHeartbeat: tradingState.lastHeartbeat };

    if (price !== undefined) {
      tradingState.price = price;
      stateUpdate.price = price;
    }
    if (spread !== undefined) {
      tradingState.spread = spread;
      stateUpdate.spread = spread;
    }
    if (rangeHigh !== undefined) {
      tradingState.rangeHigh = rangeHigh;
      stateUpdate.rangeHigh = rangeHigh;
    }
    if (rangeLow !== undefined) {
      tradingState.rangeLow = rangeLow;
      stateUpdate.rangeLow = rangeLow;
    }
    if (riskSettings) {
      tradingState.riskSettings = riskSettings;
      stateUpdate.riskSettings = riskSettings;
    }
    if (account) {
      tradingState.account = account;
      stateUpdate.account = account;
    }
    
    // Persistent update for the core state
    try {
      await setDoc(doc(db, "system", "state"), stateUpdate, { merge: true });
    } catch (e) {
      console.error("Firestore State Update Error:", e);
    }

    if (brokers) tradingState.brokers = brokers;
    if (orders) tradingState.orders = orders;
    
    if (history) {
      if (Array.isArray(history)) {
        tradingState.history = [...history, ...tradingState.history].slice(0, 100);
      } else {
        tradingState.history = [history, ...tradingState.history].slice(0, 100);
      }
    }

    if (backtest) {
      tradingState.backtestResult = backtest;
      tradingState.logs.push({
        timestamp: new Date().toLocaleTimeString(),
        level: 'SUCCESS',
        message: 'New Backtest Results Uploaded to Dashboard'
      });
      await setDoc(doc(db, "system", "backtest"), backtest);
    }

    if (log) {
      const logEntry = {
        timestamp: new Date().toLocaleTimeString(),
        ...log
      };
      tradingState.logs.push(logEntry);
      if (tradingState.logs.length > 100) tradingState.logs.shift();
      
      // Persist logs
      try {
        await addDoc(collection(db, "logs"), logEntry);
      } catch (e) {
        console.error("Firestore Log Error:", e);
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
