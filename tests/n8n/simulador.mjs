// Simulador de flujos de n8n para las pruebas N1 (docs/planes/fase-5.md).
//
// Ejecuta el subconjunto de nodos que usan los flujos del proyecto con la semantica
// comprobada en el codigo de n8n 2.47.7 (etiqueta n8n@2.47.7):
//   - Webhook 2, Edit Fields (Set) 3.4, If 2.2, Switch 3.2, HTTP Request 4.2 y
//     Respond to Webhook 1.1.
//   - Expresiones `={{ ... }}`: el codigo termina en el primer `}}`
//     (workflow/src/extensions/expression-parser.ts); `isFinite` es `Number.isFinite`.
//   - Switch: primera regla que se cumple; `fallbackOutput: "extra"` añade la ultima salida.
//   - If y Switch con `typeValidation: "strict"`: un valor del tipo equivocado es un error.
//   - HTTP Request con `neverError`: un codigo no 2xx no es un fallo. Los reintentos
//     (`retryOnFail`, `maxTries` acotado a 2..5, `waitBetweenTries` a 0..5000) solo ocurren
//     cuando el nodo falla (red, tiempo limite). Con `onError: "continueErrorOutput"` el
//     elemento fallido sale por la segunda salida con la entrada del nodo mas `error`.
//
// No es n8n: es mas estricto (tipos exactos en Set, nada fuera del subconjunto) para que
// un flujo que pasa aqui no dependa de conversiones implicitas. La prueba definitiva es N2.
//
// Entrada (stdin, JSON): {"flujo", "cuerpo", "respuestas": {"<nodo HTTP>": [respuesta...]}}
//   respuesta: {"statusCode": n, "body": ...} o {"error": {"message": "..."}}
// Salida (stdout, JSON): {"respuesta": {"codigo", "cuerpo"} | null, "peticiones",
//   "recorrido", "esperas_ms", "fallo_flujo"}

const ADMITIDOS = {
  'n8n-nodes-base.webhook': 2,
  'n8n-nodes-base.set': 3.4,
  'n8n-nodes-base.if': 2.2,
  'n8n-nodes-base.switch': 3.2,
  'n8n-nodes-base.httpRequest': 4.2,
  'n8n-nodes-base.respondToWebhook': 1.1,
};

class ErrorFlujo extends Error {}

function leerEntrada() {
  return new Promise((resolver) => {
    let datos = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (parte) => (datos += parte));
    process.stdin.on('end', () => resolver(JSON.parse(datos)));
  });
}

// --- Expresiones ---------------------------------------------------------------------------

function partirExpresion(texto) {
  // Igual que splitExpression de n8n: abre en `{{`, cierra en el primer `}}`.
  const partes = [];
  let resto = texto;
  while (resto.length) {
    const abre = resto.indexOf('{{');
    if (abre === -1) {
      partes.push({ tipo: 'texto', valor: resto });
      break;
    }
    partes.push({ tipo: 'texto', valor: resto.slice(0, abre) });
    const cierra = resto.indexOf('}}', abre + 2);
    if (cierra === -1) throw new ErrorFlujo(`Expresion sin cerrar: ${texto}`);
    partes.push({ tipo: 'codigo', valor: resto.slice(abre + 2, cierra) });
    resto = resto.slice(cierra + 2);
  }
  return partes;
}

function evaluarCodigo(codigo, contexto) {
  const nombres = Object.keys(contexto);
  let funcion;
  try {
    funcion = new Function(...nombres, `"use strict"; return (${codigo});`);
  } catch (error) {
    throw new ErrorFlujo(`Expresion invalida «${codigo.trim()}»: ${error.message}`);
  }
  try {
    return funcion(...nombres.map((n) => contexto[n]));
  } catch (error) {
    if (error instanceof ErrorFlujo) throw error;
    throw new ErrorFlujo(`Error al evaluar «${codigo.trim()}»: ${error.message}`);
  }
}

