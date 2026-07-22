// Vercel Serverless Function — futuros ROFEX via Primary API (reMarkets/prod)
// Autenticación: X-Username / X-Password → X-Auth-Token
// Endpoint: api.remarkets.primary.com.ar (sandbox) o api.primary.com.ar (prod)

const PRIMARY_URL = process.env.PRIMARY_URL || 'https://api.remarkets.primary.com.ar';
const PRIMARY_USER = process.env.PRIMARY_USER || '';
const PRIMARY_PASS = process.env.PRIMARY_PASS || '';

// Contratos DLR a consultar
const CONTRACTS = [
  'DLR/JUL26', 'DLR/AGO26', 'DLR/SEP26', 'DLR/OCT26',
  'DLR/NOV26', 'DLR/DIC26', 'DLR/ENE27', 'DLR/FEB27',
  'DLR/MAR27', 'DLR/ABR27', 'DLR/MAY27', 'DLR/JUN27'
];

// Mapeo ticker → key de FUT_DEFAULT
const TICKER_TO_KEY = {
  'DLR/JUL26':'JUL 26', 'DLR/AGO26':'AGO 26', 'DLR/SEP26':'SEP 26',
  'DLR/OCT26':'OCT 26', 'DLR/NOV26':'NOV 26', 'DLR/DIC26':'DIC 26',
  'DLR/ENE27':'ENE 27', 'DLR/FEB27':'FEB 27', 'DLR/MAR27':'MAR 27',
  'DLR/ABR27':'ABR 27', 'DLR/MAY27':'MAY 27', 'DLR/JUN27':'JUN 27'
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
  const entries = 'LA,BI,OF,OP,CL,SE,OI';
  const url = `${PRIMARY_URL}/rest/marketdata/get?marketId=ROFEX&symbol=${encodeURIComponent(ticker)}&entries=${entries}`;
  const res = await fetch(url, { headers: { 'X-Auth-Token': token } });
  if (!res.ok) return null;
  return res.json();
}

export default async function handler(req, res) {
  // Fuera de horario: devolver vacío (el frontend usa FUT_DEFAULT)
  const now = new Date();
  const ar = new Date(now.getTime() - 3 * 60 * 60 * 1000);
  const d = ar.getDay(), m = ar.getHours() * 60 + ar.getMinutes();
  const marketOpen = d >= 1 && d <= 5 && m >= 600 && m < 900;

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
        if (!data || !data.marketData) return;
        const md = data.marketData;
        const ultimo = md.LA && md.LA[0] ? md.LA[0].price : null;
        const key = TICKER_TO_KEY[ticker];
        if (key && ultimo) {
          result[key] = { ultimo, variacion: md.LA[0].change || 0 };
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
