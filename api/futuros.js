// Vercel Serverless Function — futuros ROFEX via Primary API (reMarkets/prod)
// Autenticación: X-Username / X-Password → X-Auth-Token
// Endpoint: api.remarkets.primary.com.ar (sandbox) o api.primary.com.ar (prod)

const PRIMARY_URL = process.env.PRIMARY_URL || 'https://api.primary.com.ar';
const PRIMARY_USER = process.env.PRIMARY_USER || '';
const PRIMARY_PASS = process.env.PRIMARY_PASS || '';

// Contratos DLR Mayorista (con M al final)
const CONTRACTS = [
  'DLR/JUL26M', 'DLR/AGO26M', 'DLR/SEP26M', 'DLR/OCT26M',
  'DLR/NOV26M', 'DLR/DIC26M', 'DLR/ENE27M', 'DLR/FEB27M',
  'DLR/MAR27M', 'DLR/ABR27M', 'DLR/MAY27M', 'DLR/JUN27M'
];

const TICKER_TO_KEY = {
  'DLR/JUL26M':'JUL 26', 'DLR/AGO26M':'AGO 26', 'DLR/SEP26M':'SEP 26',
  'DLR/OCT26M':'OCT 26', 'DLR/NOV26M':'NOV 26', 'DLR/DIC26M':'DIC 26',
  'DLR/ENE27M':'ENE 27', 'DLR/FEB27M':'FEB 27', 'DLR/MAR27M':'MAR 27',
  'DLR/ABR27M':'ABR 27', 'DLR/MAY27M':'MAY 27', 'DLR/JUN27M':'JUN 27'
};

async function getToken() {
  const res = await fetch(`${PRIMARY_URL}/auth/getToken`, {
    method: 'POST',
    headers: {
      'X-Username': PRIMARY_USER,
      'X-Password': PRIMARY_PASS
    }
  });
  if (!res.ok) throw new Error(`Auth failed: ${res.status}`);
  const token = res.headers.get('X-Auth-Token');
  if (!token) throw new Error('No token in response');
  return token;
}

async function getMarketData(token, ticker) {
  const entries = 'LA,CL,SE';
  const url = `${PRIMARY_URL}/rest/marketdata/get?marketId=ROFX&symbol=${encodeURIComponent(ticker)}&entries=${entries}`;
  const res = await fetch(url, { headers: { 'X-Auth-Token': token } });
  if (!res.ok) return null;
  return res.json();
}

export default async function handler(req, res) {
  // Fuera de horario: devolver vacío (el frontend usa FUT_DEFAULT)
  const now = new Date();
  const ar = new Date(now.getTime() - 3 * 60 * 60 * 1000);
  const d = ar.getDay(), m = ar.getHours() * 60 + ar.getMinutes();
  const marketOpen = d >= 1 && d <= 5 && m >= 600 && m < 1020; // 10:00-17:00 AR

  if (!marketOpen) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json({ open: false });
    return;
  }

  try {
    const token = await getToken();
    const result = {};

    // Traer todos los contratos en paralelo
    const promises = CONTRACTS.map(async (ticker) => {
      try {
        const data = await getMarketData(token, ticker);
        if (!data || data.status !== 'OK' || !data.marketData) return;
        const md = data.marketData;
        /* LA = último operado, SE = settlement. En contratos M suelen tener SE aunque no operen */
        const ultimo = (md.LA && md.LA.price > 0 ? md.LA.price : null) ||
                       (md.SE && md.SE.price > 0 ? md.SE.price : null) ||
                       (md.CL && md.CL.price > 0 ? md.CL.price : null);
        const key = TICKER_TO_KEY[ticker];
        if (key && ultimo) {
          result[key] = { ultimo, variacion: 0 };
        }
      } catch (e) {}
    });

    await Promise.all(promises);

    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json({ open: true, ...result });

  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