function resolver(valor, contexto) {
  if (Array.isArray(valor)) return valor.map((v) => resolver(v, contexto));
  if (valor && typeof valor === 'object') {
    return Object.fromEntries(Object.entries(valor).map(([k, v]) => [k, resolver(v, contexto)]));
  }
  if (typeof valor !== 'string' || !valor.startsWith('=')) return valor;
  const partes = partirExpresion(valor.slice(1)).filter((p) => !(p.tipo === 'texto' && p.valor === ''));
  if (partes.length === 1 && partes[0].tipo === 'codigo') return evaluarCodigo(partes[0].valor, contexto);
  return partes
    .map((p) => {
      if (p.tipo === 'texto') return p.valor;
      const r = evaluarCodigo(p.valor, contexto);
      if (r !== null && typeof r === 'object') {
        throw new ErrorFlujo(`Objeto dentro de un texto: «${p.valor.trim()}»`);
      }
      return String(r);
    })
    .join('');
}

// --- Condiciones (filtro de If y Switch) ----------------------------------------------------

const TIPOS = { boolean: 'boolean', number: 'number', string: 'string' };

function evaluarCondiciones(filtro, contexto, nodo) {
  const opciones = filtro.options || {};
  if (opciones.typeValidation !== 'strict') {
    throw new ErrorFlujo(`${nodo}: se exige typeValidation "strict"`);
  }
  const resultados = filtro.conditions.map((c) => {
    const tipo = c.operator.type;
    if (!TIPOS[tipo]) throw new ErrorFlujo(`${nodo}: operador de tipo ${tipo} no admitido`);
    const izquierda = resolver(c.leftValue, contexto);
    if (typeof izquierda !== tipo) {
      throw new ErrorFlujo(
        `${nodo}: con validacion estricta el valor debe ser de tipo ${tipo} y es ${JSON.stringify(izquierda)}`,
      );
    }
    const derecha = resolver(c.rightValue, contexto);
    switch (`${tipo}:${c.operator.operation}`) {
      case 'boolean:true':
        return izquierda === true;
      case 'boolean:false':
        return izquierda === false;
      case 'number:equals':
      case 'string:equals':
        return izquierda === derecha;
      case 'number:notEquals':
      case 'string:notEquals':
        return izquierda !== derecha;
      default:
        throw new ErrorFlujo(`${nodo}: operacion ${tipo}:${c.operator.operation} no admitida`);
    }
  });
  if (filtro.combinator === 'and') return resultados.every(Boolean);
  if (filtro.combinator === 'or') return resultados.some(Boolean);
  throw new ErrorFlujo(`${nodo}: combinador ${filtro.combinator} no admitido`);
}

// --- Nodos -------------------------------------------------------------------------------

function comprobarTipo(nodo, nombre, tipo, valor) {
  if (valor === null) return; // Set >= 3.2 acepta null en cualquier tipo.
  const bien = {
    string: typeof valor === 'string',
    number: typeof valor === 'number' && Number.isFinite(valor),
    boolean: typeof valor === 'boolean',
    object: typeof valor === 'object' && !Array.isArray(valor),
    array: Array.isArray(valor),
  }[tipo];
  if (bien === undefined) throw new ErrorFlujo(`${nodo}: tipo ${tipo} no admitido`);
  if (!bien) {
    throw new ErrorFlujo(`${nodo}: «${nombre}» debe ser ${tipo} y es ${JSON.stringify(valor)}`);
  }
}

function ejecutarSet(nodo, elemento, contexto) {
  const salida = nodo.parameters.includeOtherFields ? { ...elemento } : {};
  for (const a of nodo.parameters.assignments.assignments) {
    if (a.name.includes('.')) {
      throw new ErrorFlujo(`${nodo.name}: «${a.name}» lleva un punto (n8n lo anidaria)`);
    }
    const valor = resolver(a.value, contexto);
    comprobarTipo(nodo.name, a.name, a.type, valor);
    salida[a.name] = valor === undefined ? null : valor;
  }
  return [[salida]];
}

function ejecutarIf(nodo, elemento, contexto) {
  const cumple = evaluarCondiciones(nodo.parameters.conditions, contexto, nodo.name);
  return cumple ? [[elemento], []] : [[], [elemento]];
}

