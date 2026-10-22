/* MobiAire Materno — lógica de interfaz.
   Consume la API de solo lectura del servidor. NO calcula ICA (eso lo hace el
   motor Python); solo muestra lo que el backend entrega. No guarda nada del
   usuario (sin cookies, sin localStorage de datos personales). */

"use strict";

// --------- Configuración de niveles (presentación, no cálculo) ----------
const NIVEL = {
  verde:   { icono: "🟢", clase: "verde",   etiqueta: "Buena / Aceptable",
             desc: "Calidad del aire satisfactoria o aceptable." },
  naranja: { icono: "🟠", clase: "naranja", etiqueta: "Dañina a grupos sensibles",
             desc: "Las personas gestantes y otros grupos sensibles deben reducir la exposición prolongada al aire libre." },
  rojo:    { icono: "🔴", clase: "rojo",    etiqueta: "Dañina a la salud",
             desc: "Evita la exposición prolongada al aire libre y sigue las recomendaciones de salud." },
};
const NIVEL_GRIS = { icono: "⚪", clase: "gris", etiqueta: "Sin dato de ICA", desc: "" };

// --------- Estado de la app (en memoria, no se persiste) ----------
const estado = {
  demo: false,
  vista: "estacion",
  seleccion: null, // id de estación en detalle
};

// --------- Utilidades ----------
const $ = (sel) => document.querySelector(sel);

