// Página de simulación (docs/spec.md, sección 13). Sin dependencias ni compilación.
//
// Reglas que este archivo no rompe:
// - Solo habla con la API (ADR 0007): /salud, /simulacion/*, /casos.
// - La etiqueta real del lote se muestra DESPUÉS del veredicto y nunca se envía: a la API
//   solo viaja `elemento.transaccion` (función `enviarTransaccion`).
// - El sistema «señala para revisión»: nunca afirma que hubo fraude.

const NIVELES = {
  alerta_prioritaria: { nombre: 'Alerta prioritaria', corto: 'Prioritaria', marca: '--n-prio' },
  revision_recomendada: { nombre: 'Revisión recomendada', corto: 'Recomendada', marca: '--n-rec' },
  sin_alerta: { nombre: 'Sin alerta', corto: 'Sin alerta', marca: '--n-sin' },
  error_evaluacion: { nombre: 'Error de evaluación', corto: 'Error', marca: '--n-error' },
};
const ORDEN_NIVELES = ['sin_alerta', 'revision_recomendada', 'alerta_prioritaria', 'error_evaluacion'];
const ESTADOS_CASO = {
  cerrado: 'Caso cerrado sin revisión: no se señaló.',
  pendiente_revision: 'Señalada para revisión humana: queda en la bandeja.',
  revisado: 'Caso revisado.',
};
const PAISES = ['EC', 'CO', 'PE', 'US', 'ES', 'MX', 'AR', 'CL', 'BR', 'DE', 'FR', 'GB', 'CN', 'NG'];
const FILAS_HISTORIAL = 200;
const PAUSA_ETIQUETA_MS = 700;

const $ = (id) => document.getElementById(id);
const raiz = document.documentElement;
const reducirMovimiento = matchMedia('(prefers-reduced-motion: reduce)');
const esquemaOscuro = matchMedia('(prefers-color-scheme: dark)');

const numero = new Intl.NumberFormat('es-EC', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const numero3 = new Intl.NumberFormat('es-EC', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const entero = new Intl.NumberFormat('es-EC');

const estado = {
  lote: null,
  salud: null,
  sesion: crearSesion(),
  cursor: 0,
  corriendo: false,
  ocupado: false,
  temporizador: null,
  criterio: 'cualquier',
  registros: [], // un elemento por transacción evaluada, en orden de llegada
  atajos: leerPreferencia('fraude.atajos', '1') === '1',
  seleccion: null, // índice del punto seleccionado en la gráfica
  casoActual: null,
};

// --- Utilidades --------------------------------------------------------------------------

function crearSesion() {
  const azar = (globalThis.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Math.random()).slice(2);
  return 'sim-' + azar.replace(/[^A-Za-z0-9]/g, '').slice(0, 20);
}

function leerPreferencia(clave, porDefecto) {
  try { return localStorage.getItem(clave) ?? porDefecto; } catch { return porDefecto; }
}
function guardarPreferencia(clave, valor) {
  try { if (valor === null) localStorage.removeItem(clave); else localStorage.setItem(clave, valor); } catch { /* sin almacenamiento */ }
}

function el(etiqueta, atributos = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'texto') nodo.textContent = v;
    else if (k === 'clase') nodo.className = v;
    else nodo.setAttribute(k, v === true ? '' : v);
  }
  for (const hijo of hijos) if (hijo !== null && hijo !== undefined) nodo.append(hijo);
  return nodo;
}

const SVG = 'http://www.w3.org/2000/svg';
function svg(etiqueta, atributos = {}) {
  const nodo = document.createElementNS(SVG, etiqueta);
  for (const [k, v] of Object.entries(atributos)) nodo.setAttribute(k, v);
  return nodo;
}

// Forma de cada nivel: círculo, rombo, triángulo y aspa. El nivel nunca va solo en color.
function icono(nivel) {
  const s = svg('svg', { viewBox: '0 0 16 16', 'aria-hidden': 'true', focusable: 'false' });
  const comun = { fill: 'currentColor' };
  if (nivel === 'sin_alerta') s.append(svg('circle', { cx: 8, cy: 8, r: 6, fill: 'none', stroke: 'currentColor', 'stroke-width': 2.2 }));
  else if (nivel === 'revision_recomendada') s.append(svg('path', { d: 'M8 1.5 14.5 8 8 14.5 1.5 8Z', ...comun }));
  else if (nivel === 'alerta_prioritaria') s.append(svg('path', { d: 'M8 1.5 15 14H1Z', ...comun }));
  else s.append(svg('path', { d: 'M3 3l10 10M13 3 3 13', stroke: 'currentColor', 'stroke-width': 2.4, 'stroke-linecap': 'round' }));
  return s;
}

function etiquetaNivel(nivel, corto = false) {
  const info = NIVELES[nivel];
  return el('span', { clase: 'nivel', 'data-nivel': nivel }, icono(nivel), info ? (corto ? info.corto : info.nombre) : String(nivel));
}

function css(variable) {
  return getComputedStyle(raiz).getPropertyValue(variable).trim();
}

// Tamaño de letra de las gráficas: sigue a la letra de la página (el modo presentación la agranda).
function tam(px) {
  return Math.round(px * (parseFloat(getComputedStyle(raiz).fontSize) || 16) / 16);
}

function formatoMonto(valor) {
  return typeof valor === 'number' && Number.isFinite(valor) ? numero.format(valor) : 'sin monto válido';
}

function esSenalada(nivel) {
  if (estado.criterio === 'prioritaria') return nivel === 'alerta_prioritaria';
  return nivel === 'alerta_prioritaria' || nivel === 'revision_recomendada';
}

// --- Peticiones a la API -----------------------------------------------------------------

class ErrorRed extends Error {}

async function pedir(metodo, ruta, cuerpo) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      method: metodo,
      headers: cuerpo === undefined ? {} : { 'content-type': 'application/json' },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch (error) {
    throw new ErrorRed(error.message);
  }
  let datos = null;
  try { datos = await respuesta.json(); } catch { datos = null; }
  return { codigo: respuesta.status, datos };
}

function consulta(n) {
  const p = new URLSearchParams({ sesion: estado.sesion });
  if (n !== undefined && n !== null) p.set('n', String(n));
  return p.toString();
}

// Solo viaja la transacción: la etiqueta real se queda en la página.
function enviarTransaccion(transaccion, n) {
  return pedir('POST', `/simulacion/transacciones?${consulta(n)}`, transaccion);
}

// --- Estado visible ------------------------------------------------------------------------

function mostrarEstado(tipo, titulo, detalle = '') {
  const caja = $('estado');
  caja.dataset.tipo = tipo;
  $('estado-titulo').textContent = titulo;
  $('estado-detalle').textContent = detalle;
}