function ejecutarSwitch(nodo, elemento, contexto) {
  const p = nodo.parameters;
  if ((p.mode || 'rules') !== 'rules') throw new ErrorFlujo(`${nodo.name}: solo modo rules`);
  const opciones = p.options || {};
  if (opciones.allMatchingOutputs) throw new ErrorFlujo(`${nodo.name}: allMatchingOutputs no admitido`);
  const reglas = p.rules.values;
  const extra = opciones.fallbackOutput === 'extra';
  const salidas = Array.from({ length: reglas.length + (extra ? 1 : 0) }, () => []);
  const indice = reglas.findIndex((r) => evaluarCondiciones(r.conditions, contexto, nodo.name));
  if (indice >= 0) salidas[indice].push(elemento);
  else if (extra) salidas[salidas.length - 1].push(elemento);
  else throw new ErrorFlujo(`${nodo.name}: ninguna regla y sin salida de respaldo (se perderia)`);
  return salidas;
}

function ejecutarHttp(nodo, elemento, contexto, estado) {
  const p = resolver(nodo.parameters, contexto);
  const respuesta = (p.options && p.options.response && p.options.response.response) || {};
  let cuerpo;
  if (p.sendBody) {
    if (p.specifyBody !== 'json') throw new ErrorFlujo(`${nodo.name}: solo specifyBody json`);
    cuerpo = typeof p.jsonBody === 'string' ? JSON.parse(p.jsonBody) : p.jsonBody;
  }
  const intentos = nodo.retryOnFail === true ? Math.min(5, Math.max(2, nodo.maxTries || 3)) : 1;
  const espera = Math.min(5000, Math.max(0, nodo.waitBetweenTries ?? 1000));
  let resultado;
  for (let intento = 1; intento <= intentos; intento++) {
    if (intento > 1) estado.esperas_ms += espera;
    estado.peticiones.push({ nodo: nodo.name, metodo: p.method, url: p.url, cuerpo, intento });
    const cola = estado.respuestas[nodo.name] || [];
    if (!cola.length) throw new ErrorFlujo(`${nodo.name}: no queda respuesta simulada`);
    const r = cola.shift();
    if (r.error) {
      resultado = { fallo: r.error };
    } else if ((r.statusCode < 200 || r.statusCode > 299) && !respuesta.neverError) {
      resultado = { fallo: { message: `${r.statusCode} - ${JSON.stringify(r.body)}`, httpCode: String(r.statusCode) } };
    } else if (respuesta.fullResponse) {
      resultado = { bien: { body: r.body, headers: {}, statusCode: r.statusCode, statusMessage: '' } };
    } else {
      resultado = { bien: r.body };
    }
    if (resultado.bien) break;
  }
  if (resultado.bien) return [[resultado.bien], []];
  if (nodo.onError === 'continueErrorOutput') return [[], [{ ...elemento, error: resultado.fallo }]];
  if (nodo.onError === 'continueRegularOutput') return [[{ error: resultado.fallo }]];
  throw Object.assign(new Error(resultado.fallo.message), { falloDelFlujo: true });
}

function ejecutarResponder(nodo, elemento, contexto, estado) {
  if (estado.respuesta) throw new ErrorFlujo(`${nodo.name}: se respondio dos veces al webhook`);
  const p = nodo.parameters;
  if (p.respondWith !== 'json') throw new ErrorFlujo(`${nodo.name}: solo respondWith json`);
  let cuerpo = resolver(p.responseBody, contexto);
  if (typeof cuerpo === 'string') cuerpo = JSON.parse(cuerpo);
  const codigo = resolver((p.options || {}).responseCode, contexto) ?? 200;
  if (!Number.isInteger(codigo) || codigo < 100 || codigo > 599) {
    throw new ErrorFlujo(`${nodo.name}: codigo de respuesta invalido ${codigo}`);
  }
  estado.respuesta = { codigo, cuerpo: JSON.parse(JSON.stringify(cuerpo)) };
  return [[elemento]];
}

// --- Ejecucion ---------------------------------------------------------------------------

function contextoPara(elemento, estado) {
  return {
    $json: elemento,
    $: (nombre) => {
      if (!estado.salidas.has(nombre)) {
        throw new ErrorFlujo(`El nodo «${nombre}» no se ha ejecutado en este recorrido`);
      }
      const salida = estado.salidas.get(nombre);
      return { first: () => ({ json: salida }), item: { json: salida } };
    },
    $execution: { id: 'simulacion' },
    isFinite: Number.isFinite,
    isNaN: Number.isNaN,
  };
}

