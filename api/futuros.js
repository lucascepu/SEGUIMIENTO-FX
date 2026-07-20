// Vercel Serverless Function — proxy futuros MAE en tiempo real
export default async function handler(req, res) {
  const apiKey = process.env.MAE_API_KEY;
  if (!apiKey) {
    res.status(500).json({ error: 'MAE_API_KEY no configurada' });
    return;
  }

  // Fecha de hoy AR (UTC-3)
  const now = new Date();
  const ar = new Date(now.getTime() - 3 * 60 * 60 * 1000);
  const fecha = ar.toISOString().slice(0, 10);

  const payload = JSON.stringify({ fechaDesde: fecha, fechaHasta: fecha, contratosSinVolumen: false });
  const url = `https://api.marketdata.mae.com.ar/api/cem/monedas/fut?oData=${encodeURIComponent(payload)}`;

  try {
    const response = await fetch(url, { headers: { 'x-api-key': apiKey } });
    if (!response.ok) {
      res.status(502).json({ error: `MAE status ${response.status}` });
      return;
    }
    const data = await response.json();

    // Mapeo posición → key
    const MESES = {
      '01':'ENE','02':'FEB','03':'MAR','04':'ABR','05':'MAY','06':'JUN',
      '07':'JUL','08':'AGO','09':'SEP','10':'OCT','11':'NOV','12':'DIC'
    };
    const result = {};
    for (const item of data) {
      const pos = item.posicion || '';
      if (!pos.startsWith('DLR') || pos.length < 9) continue;
      const mm = pos.slice(3, 5), yy = pos.slice(7, 9);
      const mes = MESES[mm];
      if (!mes) continue;
      const key = `${mes} ${yy}`;
      result[key] = {
        ultimo: item.precioUltimo,
        ajuste: item.precioAjuste,
        variacion: item.variacionPorcentaje
      };
    }

    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json(result);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