function actualizarMando() {
  const hay = Boolean(estado.lote && estado.lote.elementos.length);
  const fin = hay && estado.cursor >= estado.lote.elementos.length;
  const iniciar = $('boton-iniciar');
  iniciar.disabled = !hay || fin;
  iniciar.textContent = estado.corriendo ? 'Pausar' : (estado.cursor > 0 && !fin ? 'Continuar simulación' : 'Iniciar simulación');
  iniciar.setAttribute('aria-pressed', estado.corriendo ? 'true' : 'false');
  $('boton-paso').disabled = !hay || fin || estado.corriendo || estado.ocupado;
  $('boton-reiniciar').disabled = !hay || estado.cursor === 0 || estado.ocupado;
  if (hay) {
    const total = estado.lote.elementos.length;
    $('progreso').hidden = false;
    const barra = $('progreso-barra');
    barra.setAttribute('aria-valuemax', String(total));
    barra.setAttribute('aria-valuenow', String(estado.cursor));
    barra.firstElementChild.style.width = `${(100 * estado.cursor) / total}%`;
    $('progreso-texto').textContent = `${entero.format(estado.cursor)} de ${entero.format(total)} transacciones enviadas`;
  }
}

function describirLote() {
  const lote = estado.lote;
  const c = lote.conteos || {};
  const fuente = lote.fuente === 'real'
    ? 'parte de prueba del conjunto real'
    : 'muestra para pruebas: no representa el fraude real y no es reportable';
  return `${entero.format(c.total ?? lote.elementos.length)} transacciones: ${entero.format(c.original ?? 0)} originales con etiqueta, ${entero.format(c.sintetico ?? 0)} sintéticas de ubicación y ${entero.format(c.invalida ?? 0)} entradas inválidas de prueba (${fuente}).`;
}

// --- Carga inicial -------------------------------------------------------------------------

async function cargar() {
  mostrarEstado('cargando', 'Cargando el lote de demostración…');
  try {
    const [salud, lote] = await Promise.all([pedir('GET', '/salud'), pedir('GET', '/simulacion/lote')]);
    estado.salud = salud.codigo === 200 ? salud.datos : null;
    pintarSobre();
    if (lote.codigo === 200 && lote.datos && Array.isArray(lote.datos.elementos)) {
      estado.lote = lote.datos;
      mostrarEstado('listo', 'Listo para empezar.', `Lote de ${describirLote()} Pulsa Iniciar simulación.`);
    } else if (lote.codigo === 404) {
      mostrarEstado('error', 'Aún no hay lote de demostración.',
        'Ejecuta ./fraude todo en la terminal; al terminar, recarga esta página. Mientras tanto puedes probar una transacción manual.');
    } else {
      mostrarEstado('error', 'La API respondió con un error al pedir el lote.', mensajeError(lote));
    }
  } catch (error) {
    mostrarEstado('error', 'La API no responde.',
      'Comprueba los servicios con ./fraude estado. Si están detenidos, ejecuta ./fraude todo y recarga la página.');
  }
  actualizarMando();
  await refrescarBandeja();
}

function pintarSobre() {
  const p = $('sobre-modelo');
  const modelo = estado.salud && estado.salud.modelo;
  if (estado.salud) $('pie-version').textContent = `Versión ${estado.salud.version}.`;
  if (!modelo) { p.textContent = 'No se pudo leer el estado del modelo: la API no respondió.'; return; }
  if (!modelo.cargado) {
    p.textContent = `Sin modelo cargado: ${modelo.motivo || 'falta entrenar'}. Las transacciones originales terminarán en error de evaluación; las reglas siguen funcionando.`;
    return;
  }
  const fuente = modelo.fuente === 'real'
    ? 'entrenado con el conjunto real'
    : 'entrenado con la muestra para pruebas (no reportable)';
  p.textContent = `Modelo ${modelo.version}, ${fuente}. Umbrales elegidos en validación: revisión desde ${numero3.format(modelo.umbral_revision)} y prioritaria desde ${numero3.format(modelo.umbral_prioritaria)}.`;
}

// --- Simulación ------------------------------------------------------------------------------

function intervalo() { return Number($('velocidad').value); }

function iniciarOPausar() {
  if (!estado.lote) return;
  if (estado.corriendo) pausar('En pausa.');
  else {
    estado.corriendo = true;
    mostrarEstado('en-curso', 'Simulación en marcha.', 'Pulsa Pausar (o Espacio) para detenerla y revisar un caso con calma.');
    actualizarMando();
    if (!estado.ocupado) bucle();
  }
}

function pausar(titulo, detalle) {
  estado.corriendo = false;
  clearTimeout(estado.temporizador);
  const total = estado.lote ? estado.lote.elementos.length : 0;
  mostrarEstado('pausa', titulo, detalle ?? `Van ${entero.format(estado.cursor)} de ${entero.format(total)}. Pulsa Continuar simulación para seguir.`);
  actualizarMando();
}

async function bucle() {
  if (!estado.corriendo) return;
  const inicio = performance.now();
  const seguir = await enviarSiguiente();
  if (!seguir || !estado.corriendo) return;
  const espera = Math.max(0, intervalo() - (performance.now() - inicio));
  estado.temporizador = setTimeout(bucle, espera);
}

async function enviarSiguiente() {
  const lote = estado.lote;
  if (!lote || estado.ocupado) return false;
  if (estado.cursor >= lote.elementos.length) { terminarLote(); return false; }
  const elemento = lote.elementos[estado.cursor];
  estado.cursor += 1;
  estado.ocupado = true;
  actualizarMando();
  const id = elemento.transaccion && typeof elemento.transaccion.id_transaccion === 'string'
    ? elemento.transaccion.id_transaccion : 'sin identificador';
  if (estado.corriendo && intervalo() >= 1000) mostrarEstado('en-curso', `Evaluando ${id}…`);
  let seguir = true;
  try {
    const respuesta = await enviarTransaccion(elemento.transaccion, elemento.n);
    seguir = procesarRespuesta(respuesta, {
      n: elemento.n,
      tipo: elemento.tipo,
      etiqueta: elemento.etiqueta_real,
      descripcion: elemento.descripcion,
      transaccion: elemento.transaccion,
    });
  } catch (error) {
    estado.cursor -= 1; // no se evaluó: se reintentará al continuar
    seguir = false;
    pausar('La API no responde. La simulación quedó en pausa.',
      'Comprueba los servicios con ./fraude estado; si están detenidos, ejecuta ./fraude todo. Después pulsa Continuar simulación.');
    mostrarEstadoError();
  } finally {
    estado.ocupado = false;
    actualizarMando();
  }
  if (seguir && estado.cursor >= lote.elementos.length) { terminarLote(); return false; }
  return seguir;
}

function mostrarEstadoError() { $('estado').dataset.tipo = 'error'; }

