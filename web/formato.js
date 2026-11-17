// Lectura de montos escritos a mano, con las convenciones de Ecuador (es-EC), que son las
// que usa la página para mostrarlos: punto de miles y coma decimal («1.250,50»).
// Devuelve NaN si el texto no es un monto válido.
export function leerMonto(texto) {
  const t = String(texto ?? '').replace(/\s/g, '');
  if (!/^\d[\d.,]*$/.test(t) || /[.,]$/.test(t)) return NaN;
  const ultimoPunto = t.lastIndexOf('.');
  const ultimaComa = t.lastIndexOf(',');
  let normal;
  if (ultimoPunto >= 0 && ultimaComa >= 0) {
    // Los dos separadores: el último es el decimal y el otro marca los miles.
    const [miles, decimal] = ultimaComa > ultimoPunto ? ['.', ','] : [',', '.'];
    const [entera, fraccion, ...resto] = t.split(decimal);
    if (resto.length || !new RegExp(`^\\d{1,3}(\\${miles}\\d{3})*$`).test(entera)) return NaN;
    normal = `${entera.split(miles).join('')}.${fraccion}`;
  } else if (ultimaComa >= 0) {
    // Solo comas: una coma es decimal («1250,50»); más de una no es un monto.
    if (t.indexOf(',') !== ultimaComa) return NaN;
    normal = t.replace(',', '.');
  } else if (ultimoPunto >= 0) {
    // Solo puntos: grupos de tres cifras son miles («1.500», «1.250.000»); si no, decimal.
    if (/^\d{1,3}(\.\d{3})+$/.test(t)) normal = t.split('.').join('');
    else if (t.indexOf('.') === ultimoPunto) normal = t;
    else return NaN;
  } else {
    normal = t;
  }
  const valor = Number(normal);
  return Number.isFinite(valor) ? valor : NaN;
}