function fmtFecha(iso) {
  if (!iso) return "No disponible";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString("es-CO", {
    year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function esc(t) {
  const div = document.createElement("div");
  div.textContent = t == null ? "" : String(t);
  return div.innerHTML;
}

function nivelDe(est) {
  if (!est || est.estado !== "ok" || est.nivel == null) return NIVEL_GRIS;
  return NIVEL[est.nivel] || NIVEL_GRIS;
}

async function api(ruta) {
  const sep = ruta.includes("?") ? "&" : "?";
  const url = ruta + (estado.demo ? sep + "demo=1" : "");
  const resp = await fetch(url, { headers: { "Accept": "application/json" } });
  if (!resp.ok) {
    let msg = "El servidor respondió " + resp.status;
    try { const j = await resp.json(); if (j.error) msg = j.error; } catch (_) {}
    const err = new Error(msg);
    err.codigo = resp.status;
    throw err;
  }
  return resp.json();
}

// --------- Plantillas de estado (cargando / error / vacío) ----------
function estadoHTML({ icono, titulo, texto, tipo = "" }) {
  return `<div class="estado ${tipo}">
    <div class="estado__icono" aria-hidden="true">${icono}</div>
    <h2 class="estado__titulo">${esc(titulo)}</h2>
    <p class="estado__texto">${texto}</p>
  </div>`;
}

const CARGANDO = `<div class="estado">
  <div aria-hidden="true"><span class="cargando-punto"></span><span class="cargando-punto"></span><span class="cargando-punto"></span></div>
  <h2 class="estado__titulo">Cargando información…</h2>
  <p class="estado__texto">Consultando los resultados más recientes guardados por el sistema.</p>
</div>`;

// --------- Avisos (histórico / demo) ----------
function avisoHistorico(datos) {
  if (datos.modo === "demo") {
    return `<div class="aviso aviso--demo"><span class="aviso__icono" aria-hidden="true">🧪</span>
      <div><strong>DEMO — DATOS SIMULADOS.</strong> Estos valores son sintéticos, sirven solo para
      probar la interfaz y <strong>no representan mediciones reales</strong>.</div></div>`;
  }
  if (datos.datos_historicos) {
    return `<div class="aviso aviso--historico"><span class="aviso__icono" aria-hidden="true">🕰️</span>
      <div><strong>Datos históricos.</strong> ${esc(datos.aviso || "La fuente no es en tiempo real.")}
      Lo mostrado <strong>no refleja la calidad del aire actual</strong>.</div></div>`;
  }
  return "";
}

const AVISO_MEDICO = `<div class="aviso aviso--info"><span class="aviso__icono" aria-hidden="true">ℹ️</span>
  <div>Información orientativa. <strong>No es un diagnóstico médico.</strong></div></div>`;

// --------- Render: semáforo principal (una estación destacada) ----------
function tarjetaSemaforo(datos, id, est) {
  const n = nivelDe(est);
  const insuf = est.estado !== "ok";
  const desactualizado = est.desactualizado;

  const pm = (nombre, valor, unidad, ica) => {
    const na = valor == null;
    return `<div class="medida ${na ? "medida--na" : ""}">
      <p class="medida__nombre">${nombre}</p>
      <p class="medida__valor">${na ? "No disponible" : esc(valor) + " <small>" + unidad + "</small>"}</p>
      ${!na && ica != null ? `<p class="medida__ica">ICA ${esc(ica)}</p>` : (na ? `<p class="medida__ica">Sin medición suficiente</p>` : "")}
    </div>`;
  };

  const luces = ["verde", "naranja", "rojo"].map((k) =>
    `<span class="luz ${(!insuf && est.nivel === k) ? "on luz-" + k : ""}"></span>`).join("");

  const cinta = insuf
    ? `<div class="semaforo__cinta nivel-gris">
         <span class="semaforo__icono" aria-hidden="true">⚪</span>
         <div><p class="semaforo__nivel">Datos insuficientes</p>
         <p class="semaforo__nivel-desc">No hay mediciones suficientes para calcular el ICA.</p></div>
       </div>`
    : `<div class="semaforo__cinta nivel-${n.clase}">
         <span class="semaforo__icono" aria-hidden="true">${n.icono}</span>
         <div class="semaforo__ica">${esc(est.ica)}<small>ICA (0–500)</small></div>
         <div><p class="semaforo__nivel">${n.icono} ${esc(n.etiqueta)}</p>
         <p class="semaforo__nivel-desc">${esc(n.desc)}</p></div>
       </div>`;

  const detalleInsuf = insuf
    ? `<div class="aviso aviso--historico"><span class="aviso__icono" aria-hidden="true">⚠️</span>
         <div><strong>Datos insuficientes.</strong> Esta estación no reunió el mínimo de mediciones
         horarias necesarias (PM2.5: ${esc(est.datos_pm25)} · PM10: ${esc(est.datos_pm10)} datos).
         No se calcula un ICA para no mostrar un valor engañoso.</div></div>`
    : "";

  return `<article class="semaforo">
    ${cinta}
    <div class="semaforo__cuerpo">
      <h2 class="semaforo__estacion">${esc(est.estacion)}</h2>
      <p class="semaforo__ubicacion">${esc(est.municipio || "")}${est.autoridad ? " · " + esc(est.autoridad) : ""}</p>

      <div class="luces" role="img" aria-label="Nivel del semáforo: ${insuf ? "sin dato" : esc(est.nivel)}">
        ${luces}<span class="luces__texto">${insuf ? "Sin dato de ICA" : "Nivel: " + esc(est.nivel)}</span>
      </div>

      <div class="medidas">
        ${pm("PM2.5 (prom. 24 h)", est.pm25_24h, "µg/m³", est.ica_pm25)}
        ${pm("PM10 (prom. 24 h)", est.pm10_24h, "µg/m³", est.ica_pm10)}
      </div>

      ${detalleInsuf}

      <dl class="datos-fecha">
        <dt>Fecha y hora de las mediciones</dt>
        <dd>${fmtFecha(est.ultima_medicion)} ${desactualizado ? '<span class="badge badge--naranja">⚠️ desactualizado</span>' : ""}</dd>
        <dt>Última sincronización del sistema</dt>
        <dd>${fmtFecha(datos.generado_en)}</dd>
        <dt>Última consulta (ahora)</dt>
        <dd>${fmtFecha(datos.consultado_en)}</dd>
      </dl>

      ${avisoHistorico(datos)}
      ${AVISO_MEDICO}
    </div>
  </article>`;
}

// --------- Elegir qué estación destacar en la pantalla principal ----------
function idDestacado(datos) {
  if (estado.seleccion && datos.estaciones[estado.seleccion]) return estado.seleccion;
  // Preferir Ciudad Bolívar (foco del proyecto); si no, la primera con ICA.
  const ids = Object.keys(datos.estaciones);
  const cb = ids.find((k) => k.includes("ciudad_bolivar"));
  if (cb) return cb;
  const conIca = ids.find((k) => datos.estaciones[k].estado === "ok");
  return conIca || ids[0];
}

async function renderSemaforo() {
  const destino = $("#semaforo-destino");
  destino.innerHTML = CARGANDO;
  try {
    const datos = await api("/api/estaciones");
    const ids = Object.keys(datos.estaciones || {});
    if (ids.length === 0) {
      destino.innerHTML = estadoHTML({
        icono: "📭", titulo: "Información no disponible",
        texto: "El sistema no tiene estaciones para mostrar en este momento.",
      });
      return;
    }
    const id = idDestacado(datos);
    let cabecera = "";
    if (estado.seleccion) {
      cabecera = `<button class="volver" id="btn-volver">← Ver otra estación</button>`;
    }
    destino.innerHTML = cabecera + tarjetaSemaforo(datos, id, datos.estaciones[id]);
    const bv = $("#btn-volver");
    if (bv) bv.onclick = () => { estado.seleccion = null; cambiarVista("estaciones"); };
  } catch (e) {
    destino.innerHTML = errorEstado(e);
  }
}

function errorEstado(e) {
  // Distingue error de conexión vs. datos no disponibles.
  if (e.codigo === 503) {
    return estadoHTML({
      tipo: "estado--error", icono: "📂", titulo: "Datos no disponibles",
      texto: esc(e.message) + " Verifica que el sistema de ingesta haya generado los resultados.",
    });
  }
  if (e.codigo === 404) {
    return estadoHTML({ icono: "🔍", titulo: "No encontrado", texto: esc(e.message) });
  }
  return estadoHTML({
    tipo: "estado--error", icono: "🔌", titulo: "Error de conexión",
    texto: "No se pudo contactar al servidor. Revisa que el servidor de MobiAire esté en ejecución e inténtalo de nuevo.",
  });
}

// --------- Render: lista de estaciones ----------
async function renderEstaciones() {
  const destino = $("#lista-estaciones");
  destino.innerHTML = CARGANDO;
  try {
    const datos = await api("/api/estaciones");
    const ids = Object.keys(datos.estaciones || {});
    if (ids.length === 0) {
      destino.innerHTML = estadoHTML({ icono: "📭", titulo: "Sin estaciones", texto: "No hay estaciones para mostrar." });
      return;
    }
    // Ordenar por ICA descendente; las insuficientes al final.
    ids.sort((a, b) => (datos.estaciones[b].ica ?? -1) - (datos.estaciones[a].ica ?? -1));
    destino.innerHTML = ids.map((id) => {
      const e = datos.estaciones[id];
      const n = nivelDe(e);
      const insuf = e.estado !== "ok";
      const badge = insuf
        ? `<span class="badge badge--gris">⚪ Datos insuficientes</span>`
        : `<span class="badge badge--${n.clase}">${n.icono} ${esc(e.nivel)}</span>`;
      return `<button class="tarjeta-est nivel-${insuf ? "gris" : n.clase}" data-id="${esc(id)}">
        <div class="tarjeta-est__cabe">
          <h3 class="tarjeta-est__nombre">${esc(e.estacion)}</h3>
          ${badge}
        </div>
        <p class="tarjeta-est__ica">${insuf ? "—" : esc(e.ica)} <small>ICA</small></p>
        <p class="tarjeta-est__pm">
          PM2.5: ${e.pm25_24h == null ? "N/D" : esc(e.pm25_24h) + " µg/m³"} ·
          PM10: ${e.pm10_24h == null ? "N/D" : esc(e.pm10_24h) + " µg/m³"}
        </p>
        <p class="tarjeta-est__fecha">Medición: ${fmtFecha(e.ultima_medicion)}${e.desactualizado ? " · ⚠️ desactualizado" : ""}</p>
      </button>`;
    }).join("");

    destino.querySelectorAll(".tarjeta-est").forEach((btn) => {
      btn.onclick = () => {
        estado.seleccion = btn.getAttribute("data-id");
        cambiarVista("estacion");
      };
    });
  } catch (e) {
    destino.innerHTML = errorEstado(e);
  }
}

// --------- Render: zonas (Sprint 2 — estructura, asociación pendiente) ----------
async function renderZonas() {
  const destino = $("#zonas-destino");
  destino.innerHTML = CARGANDO;
  try {
    const zonas = await api("/api/zonas");
    const lista = zonas.zonas || [];
    const opciones = lista.map((z) =>
      `<option value="${esc(z.id)}">${esc(z.nombre)}</option>`).join("");

    destino.innerHTML = `
      <p class="vista__ayuda">${esc(zonas.descripcion || "")}</p>
      <div class="selector-zona">
        <label for="sel-zona">Elige una zona de Ciudad Bolívar</label>
        <select id="sel-zona">
          <option value="">— Selecciona una zona —</option>
          ${opciones}
        </select>
      </div>
      <div id="zona-resultado"></div>
      <div class="pendiente">
        <strong>⏳ Asociación zona ↔ estación: pendiente</strong>
        ${esc(zonas.nota_pendiente || "La vinculación geográfica verificable aún no está disponible.")}
      </div>`;

    $("#sel-zona").onchange = (ev) => mostrarZona(ev.target.value, lista);
  } catch (e) {
    destino.innerHTML = errorEstado(e);
  }
}

async function mostrarZona(zonaId, lista) {
  const cont = $("#zona-resultado");
  if (!zonaId) { cont.innerHTML = ""; return; }
  const zona = lista.find((z) => z.id === zonaId);
  cont.innerHTML = `<div class="aviso aviso--info" style="margin-top:14px">
    <span class="aviso__icono" aria-hidden="true">📍</span>
    <div>Seleccionaste <strong>${esc(zona ? zona.nombre : zonaId)}</strong>.
    Todavía no podemos afirmar cuál es la estación más cercana porque falta información
    geográfica verificable (límites de zona y una referencia oficial de distancias).
    Mientras tanto, consulta las <strong>estaciones disponibles</strong> en la pestaña «Estaciones».</div>
  </div>`;
}

// --------- Navegación entre vistas ----------
function cambiarVista(vista) {
  estado.vista = vista;
  const vistas = { estacion: "#vista-estacion", estaciones: "#vista-estaciones", zonas: "#vista-zonas" };
  Object.entries(vistas).forEach(([k, sel]) => { $(sel).hidden = (k !== vista); });
  document.querySelectorAll(".tab").forEach((t) =>
    t.setAttribute("aria-selected", t.dataset.vista === vista ? "true" : "false"));

  if (vista === "estacion") renderSemaforo();
  else if (vista === "estaciones") renderEstaciones();
  else if (vista === "zonas") renderZonas();
}

function actualizarBandaDemo() {
  $("#banda-demo").hidden = !estado.demo;
}

// --------- Arranque ----------
function init() {
  document.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => cambiarVista(t.dataset.vista);
  });
  $("#chk-demo").onchange = (ev) => {
    estado.demo = ev.target.checked;
    estado.seleccion = null;
    actualizarBandaDemo();
    cambiarVista(estado.vista);
  };
  $("#btn-recargar").onclick = () => cambiarVista(estado.vista);
  cambiarVista("estacion");
}

document.addEventListener("DOMContentLoaded", init);