function terminarLote() {
  estado.corriendo = false;
  clearTimeout(estado.temporizador);
  const pendientes = $('bandeja-lista').children.length;
  mostrarEstado('fin', 'Lote completo.',
    `Se enviaron ${entero.format(estado.cursor)} transacciones. ${pendientes ? `Quedan ${entero.format(pendientes)} casos en la bandeja de revisión.` : 'No quedan casos pendientes.'} Pulsa Reiniciar para volver a empezar.`);
  actualizarMando();
  anunciar('Lote completo.');
}

function mensajeError(respuesta) {
  const e = respuesta.datos && respuesta.datos.error;
  if (e && typeof e === 'object' && e.mensaje) return e.mensaje;
  if (typeof e === 'string') return e;
  return `Código HTTP ${respuesta.codigo}.`;
}

// Devuelve false si la simulación debe detenerse.
function procesarRespuesta(respuesta, contexto) {
  const { codigo, datos } = respuesta;
  if (codigo === 200 && datos && datos.nivel) {
    registrar(datos, contexto, null);
    return true;
  }
  if (codigo === 502 && datos && datos.caso && datos.caso.nivel) {
    registrar(datos.caso, contexto, 'n8n calculó el caso, pero la API no pudo guardarlo: no aparecerá en la bandeja.');
    pausar('El caso no se pudo registrar. La simulación quedó en pausa.',
      'n8n respondió, pero la API no guardó el caso. Comprueba ./fraude estado y pulsa Continuar simulación.');
    mostrarEstadoError();
    return false;
  }
  if (codigo === 502) {
    estado.cursor -= 1;
    pausar('n8n no responde. La simulación quedó en pausa.',
      `${mensajeError(respuesta)} Después pulsa Continuar simulación.`);
    mostrarEstadoError();
    return false;
  }
  if (codigo === 422 && datos && datos.error && datos.error.tipo === 'etiqueta_en_transaccion') {
    pausar('La transacción traía la etiqueta real y no se envió.', mensajeError(respuesta));
    mostrarEstadoError();
    return false;
  }
  pausar('Respuesta inesperada. La simulación quedó en pausa.', mensajeError(respuesta));
  mostrarEstadoError();
  return false;
}

// --- Registro y pintado de cada caso -------------------------------------------------------

function registrar(caso, contexto, aviso) {
  const modelo = caso.senales && caso.senales.modelo;
  const registro = {
    orden: estado.registros.length + 1,
    n: contexto.n,
    tipo: contexto.tipo,
    etiqueta: contexto.etiqueta,
    descripcion: contexto.descripcion,
    id: caso.id_transaccion ?? (contexto.transaccion && contexto.transaccion.id_transaccion) ?? null,
    monto: typeof caso.monto === 'number' ? caso.monto : null,
    origen: caso.origen,
    nivel: caso.nivel,
    puntuacion: modelo && modelo.evaluable && typeof modelo.puntuacion === 'number' ? modelo.puntuacion : null,
    umbralRevision: modelo && typeof modelo.umbral_revision === 'number' ? modelo.umbral_revision : null,
    umbralPrioritaria: modelo && typeof modelo.umbral_prioritaria === 'number' ? modelo.umbral_prioritaria : null,
    caso,
    aviso,
  };
  estado.registros.push(registro);
  estado.casoActual = registro;
  pintarCaso(registro);
  agregarFilaHistorial(registro);
  actualizarContadores();
  dibujarGraficas();
  if (caso.estado === 'pendiente_revision') refrescarBandeja();
}

function textoOrigen(registro) {
  if (registro.tipo === 'invalida') return `Entrada inválida de prueba: ${registro.descripcion || 'no cumple el contrato'}`;
  if (registro.origen === 'sintetico' || registro.tipo === 'sintetico' || registro.tipo === 'manual') return 'Sintético (ubicación inventada para probar la regla)';
  if (registro.origen === 'original') return 'Conjunto original (Kaggle / OpenML)';
  return 'Sin origen válido';
}

function pintarCaso(registro) {
  const caso = registro.caso;
  $('caso').removeAttribute('data-vacia');
  $('caso-vacio').hidden = true;
  $('caso-contenido').hidden = false;

  $('caso-id').textContent = registro.id ?? 'sin identificador';
  $('caso-monto').textContent = formatoMonto(registro.monto);
  $('caso-origen').textContent = textoOrigen(registro);

  const sello = $('caso-sello');
  sello.replaceChildren(icono(caso.nivel), document.createTextNode(NIVELES[caso.nivel]?.nombre ?? caso.nivel));
  sello.dataset.nivel = caso.nivel;
  sello.removeAttribute('data-estampar');
  if (!reducirMovimiento.matches && intervalo() >= 500) {
    void sello.offsetWidth; // reinicia la animación
    sello.setAttribute('data-estampar', '');
  }
  const textoEstado = caso.nivel === 'error_evaluacion'
    ? 'La evaluación falló: el caso queda pendiente de revisión humana, nunca sin alerta.'
    : (ESTADOS_CASO[caso.estado] ?? '');
  const estadoTexto = [textoEstado, registro.aviso ?? ''].filter(Boolean).join(' ');
  $('caso-estado').textContent = estadoTexto;

  const lista = $('caso-razones');
  lista.replaceChildren();
  const razones = Array.isArray(caso.razones) && caso.razones.length ? caso.razones : ['Ninguna regla se activó y la puntuación no superó el umbral de revisión.'];
  for (const r of razones) lista.append(el('li', { texto: r }));
  $('caso-explicacion').textContent = caso.explicacion && caso.explicacion.texto
    ? `${caso.explicacion.texto} (explicación por ${caso.explicacion.origen === 'llm' ? 'modelo de lenguaje' : 'plantilla'})` : '';

  pintarPista(registro);
  pintarPesos(caso);
  pintarRevisionActual(registro);

  // Primero el veredicto; la etiqueta real llega después y aparte.
  const etiqueta = $('caso-etiqueta');
  etiqueta.replaceChildren();
  etiqueta.removeAttribute('data-revelar');
  const espera = Math.min(PAUSA_ETIQUETA_MS, Math.max(0, intervalo() / 2));
  const mostrarla = () => {
    if (estado.casoActual !== registro) return;
    etiqueta.replaceChildren(...contenidoEtiqueta(registro));
    if (!reducirMovimiento.matches && espera > 0) etiqueta.setAttribute('data-revelar', '');
    anunciarCaso(registro);
  };
  if (espera > 0) setTimeout(mostrarla, espera); else mostrarla();
}

function resultado(registro) {
  if (registro.etiqueta !== 0 && registro.etiqueta !== 1) return null;
  if (registro.nivel === 'error_evaluacion') return { texto: 'Sin veredicto: error de evaluación', coincide: null, celda: null };
  const senalada = esSenalada(registro.nivel);
  if (registro.etiqueta === 1) return senalada
    ? { texto: 'Fraude señalado', coincide: true, celda: 'vp' }
    : { texto: 'Fraude no señalado', coincide: false, celda: 'fn' };
  return senalada
    ? { texto: 'Falsa alarma', coincide: false, celda: 'fp' }
    : { texto: 'Legítima sin alerta', coincide: true, celda: 'vn' };
}

