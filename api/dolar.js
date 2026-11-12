// Vercel Serverless Function — último dato de MAE (SIOPEL, UST$T segmento M), devuelve { mayorista }.
// Requiere la variable de entorno MAE_API_KEY. Sin fallback a otras fuentes: si MAE no trae dato, responde error.
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');
  try {
    const apiKey = process.env.MAE_API_KEY;
    if (!apiKey) { res.status(500).json({ error: 'MAE_API_KEY no definida' }); return; }
    // fecha de hoy en Argentina (YYYY-MM-DD)
    const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Argentina/Buenos_Aires' }).format(new Date());
    const payload = JSON.stringify({ fechaDesde: hoy, fechaHasta: hoy });
    const url = 'https://api.marketdata.mae.com.ar/api/mercado/titulo/historicoforex?oTitulo=' + encodeURIComponent(payload);
    const response = await fetch(url, { headers: { 'x-api-key': apiKey, 'Accept': 'application/json' } });
    if (!response.ok) { res.status(502).json({ error: `MAE status ${response.status}` }); return; }
    const data = await response.json();
    let precio = null, plazo = null;
    for (const p of ['001', '000']) {
      for (const dia of (Array.isArray(data) ? data : [])) {
        for (const d of (dia.details || [])) {
          if (d.ticker === 'UST$T' && d.codigoSegmento === 'M' && d.plazo === p && d.precioCierre) {
            precio = Math.round(parseFloat(d.precioCierre) * 100) / 100; plazo = p;
          }
        }
      }
      if (precio) break;
    }
    if (!precio) { res.status(404).json({ error: 'MAE sin dato UST$T para hoy', fecha: hoy }); return; }
    res.status(200).json({ mayorista: precio, fecha: hoy, plazo, fuente: 'MAE' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