function ejecutarNodo(flujo, nombre, elemento, estado) {
  const nodo = flujo.nodos.get(nombre);
  if (!nodo) throw new ErrorFlujo(`Conexion hacia un nodo que no existe: ${nombre}`);
  estado.recorrido.push(nombre);
  if (estado.recorrido.length > 200) throw new ErrorFlujo('Demasiados pasos: ¿hay un ciclo?');
  const contexto = contextoPara(elemento, estado);
  const ejecutores = {
    'n8n-nodes-base.set': ejecutarSet,
    'n8n-nodes-base.if': ejecutarIf,
    'n8n-nodes-base.switch': ejecutarSwitch,
    'n8n-nodes-base.httpRequest': ejecutarHttp,
    'n8n-nodes-base.respondToWebhook': ejecutarResponder,
  };
  const salidas = ejecutores[nodo.type](nodo, elemento, contexto, estado);
  // $('Nodo') solo se usa con nodos de una salida: con varias seria ambiguo.
  if (salidas.length === 1 && salidas[0].length) estado.salidas.set(nombre, salidas[0][0]);
  seguir(flujo, nombre, salidas, estado);
}

function seguir(flujo, nombre, salidas, estado) {
  const conexiones = (flujo.conexiones[nombre] || {}).main || [];
  salidas.forEach((elementos, indice) => {
    for (const elemento of elementos) {
      for (const destino of conexiones[indice] || []) ejecutarNodo(flujo, destino.node, elemento, estado);
    }
  });
}

function validarFlujo(datos) {
  const nodos = new Map();
  for (const nodo of datos.nodes) {
    if (!(nodo.type in ADMITIDOS) || ADMITIDOS[nodo.type] !== nodo.typeVersion) {
      throw new ErrorFlujo(`Nodo no admitido por el simulador: ${nodo.name} (${nodo.type} ${nodo.typeVersion})`);
    }
    if (nodos.has(nodo.name)) throw new ErrorFlujo(`Nombre de nodo repetido: ${nodo.name}`);
    nodos.set(nodo.name, nodo);
  }
  for (const [origen, tipos] of Object.entries(datos.connections || {})) {
    if (!nodos.has(origen)) throw new ErrorFlujo(`Conexion desde un nodo que no existe: ${origen}`);
    for (const salida of tipos.main || []) {
      for (const destino of salida || []) {
        if (!nodos.has(destino.node)) throw new ErrorFlujo(`Conexion hacia un nodo que no existe: ${destino.node}`);
      }
    }
  }
  const webhooks = datos.nodes.filter((n) => n.type === 'n8n-nodes-base.webhook');
  if (webhooks.length !== 1) throw new ErrorFlujo('El flujo debe tener exactamente un webhook');
  return { nodos, conexiones: datos.connections || {}, webhook: webhooks[0] };
}

async function main() {
  const entrada = await leerEntrada();
  const flujo = validarFlujo(entrada.flujo);
  const estado = {
    respuestas: structuredClone(entrada.respuestas || {}),
    peticiones: [],
    recorrido: [],
    salidas: new Map(),
    esperas_ms: 0,
    respuesta: null,
    fallo_flujo: null,
  };
  const webhook = flujo.webhook;
  const elemento = {
    headers: { 'content-type': 'application/json' },
    params: {},
    query: {},
    body: entrada.cuerpo,
    webhookUrl: `http://localhost:5678/webhook/${webhook.parameters.path}`,
    executionMode: 'production',
  };
  estado.recorrido.push(webhook.name);
  estado.salidas.set(webhook.name, elemento);
  try {
    seguir(flujo, webhook.name, [[elemento]], estado);
  } catch (error) {
    if (!error.falloDelFlujo) throw error;
    estado.fallo_flujo = error.message;
  }
  const sobrantes = Object.entries(estado.respuestas).filter(([, cola]) => cola.length);
  const { respuesta, peticiones, recorrido, esperas_ms, fallo_flujo } = estado;
  process.stdout.write(
    JSON.stringify({ respuesta, peticiones, recorrido, esperas_ms, fallo_flujo, sobrantes: Object.fromEntries(sobrantes) }),
  );
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