function textoEtiqueta(registro) {
  if (registro.etiqueta === 1) return 'fraude';
  if (registro.etiqueta === 0) return 'legítima';
  if (registro.tipo === 'invalida') return 'no aplica (entrada inválida)';
  return 'sin etiqueta real (sintética)';
}

function contenidoEtiqueta(registro) {
  const r = resultado(registro);
  const linea = el('p', { clase: 'etiqueta__linea' }, `Etiqueta real del conjunto: ${textoEtiqueta(registro)}`);
  const nodos = [linea];
  if (r) {
    nodos.push(el('p', { clase: 'etiqueta__resultado', 'data-coincide': r.coincide === null ? 'na' : (r.coincide ? 'si' : 'no'), texto: `${r.texto}. ${r.coincide === null ? '' : (r.coincide ? 'Coincide con la etiqueta.' : 'No coincide con la etiqueta.')}`.trim() }));
  } else {
    nodos.push(el('p', { clase: 'nota', texto: registro.tipo === 'invalida'
      ? 'Comprueba que una entrada que no cumple el contrato queda como error de evaluación y pendiente de revisión.'
      : 'Las sintéticas solo comprueban que la regla de ubicación se activa cuando debe: no cuentan en la matriz.' }));
  }
  return nodos;
}

function anunciar(texto) {
  const region = $('anuncio');
  region.textContent = '';
  setTimeout(() => { region.textContent = texto; }, 30);
}

function anunciarCaso(registro) {
  // A velocidad alta solo se anuncian las alertas, para no saturar al lector de pantalla.
  if (estado.corriendo && intervalo() < 1000 && !esSenalada(registro.nivel)) return;
  const r = resultado(registro);
  anunciar(`${registro.id ?? 'Transacción'}: ${NIVELES[registro.nivel]?.nombre ?? registro.nivel}. Etiqueta real: ${textoEtiqueta(registro)}.${r ? ' ' + r.texto + '.' : ''}`);
}

function dominioPuntuacion() {
  let min = Infinity; let max = -Infinity;
  for (const r of estado.registros) {
    for (const v of [r.puntuacion, r.umbralRevision, r.umbralPrioritaria]) {
      if (typeof v === 'number') { min = Math.min(min, v); max = Math.max(max, v); }
    }
  }
  const umbrales = estado.salud && estado.salud.modelo;
  if (umbrales && umbrales.cargado) {
    min = Math.min(min, umbrales.umbral_revision); max = Math.max(max, umbrales.umbral_prioritaria);
  }
  if (!Number.isFinite(min)) return [0, 1];
  const margen = Math.max(0.02, (max - min) * 0.12);
  return [Math.max(0, min - margen), Math.min(1, max + margen)];
}

function pintarPista(registro) {
  const caja = $('caso-pista');
  if (registro.puntuacion === null || registro.umbralRevision === null) { caja.hidden = true; return; }
  caja.hidden = false;
  const s = $('pista-svg');
  s.replaceChildren();
  const ancho = s.getBoundingClientRect().width || 400;
  const altoPista = tam(64);
  s.setAttribute('viewBox', `0 0 ${ancho} ${altoPista}`);
  s.style.height = `${altoPista}px`;
  const [a, b] = dominioPuntuacion();
  const x = (v) => 6 + ((v - a) / (b - a)) * (ancho - 12);
  const y0 = tam(34);
  s.append(svg('line', { x1: 6, x2: ancho - 6, y1: y0, y2: y0, stroke: css('--filete-fuerte'), 'stroke-width': 2, 'stroke-linecap': 'round' }));
  s.append(svg('rect', { x: x(registro.umbralRevision), y: y0 - 3, width: Math.max(0, x(b) - x(registro.umbralRevision) - 6), height: 6, fill: css('--n-rec'), opacity: 0.25, rx: 3 }));
  s.append(svg('rect', { x: x(registro.umbralPrioritaria), y: y0 - 3, width: Math.max(0, x(b) - x(registro.umbralPrioritaria) - 6), height: 6, fill: css('--n-prio'), opacity: 0.3, rx: 3 }));
  for (const [v, texto, ancla] of [[registro.umbralRevision, 'revisión', 'end'], [registro.umbralPrioritaria, 'prioritaria', 'start']]) {
    s.append(svg('line', { x1: x(v), x2: x(v), y1: y0 - 12, y2: y0 + 12, stroke: css('--tinta-2'), 'stroke-width': 1.5 }));
    const t = svg('text', { x: x(v) + (ancla === 'end' ? -4 : 4), y: altoPista - 4, 'text-anchor': ancla, fill: css('--tinta-2'), 'font-size': tam(12) });
    t.textContent = `${texto} ${numero3.format(v)}`;
    s.append(t);
  }
  const color = css(NIVELES[registro.nivel]?.marca ?? '--n-error');
  s.append(svg('circle', { cx: x(registro.puntuacion), cy: y0, r: 8, fill: color, stroke: css('--hoja'), 'stroke-width': 2 }));
  const t = svg('text', { x: Math.min(Math.max(x(registro.puntuacion), 30), ancho - 30), y: tam(14), 'text-anchor': 'middle', fill: css('--tinta'), 'font-size': tam(13), 'font-weight': 700 });
  t.textContent = numero3.format(registro.puntuacion);
  s.append(t);
  const frente = registro.puntuacion >= registro.umbralPrioritaria
    ? 'supera el umbral prioritario'
    : registro.puntuacion >= registro.umbralRevision ? 'supera el umbral de revisión, no el prioritario' : 'queda por debajo de los dos umbrales';
  $('pista-texto').textContent = `Puntuación ${numero3.format(registro.puntuacion)}: ${frente} (revisión ${numero3.format(registro.umbralRevision)}, prioritaria ${numero3.format(registro.umbralPrioritaria)}).`;
}

function pintarPesos(caso) {
  const caja = $('caso-pesos');
  const lista = $('pesos-lista');
  const pesos = caso.senales && caso.senales.modelo && Array.isArray(caso.senales.modelo.contribuciones)
    ? caso.senales.modelo.contribuciones.filter((c) => typeof c.peso === 'number') : [];
  lista.replaceChildren();
  if (!pesos.length) { caja.hidden = true; return; }
  caja.hidden = false;
  const max = Math.max(...pesos.map((c) => Math.abs(c.peso)), 1e-9);
  for (const c of pesos) {
    const barra = el('span', { clase: 'pesos__barra', 'aria-hidden': 'true' });
    barra.style.width = `${Math.max(2, (100 * Math.max(0, c.peso)) / max)}%`;
    lista.append(el('li', {}, el('span', { texto: c.variable }), el('span', {}, barra), el('span', { clase: 'pesos__valor', texto: numero3.format(c.peso) })));
  }
}

