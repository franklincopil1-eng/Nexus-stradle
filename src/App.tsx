import { useState, useEffect, useRef } from 'react';
import { Activity, Shield, AlertTriangle, Terminal, Zap, TrendingUp, TrendingDown } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'STRATEGY' | 'EXECUTION' | 'ERROR';
  message: string;
}

interface Order {
  ticket: string;
  type: 'BUY STOP' | 'SELL STOP' | 'BUY' | 'SELL';
  volume: string;
  price: string;
  sl: string;
  tp: string;
  status: 'PENDING' | 'OPEN';
}

export default function App() {
  const [price, setPrice] = useState(0);
  const [spread, setSpread] = useState(0);
  const [rangeHigh, setRangeHigh] = useState(0);
  const [rangeLow, setRangeLow] = useState(0);
  const [riskSettings, setRiskSettings] = useState({
    fixedLot: 0,
    slPoints: 0,
    tpPoints: 0,
    trailingStop: 0,
    lookback: 0
  });
  const [systemStatus, setSystemStatus] = useState('ENGAGED');
  const [account, setAccount] = useState({
    balance: 0,
    equity: 0,
    marginFree: 0,
    floatingPL: 0
  });
  const [orders, setOrders] = useState<Order[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connectedBrokers, setConnectedBrokers] = useState<string[]>([]);
  
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch('/api/state');
        const data = await res.json();
        setPrice(data.price);
        setSpread(data.spread);
        setRangeHigh(data.rangeHigh);
        setRangeLow(data.rangeLow);
        setRiskSettings(data.riskSettings);
        setSystemStatus(data.systemStatus);
        setAccount(data.account);
        setOrders(data.orders);
        setLogs(data.logs);
        
        // Extract unique broker names from orders or logs if not explicitly provided
        // For now, let's assume we can get them from the logs or just hardcode the ones we expect if they have logs
        const brokers = new Set<string>();
        data.logs.forEach((l: LogEntry) => {
          if (l.message.includes("Connected to")) {
            const match = l.message.match(/Connected to ([^:]+)/);
            if (match) brokers.add(match[1]);
          }
        });
        setConnectedBrokers(Array.from(brokers));
      } catch (err) {
        console.error("Failed to fetch state", err);
      }
    };

    const interval = setInterval(fetchState, 1000);
    return () => clearInterval(interval);
  }, []);

  const sendCommand = async (command: string) => {
    try {
      await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });
    } catch (err) {
      console.error("Failed to send command", err);
    }
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#0a0a0b] text-[#e2e2e4]">
      {/* Header */}
      <header className="h-[60px] border-b border-[#27272a] flex items-center justify-between px-6 bg-[#151518]">
        <div className="flex items-center gap-2.5 font-extrabold tracking-[2px]">
          ATLAS-X 
          <span className="text-[#71717a] font-light text-xs tracking-normal">// EXECUTION ENGINE</span>
        </div>
        <div className="flex gap-8">
          {connectedBrokers.map(broker => (
            <div key={broker} className="flex items-center gap-2 text-[12px] uppercase tracking-wider text-[#22c55e]">
              <div className="w-2 h-2 bg-[#22c55e] rounded-full shadow-[0_0_8px_#22c55e]" />
              {broker}: CONNECTED
            </div>
          ))}
          {connectedBrokers.length === 0 && (
            <div className="flex items-center gap-2 text-[12px] uppercase tracking-wider text-[#71717a]">
              <div className="w-2 h-2 bg-[#71717a] rounded-full" />
              WAITING FOR BROKERS...
            </div>
          )}
          <div className="flex items-center gap-2 text-[12px] uppercase tracking-wider text-[#71717a]">
            <div className="w-2 h-2 bg-[#71717a] rounded-full" />
            STRATEGY: MULTI_BROKER_RUNNING
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 grid grid-cols-[320px_1fr_300px] gap-px bg-[#27272a]">
        {/* Left Pane: Market Data & Account */}
        <section className="pane">
          <div>
            <h3 className="section-title">Market Data: XAUUSD</h3>
            <div className="flex flex-col items-center justify-center h-[120px] bg-[#151518] rounded border border-[#27272a]">
              <motion.div 
                key={price}
                initial={{ opacity: 0.5 }}
                animate={{ opacity: 1 }}
                className="text-[42px] font-mono font-bold"
              >
                {price.toFixed(2)}
              </motion.div>
              <div className="text-xs text-[#71717a] mt-2">
                Spread: {spread} pts | Tick: 0.01
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="stat-card">
              <div className="stat-label">Range High ({riskSettings.lookback * 5}m)</div>
              <div className="stat-value">{rangeHigh.toFixed(2)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Range Low ({riskSettings.lookback * 5}m)</div>
              <div className="stat-value">{rangeLow.toFixed(2)}</div>
            </div>
          </div>

          <div>
            <h3 className="section-title">Account Metrics</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="stat-card">
                <div className="stat-label">Balance</div>
                <div className="stat-value">${account.balance.toLocaleString()}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Equity</div>
                <div className="stat-value">${account.equity.toLocaleString()}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Margin Free</div>
                <div className="stat-value">${account.marginFree.toLocaleString()}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Floating P/L</div>
                <div className={`stat-value ${account.floatingPL >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
                  ${account.floatingPL.toLocaleString()}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Center Pane: Execution Pipeline */}
        <section className="pane border-x border-[#27272a]">
          <h3 className="section-title">Live Execution Pipeline</h3>
          <table className="w-full border-collapse order-table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Type</th>
                <th>Volume</th>
                <th>Entry/Price</th>
                <th>S/L</th>
                <th>T/P</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order, idx) => (
                <tr key={order.ticket} className={order.status === 'OPEN' ? 'bg-white/5' : ''}>
                  <td>{order.ticket}</td>
                  <td>
                    <span className={`badge ${order.type.includes('BUY') ? 'bg-[#22c55e]/20 text-[#22c55e]' : 'bg-[#ef4444]/20 text-[#ef4444]'}`}>
                      {order.type}
                    </span>
                  </td>
                  <td>{order.volume}</td>
                  <td>{order.price}</td>
                  <td>{order.sl}</td>
                  <td>{order.tp}</td>
                  <td className={order.status === 'OPEN' ? 'text-[#22c55e]' : ''}>{order.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* Right Pane: Risk & Strategy */}
        <section className="pane">
          <h3 className="section-title">Risk & Strategy</h3>
          <div className="flex flex-col gap-2.5">
            <button 
              onClick={() => sendCommand(systemStatus === 'ENGAGED' ? 'HALT' : 'RESUME')}
              className={`btn ${systemStatus === 'ENGAGED' ? 'btn-active' : 'border-[#ef4444] text-[#ef4444]'}`}
            >
              {systemStatus === 'ENGAGED' ? 'SYSTEM ENGAGED' : 'SYSTEM HALTED'}
            </button>
            <button 
              onClick={() => sendCommand('CLOSE_ALL')}
              className="btn hover:border-[#ef4444] hover:text-[#ef4444]"
            >
              HALT & CLOSE ALL
            </button>
          </div>
          
          <div className="space-y-3">
            <div className="stat-card">
              <div className="stat-label">Fixed Lot Size</div>
              <div className="stat-value">{riskSettings.fixedLot} Lots</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">S/L | T/P Points</div>
              <div className="stat-value">{riskSettings.slPoints} | {riskSettings.tpPoints}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Trailing Stop</div>
              <div className="stat-value">{riskSettings.trailingStop} pts</div>
            </div>
          </div>

          <div className="mt-auto p-3 bg-[#eab308]/10 border border-[#eab308] rounded">
            <div className="stat-label text-[#eab308] flex items-center gap-1.5">
              <AlertTriangle size={10} /> System Notice
            </div>
            <div className="text-[11px] leading-relaxed">
              {logs.filter(l => l.level === 'ERROR').length > 0 
                ? `Latest Error: ${logs.filter(l => l.level === 'ERROR').slice(-1)[0].message}`
                : `System operational. Monitoring ${connectedBrokers.length} brokers.`}
            </div>
          </div>
        </section>
      </main>

      {/* Footer: Log Viewport */}
      <div className="h-[240px] bg-black border-t border-[#27272a] p-3 font-mono text-[11px] overflow-y-auto text-[#88cc88]">
        {logs.map((log, idx) => (
          <div key={idx} className="mb-1 whitespace-nowrap">
            <span className="text-[#71717a] mr-2">[{log.timestamp}]</span>
            <span className={`mr-2 ${
              log.level === 'INFO' ? 'text-white' : 
              log.level === 'STRATEGY' ? 'text-[#eab308]' : 
              'text-[#22c55e]'
            }`}>
              {log.level}:
            </span>
            {log.message}
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