// --- Revisión humana -------------------------------------------------------------------------

function pintarRevisionActual(registro) {
  const form = $('caso-revisar');
  const pendiente = registro.caso.estado === 'pendiente_revision' && registro.caso.id_caso;
  form.hidden = !pendiente;
  $('caso-comentario').value = '';
  $('caso-revision-resultado').textContent = '';
  for (const b of form.querySelectorAll('button')) b.disabled = false;
}

async function revisar(idCaso, decision, comentario, salida, botones) {
  const revisor = $('revisor').value.trim() || 'Revisor de la demostración';
  guardarPreferencia('fraude.revisor', revisor);
  for (const b of botones) b.disabled = true;
  salida.dataset.tipo = '';
  salida.textContent = 'Guardando la decisión…';
  let respuesta;
  try {
    respuesta = await pedir('POST', `/simulacion/revisiones?${consulta()}`, { id_caso: idCaso, decision, revisor, comentario });
  } catch {
    salida.dataset.tipo = 'error';
    salida.textContent = 'La API no responde: la decisión no se guardó. Comprueba ./fraude estado y vuelve a intentarlo.';
    for (const b of botones) b.disabled = false;
    return false;
  }
  if (respuesta.codigo === 200) {
    const texto = decision === 'sospecha_confirmada' ? 'sospecha confirmada' : 'sospecha descartada';
    salida.dataset.tipo = 'ok';
    salida.textContent = `Guardado: caso ${idCaso} revisado, ${texto}, por ${revisor}. Sale de la bandeja y quedará en revisiones.csv al reunir la evidencia.`;
    if (estado.casoActual && estado.casoActual.caso.id_caso === idCaso) {
      estado.casoActual.caso.estado = 'revisado';
      $('caso-estado').textContent = `Caso revisado: ${texto}.`;
    }
    await refrescarBandeja();
    return true;
  }
  salida.dataset.tipo = 'error';
  const motivo = {
    409: 'Este caso ya estaba revisado: la primera decisión es la que vale.',
    404: 'La API no encuentra este caso.',
    422: 'La decisión no tiene la forma esperada.',
    502: 'n8n no respondió: la decisión no se guardó.',
  }[respuesta.codigo] ?? `Respuesta inesperada (código ${respuesta.codigo}).`;
  salida.textContent = `${motivo} ${mensajeError(respuesta)}`;
  if (respuesta.codigo === 409) await refrescarBandeja();
  else for (const b of botones) b.disabled = false;
  return false;
}

async function refrescarBandeja() {
  let respuesta;
  try { respuesta = await pedir('GET', '/casos?estado=pendiente_revision&limite=50'); } catch { return; }
  if (respuesta.codigo !== 200 || !respuesta.datos || !Array.isArray(respuesta.datos.casos)) return;
  const lista = $('bandeja-lista');
  const enFoco = document.activeElement && lista.contains(document.activeElement) ? document.activeElement.closest('li')?.dataset.caso : null;
  const casos = respuesta.datos.casos;
  const actuales = new Map([...lista.children].map((li) => [li.dataset.caso, li]));
  const nuevos = [];
  for (const caso of casos) nuevos.push(actuales.get(caso.id_caso) ?? itemBandeja(caso));
  lista.replaceChildren(...nuevos);
  $('bandeja-vacia').hidden = casos.length > 0;
  if (enFoco && !casos.some((c) => c.id_caso === enFoco)) {
    (lista.querySelector('button') ?? $('revisor')).focus();
  }
}

function itemBandeja(caso) {
  const idComentario = `comentario-${caso.id_caso}`;
  const razones = el('ul', { clase: 'pendiente__razones' });
  for (const r of (caso.razones || []).slice(0, 3)) razones.append(el('li', { texto: r }));
  const comentario = el('input', { type: 'text', id: idComentario, maxlength: 500, autocomplete: 'off' });
  const salida = el('p', { clase: 'revisar__resultado', role: 'status' });
  const botones = [
    el('button', { type: 'button', clase: 'boton', texto: 'Confirmar sospecha', 'aria-describedby': `id-${caso.id_caso}` }),
    el('button', { type: 'button', clase: 'boton', texto: 'Descartar sospecha', 'aria-describedby': `id-${caso.id_caso}` }),
  ];
  botones[0].addEventListener('click', () => revisar(caso.id_caso, 'sospecha_confirmada', comentario.value.trim(), $('bandeja-resultado'), botones));
  botones[1].addEventListener('click', () => revisar(caso.id_caso, 'sospecha_descartada', comentario.value.trim(), $('bandeja-resultado'), botones));
  return el('li', { clase: 'pendiente', 'data-nivel': caso.nivel, 'data-caso': caso.id_caso },
    el('div', { clase: 'pendiente__cabeza' },
      el('span', { clase: 'pendiente__id', id: `id-${caso.id_caso}`, texto: `${caso.id_transaccion ?? 'Sin identificador'}, monto ${formatoMonto(caso.monto)}` }),
      etiquetaNivel(caso.nivel)),
    razones,
    el('div', { clase: 'pendiente__acciones' },
      el('label', { clase: 'campo', for: idComentario }, el('span', { clase: 'campo__etiqueta', texto: 'Comentario (opcional)' }), comentario),
      ...botones),
    salida);
}

// --- Contadores, matriz e historial ------------------------------------------------------------

function actualizarContadores() {
  const m = { vp: 0, fp: 0, fn: 0, vn: 0 };
  let alertas = 0; let errores = 0;
  for (const r of estado.registros) {
    if (esSenalada(r.nivel)) alertas += 1;
    if (r.nivel === 'error_evaluacion') errores += 1;
    const res = resultado(r);
    if (res && res.celda) m[res.celda] += 1;
  }
  $('c-analizadas').textContent = entero.format(estado.registros.length);
  $('c-alertas').textContent = entero.format(alertas);
  $('c-vp').textContent = entero.format(m.vp);
  $('c-fn').textContent = entero.format(m.fn);
  $('c-fp').textContent = entero.format(m.fp);
  $('c-errores').textContent = entero.format(errores);
  for (const k of Object.keys(m)) $(`m-${k}`).textContent = entero.format(m[k]);
}

function filaHistorial(registro) {
  const r = resultado(registro);
  return el('tr', { 'data-orden': registro.orden },
    el('td', { texto: entero.format(registro.orden) }),
    el('td', { texto: registro.id ?? 'sin identificador' }),
    el('td', { clase: 'num', texto: formatoMonto(registro.monto) }),
    el('td', {}, etiquetaNivel(registro.nivel, true)),
    el('td', { clase: 'num', texto: registro.puntuacion === null ? 'sin puntuación' : numero3.format(registro.puntuacion) }),
    el('td', { texto: textoEtiqueta(registro) }),
    el('td', { texto: r ? r.texto : 'no se compara' }));
}

function agregarFilaHistorial(registro) {
  const cuerpo = $('historial-cuerpo');
  cuerpo.prepend(filaHistorial(registro));
  while (cuerpo.children.length > FILAS_HISTORIAL) cuerpo.lastElementChild.remove();
  if (estado.registros.length > FILAS_HISTORIAL) {
    $('historial-nota').textContent = `Se muestran las ${FILAS_HISTORIAL} más recientes de ${entero.format(estado.registros.length)}. Todas quedan en simulacion.json al reunir la evidencia.`;
  }
}

function repintarHistorial() {
  const cuerpo = $('historial-cuerpo');
  const ultimos = estado.registros.slice(-FILAS_HISTORIAL).reverse();
  cuerpo.replaceChildren(...ultimos.map(filaHistorial));
}

// --- Gráficas en lienzo ------------------------------------------------------------------------

function prepararLienzo(lienzo) {
  const proporcion = window.devicePixelRatio || 1;
  const { width, height } = lienzo.getBoundingClientRect();
  if (lienzo.width !== Math.round(width * proporcion) || lienzo.height !== Math.round(height * proporcion)) {
    lienzo.width = Math.round(width * proporcion);
    lienzo.height = Math.round(height * proporcion);
  }
  const ctx = lienzo.getContext('2d');
  ctx.setTransform(proporcion, 0, 0, proporcion, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return { ctx, ancho: width, alto: height };
}

function marca(ctx, nivel, x, y, r, relleno, anillo) {
  ctx.beginPath();
  if (nivel === 'revision_recomendada') {
    ctx.moveTo(x, y - r - 1); ctx.lineTo(x + r + 1, y); ctx.lineTo(x, y + r + 1); ctx.lineTo(x - r - 1, y); ctx.closePath();
  } else if (nivel === 'alerta_prioritaria') {
    ctx.moveTo(x, y - r - 1.5); ctx.lineTo(x + r + 1, y + r); ctx.lineTo(x - r - 1, y + r); ctx.closePath();
  } else if (nivel === 'sin_alerta') {
    ctx.arc(x, y, r - 0.5, 0, Math.PI * 2);
  } else {
    ctx.moveTo(x - r, y - r); ctx.lineTo(x + r, y + r); ctx.moveTo(x + r, y - r); ctx.lineTo(x - r, y + r);
    ctx.lineWidth = 2.2; ctx.strokeStyle = relleno; ctx.stroke();
    return;
  }
  ctx.lineWidth = 2; ctx.strokeStyle = anillo; ctx.stroke();
  ctx.fillStyle = relleno; ctx.fill();
}

const MARGEN_BASE = { izq: 46, der: 132, arr: 12, aba: 26 };
const MARGEN = Object.defineProperties({}, Object.fromEntries(
  Object.entries(MARGEN_BASE).map(([k, v]) => [k, { get: () => tam(v) }])));

function escalaX(ancho) {
  const total = Math.max(estado.lote ? estado.lote.elementos.length : 0, estado.registros.length, 10);
  const n = Math.max(total, estado.registros.length);
  return (orden) => MARGEN.izq + ((orden - 0.5) / n) * (ancho - MARGEN.izq - MARGEN.der);
}

function dibujarGraficas() {
  dibujarPuntos();
  dibujarTiempo();
  const con = estado.registros.filter((r) => r.puntuacion !== null).length;
  const n = estado.registros.length;
  $('grafica-resumen').textContent = n
    ? `${entero.format(n)} transacciones evaluadas; ${entero.format(con)} con puntuación del modelo (las sintéticas y las inválidas no la tienen). El historial tiene los mismos datos en texto.`
    : 'Aún no hay transacciones evaluadas.';
}

function dibujarPuntos() {
  const lienzo = $('grafica-puntos');
  const { ctx, ancho, alto } = prepararLienzo(lienzo);
  const [a, b] = dominioPuntuacion();
  const y = (v) => MARGEN.arr + (1 - (v - a) / (b - a)) * (alto - MARGEN.arr - MARGEN.aba);
  const x = escalaX(ancho);
  ctx.font = `${tam(12)}px ${css('--fuente')}`;
  // Rejilla y eje.
  ctx.strokeStyle = css('--rejilla'); ctx.lineWidth = 1; ctx.fillStyle = css('--tinta-2');
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  const pasos = 4;
  for (let i = 0; i <= pasos; i += 1) {
    const v = a + ((b - a) * i) / pasos;
    const yy = Math.round(y(v)) + 0.5;
    ctx.beginPath(); ctx.moveTo(MARGEN.izq, yy); ctx.lineTo(ancho - MARGEN.der, yy); ctx.stroke();
    ctx.fillText(numero.format(v), MARGEN.izq - 6, yy);
  }
  ctx.strokeStyle = css('--eje');
  ctx.beginPath(); ctx.moveTo(MARGEN.izq, alto - MARGEN.aba + 0.5); ctx.lineTo(ancho - MARGEN.der, alto - MARGEN.aba + 0.5); ctx.stroke();
  ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  ctx.fillText('orden de llegada →', MARGEN.izq, alto - MARGEN.aba + 6);
  // Umbrales del último caso con puntuación (o los del modelo).
  const ultimo = [...estado.registros].reverse().find((r) => r.umbralRevision !== null);
  const modelo = estado.salud && estado.salud.modelo;
  const umbrales = ultimo
    ? [[ultimo.umbralRevision, 'Revisión', '--n-rec-tinta'], [ultimo.umbralPrioritaria, 'Prioritaria', '--n-prio-tinta']]
    : (modelo && modelo.cargado ? [[modelo.umbral_revision, 'Revisión', '--n-rec-tinta'], [modelo.umbral_prioritaria, 'Prioritaria', '--n-prio-tinta']] : []);
  let ultimaEtiqueta = -Infinity;
  for (const [v, texto, color] of umbrales.sort((p, q) => q[0] - p[0])) {
    const yy = Math.round(y(v)) + 0.5;
    ctx.strokeStyle = css(color); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(MARGEN.izq, yy); ctx.lineTo(ancho - MARGEN.der, yy); ctx.stroke();
    ctx.fillStyle = css(color); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    // Umbrales iguales o muy cercanos: las etiquetas se apilan sin taparse.
    const yt = Math.max(yy, ultimaEtiqueta + tam(18));
    ctx.font = `600 ${tam(12)}px ${css('--fuente')}`;
    ctx.fillText(`${texto} ${numero3.format(v)}`, ancho - MARGEN.der + 8, yt);
    ultimaEtiqueta = yt;
  }
  // Puntos.
  const anillo = css('--hoja');
  const r = estado.registros.length > 600 ? 3 : 4.5;
  for (const reg of estado.registros) {
    if (reg.puntuacion === null) continue;
    marca(ctx, reg.nivel, x(reg.orden), y(reg.puntuacion), r, css(NIVELES[reg.nivel]?.marca ?? '--n-error'), anillo);
  }
  if (estado.seleccion !== null) {
    const reg = estado.registros[estado.seleccion];
    if (reg && reg.puntuacion !== null) {
      ctx.strokeStyle = css('--tinta'); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x(reg.orden), y(reg.puntuacion), r + 5, 0, Math.PI * 2); ctx.stroke();
    }
  }
  lienzo._escala = { x, y };
}

function dibujarTiempo() {
  const lienzo = $('grafica-tiempo');
  const { ctx, ancho, alto } = prepararLienzo(lienzo);
  const x = escalaX(ancho);
  ctx.fillStyle = css('--rejilla');
  ctx.fillRect(MARGEN.izq, alto / 2 - 0.5, ancho - MARGEN.izq - MARGEN.der, 1);
  const total = Math.max(estado.lote ? estado.lote.elementos.length : 0, estado.registros.length, 10);
  const grosor = Math.max(1.5, Math.min(6, (ancho - MARGEN.izq - MARGEN.der) / total - 1));
  for (const reg of estado.registros) {
    const xx = x(reg.orden);
    if (reg.nivel === 'alerta_prioritaria') { ctx.fillStyle = css('--n-prio'); ctx.fillRect(xx - grosor / 2, 4, grosor, alto - 8); }
    else if (reg.nivel === 'revision_recomendada') { ctx.fillStyle = css('--n-rec'); ctx.fillRect(xx - grosor / 2, 10, grosor, alto - 20); }
    else if (reg.nivel === 'error_evaluacion') { ctx.fillStyle = css('--n-error'); ctx.fillRect(xx - grosor / 2, alto / 2 - 7, grosor, 14); }
    else { ctx.fillStyle = css('--n-sin'); ctx.fillRect(xx - grosor / 2, alto / 2 - 2, grosor, 4); }
  }
  ctx.fillStyle = css('--tinta-2'); ctx.font = `${tam(12)}px ${css('--fuente')}`; ctx.textBaseline = 'middle'; ctx.textAlign = 'right';
  ctx.fillText('alertas', MARGEN.izq - 6, alto / 2);
}

function pintarLeyenda() {
  const ul = $('leyenda');
  ul.replaceChildren();
  for (const nivel of ORDEN_NIVELES) {
    ul.append(el('li', {}, etiquetaNivel(nivel)));
  }
  const nota = el('li', { clase: 'nota', texto: 'Líneas horizontales: umbrales de revisión y prioritario del modelo' });
  ul.append(nota);
}

// Información emergente con ratón y con teclado (mismo contenido).
function mostrarGlobo(indice) {
  const globo = $('globo');
  const lienzo = $('grafica-puntos');
  const reg = estado.registros[indice];
  if (!reg || reg.puntuacion === null || !lienzo._escala) { globo.hidden = true; return; }
  const { x, y } = lienzo._escala;
  globo.replaceChildren(
    el('strong', { texto: numero3.format(reg.puntuacion) }),
    el('span', { texto: `${reg.id ?? ''}, monto ${formatoMonto(reg.monto)}` }), el('br'),
    etiquetaNivel(reg.nivel), el('br'),
    el('span', { texto: `Etiqueta real: ${textoEtiqueta(reg)}` }));
  globo.hidden = false;
  const caja = lienzo.getBoundingClientRect();
  const gx = x(reg.orden); const gy = y(reg.puntuacion);
  const anchoGlobo = globo.offsetWidth;
  globo.style.left = `${Math.min(Math.max(0, gx + 14), caja.width - anchoGlobo)}px`;
  globo.style.top = `${Math.max(0, gy - globo.offsetHeight - 10)}px`;
}

function indiceCercano(px, py) {
  const lienzo = $('grafica-puntos');
  if (!lienzo._escala) return null;
  const { x, y } = lienzo._escala;
  let mejor = null; let distancia = 24 * 24; // área de toque de 24 px
  estado.registros.forEach((reg, i) => {
    if (reg.puntuacion === null) return;
    const d = (x(reg.orden) - px) ** 2 + (y(reg.puntuacion) - py) ** 2;
    if (d < distancia) { distancia = d; mejor = i; }
  });
  return mejor;
}

function moverSeleccion(paso) {
  const con = estado.registros.map((r, i) => (r.puntuacion !== null ? i : null)).filter((i) => i !== null);
  if (!con.length) return;
  let pos = con.indexOf(estado.seleccion);
  if (pos === -1) pos = paso > 0 ? -1 : con.length;
  pos = Math.min(con.length - 1, Math.max(0, pos + paso));
  estado.seleccion = con[pos];
  dibujarPuntos();
  mostrarGlobo(estado.seleccion);
}

// --- Transacción manual -------------------------------------------------------------------------

function llenarPaises() {
  for (const [id, valor] of [['manual-habitual', 'EC'], ['manual-pais', 'US']]) {
    const select = $(id);
    for (const p of PAISES) select.append(el('option', { value: p, texto: p, selected: p === valor }));
  }
}

async function enviarManual(evento) {
  evento.preventDefault();
  const campo = $('manual-monto');
  const error = $('manual-error');
  const texto = campo.value.trim().replace(/\s/g, '');
  const normal = /,\d{1,2}$/.test(texto) ? texto.replace(/\./g, '').replace(',', '.') : texto.replace(/,/g, '');
  const monto = Number(normal);
  if (!texto || !Number.isFinite(monto) || monto < 0) {
    campo.setAttribute('aria-invalid', 'true');
    error.textContent = 'Escribe un monto válido: un número mayor o igual a 0.';
    campo.focus();
    return;
  }
  campo.removeAttribute('aria-invalid');
  error.textContent = '';
  const transaccion = {
    id_transaccion: `manual-${Date.now().toString(36)}`,
    origen: 'sintetico',
    monto,
    ubicacion: { pais_habitual: $('manual-habitual').value, pais_transaccion: $('manual-pais').value },
  };
  const boton = $('manual-enviar');
  boton.disabled = true;
  try {
    const respuesta = await enviarTransaccion(transaccion, null);
    if (respuesta.codigo === 200 && respuesta.datos && respuesta.datos.nivel) {
      registrar(respuesta.datos, { n: null, tipo: 'manual', etiqueta: null, descripcion: null, transaccion }, null);
      $('caso').focus();
    } else if (respuesta.codigo === 502 && respuesta.datos && respuesta.datos.caso) {
      registrar(respuesta.datos.caso, { n: null, tipo: 'manual', etiqueta: null, descripcion: null, transaccion }, 'n8n calculó el caso, pero la API no pudo guardarlo.');
      $('caso').focus();
    } else {
      error.textContent = `No se pudo evaluar: ${mensajeError(respuesta)}`;
    }
  } catch {
    error.textContent = 'La API no responde. Comprueba ./fraude estado y vuelve a intentarlo.';
  } finally {
    boton.disabled = false;
  }
}

// --- Preferencias: tema, presentación y atajos -------------------------------------------------

function temaEfectivo() {
  return raiz.dataset.tema || (esquemaOscuro.matches ? 'oscuro' : 'claro');
}

function pintarTema() {
  const preferencia = raiz.dataset.tema;
  const texto = preferencia ? `Tema ${preferencia} elegido.` : `Tema del sistema (${temaEfectivo()}).`;
  $('tema-actual').textContent = texto;
  $('boton-tema').textContent = `Tema: ${preferencia ?? 'sistema'}`;
}

function cambiarTema() {
  // sistema -> claro -> oscuro -> sistema
  const siguiente = { undefined: 'claro', claro: 'oscuro', oscuro: undefined }[raiz.dataset.tema];
  if (siguiente) raiz.dataset.tema = siguiente; else delete raiz.dataset.tema;
  guardarPreferencia('fraude.tema', siguiente ?? null);
  pintarTema();
  repintarTodo();
  anunciar(`Tema: ${siguiente ?? 'el del sistema'}.`);
}

function cambiarPresentacion() {
  const activo = !raiz.hasAttribute('data-presentacion');
  if (activo) raiz.setAttribute('data-presentacion', ''); else raiz.removeAttribute('data-presentacion');
  guardarPreferencia('fraude.presentacion', activo ? '1' : null);
  $('boton-presentacion').setAttribute('aria-pressed', String(activo));
  repintarTodo();
  anunciar(activo ? 'Modo presentación activado.' : 'Modo presentación desactivado.');
}

function repintarTodo() {
  requestAnimationFrame(() => {
    dibujarGraficas();
    if (estado.casoActual) pintarPista(estado.casoActual);
  });
}

function escribiendo(objetivo) {
  return objetivo instanceof HTMLElement && (objetivo.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(objetivo.tagName));
}

function teclado(evento) {
  if (!estado.atajos || evento.ctrlKey || evento.metaKey || evento.altKey) return;
  if (escribiendo(evento.target) || $('dialogo-atajos').open) return;
  const tecla = evento.key;
  if (tecla === ' ' && !(evento.target instanceof HTMLButtonElement) && evento.target !== $('grafica-puntos')) {
    evento.preventDefault(); iniciarOPausar();
  } else if (tecla === 's' || tecla === 'S') { if (!$('boton-paso').disabled) enviarSiguiente(); }
  else if (tecla === 't' || tecla === 'T') cambiarTema();
  else if (tecla === 'p' || tecla === 'P') cambiarPresentacion();
  else if (tecla === '?') { evento.preventDefault(); $('dialogo-atajos').showModal(); }
}

// --- Arranque ------------------------------------------------------------------------------------

function reiniciar() {
  clearTimeout(estado.temporizador);
  estado.corriendo = false;
  estado.cursor = 0;
  estado.registros = [];
  estado.seleccion = null;
  estado.casoActual = null;
  estado.sesion = crearSesion();
  $('caso').setAttribute('data-vacia', '');
  $('caso-vacio').hidden = false;
  $('caso-contenido').hidden = true;
  $('historial-cuerpo').replaceChildren();
  $('globo').hidden = true;
  actualizarContadores();
  dibujarGraficas();
  mostrarEstado('listo', 'Simulación reiniciada.', 'Los casos ya registrados siguen en la bandeja. Pulsa Iniciar simulación para enviar el lote otra vez.');
  actualizarMando();
}

function enlazar() {
  document.body.append(el('div', { id: 'anuncio', clase: 'oculto', 'aria-live': 'polite', 'aria-atomic': 'true' }));
  $('revisor').value = leerPreferencia('fraude.revisor', $('revisor').value);
  $('boton-iniciar').addEventListener('click', iniciarOPausar);
  $('boton-paso').addEventListener('click', () => enviarSiguiente());
  $('boton-reiniciar').addEventListener('click', reiniciar);
  $('boton-tema').addEventListener('click', cambiarTema);
  $('boton-presentacion').addEventListener('click', cambiarPresentacion);
  $('boton-presentacion').setAttribute('aria-pressed', String(raiz.hasAttribute('data-presentacion')));
  $('boton-atajos').addEventListener('click', () => $('dialogo-atajos').showModal());
  const casilla = $('atajos-activos');
  casilla.checked = estado.atajos;
  casilla.addEventListener('change', () => { estado.atajos = casilla.checked; guardarPreferencia('fraude.atajos', casilla.checked ? '1' : '0'); });
  $('velocidad').addEventListener('change', () => { if (estado.corriendo) { clearTimeout(estado.temporizador); if (!estado.ocupado) bucle(); } });
  for (const radio of document.querySelectorAll('input[name="criterio"]')) {
    radio.addEventListener('change', () => {
      estado.criterio = radio.value;
      actualizarContadores();
      repintarHistorial();
      if (estado.casoActual) $('caso-etiqueta').replaceChildren(...contenidoEtiqueta(estado.casoActual));
    });
  }
  $('caso-revisar').addEventListener('submit', (evento) => {
    evento.preventDefault();
    const registro = estado.casoActual;
    if (!registro || !registro.caso.id_caso) return;
    const botones = [...$('caso-revisar').querySelectorAll('button')];
    revisar(registro.caso.id_caso, evento.submitter.value, $('caso-comentario').value.trim(), $('caso-revision-resultado'), botones);
  });
  $('form-manual').addEventListener('submit', enviarManual);
  const lienzo = $('grafica-puntos');
  lienzo.addEventListener('pointermove', (e) => {
    const caja = lienzo.getBoundingClientRect();
    const i = indiceCercano(e.clientX - caja.left, e.clientY - caja.top);
    if (i === null) { $('globo').hidden = true; return; }
    mostrarGlobo(i);
  });
  lienzo.addEventListener('pointerleave', () => { if (document.activeElement !== lienzo) $('globo').hidden = true; });
  lienzo.addEventListener('keydown', (e) => {
    const pasos = { ArrowRight: 1, ArrowLeft: -1, End: 1e9, Home: -1e9 };
    if (e.key in pasos) { e.preventDefault(); moverSeleccion(pasos[e.key]); }
    if (e.key === 'Escape') { estado.seleccion = null; $('globo').hidden = true; dibujarPuntos(); }
  });
  lienzo.addEventListener('blur', () => { $('globo').hidden = true; });
  document.addEventListener('keydown', teclado);
  esquemaOscuro.addEventListener('change', () => { pintarTema(); repintarTodo(); });
  let pendiente = null;
  addEventListener('resize', () => { cancelAnimationFrame(pendiente); pendiente = requestAnimationFrame(repintarTodo); });
}

enlazar();
llenarPaises();
pintarLeyenda();
pintarTema();
dibujarGraficas();
actualizarContadores();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => dibujarGraficas());
cargar();

// Para las pruebas automáticas de la página (capturas y teclado): solo lectura.
window.__simulacion = { estado };
