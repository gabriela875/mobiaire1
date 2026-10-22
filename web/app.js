/* MobiAire Materno — lógica de interfaz.
   Consume la API de solo lectura del servidor. NO calcula el ICA (eso lo hace
   el motor en Python); aquí solo se PRESENTA lo que el backend entrega.
   No se guarda nada del usuario: sin cookies ni almacenamiento de datos
   personales ni historial de zonas consultadas. */

"use strict";

/* ---------- Presentación de los 3 niveles (no cálculo) ---------- */
const NIVEL = {
  verde:   { clase: "verde",   etq: "Verde",   titulo: "Aire aceptable",
             desc: "La calidad del aire es satisfactoria o aceptable para la mayoría de las personas." },
  naranja: { clase: "naranja", etq: "Naranja", titulo: "Dañino a grupos sensibles",
             desc: "Las personas gestantes y otros grupos sensibles deberían limitar los esfuerzos prolongados al aire libre." },
  rojo:    { clase: "rojo",    etq: "Rojo",    titulo: "Dañino a la salud",
             desc: "Conviene evitar la exposición prolongada al aire libre y seguir las recomendaciones de salud." },
};
const GRIS = { clase: "gris", etq: "Sin dato", titulo: "Sin ICA disponible", desc: "" };

/* ---------- Iconos SVG reutilizables ---------- */
const SVG = {
  check: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  reloj: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10 5.5V10l3 2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  alerta: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 2.5l8 14H2z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 8v3.5M10 14v.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  info: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10 6v.2M10 9v5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  frasco: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M8 2h4M8.5 2v5l-4 8a1.5 1.5 0 0 0 1.4 2.2h8.2A1.5 1.5 0 0 0 19.5 15l-4-8V2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" transform="translate(-2 0)"/></svg>',
  mapa: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 2C6.7 2 4 4.7 4 8c0 4.5 6 10 6 10s6-5.5 6-10c0-3.3-2.7-6-6-6z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="10" cy="8" r="2" fill="currentColor"/></svg>',
  enchufe: '<svg viewBox="0 0 48 48" width="52" height="52" aria-hidden="true"><path d="M18 6v10M30 6v10M14 16h20v6a10 10 0 0 1-20 0zM24 32v10" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  carpeta: '<svg viewBox="0 0 48 48" width="52" height="52" aria-hidden="true"><path d="M6 12h12l4 5h20v22H6z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/></svg>',
  hoja: '<svg viewBox="0 0 48 48" width="52" height="52" aria-hidden="true"><path d="M40 8C20 8 10 20 10 36c0 2 .3 4 .8 4C26 40 40 28 40 8z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/><path d="M14 36C22 26 30 20 38 14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>',
};

/* ---------- Estado en memoria (no se persiste) ---------- */
const estado = { demo: false, vista: "estacion", seleccion: null, zonaSel: null };

const $ = (s) => document.querySelector(s);

/* ---------- Utilidades ---------- */
function fmtFecha(iso) {
  if (!iso) return "No disponible";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString("es-CO", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
function esc(t) { const d = document.createElement("div"); d.textContent = t == null ? "" : String(t); return d.innerHTML; }
function nivelDe(e) { if (!e || e.estado !== "ok" || e.nivel == null) return GRIS; return NIVEL[e.nivel] || GRIS; }

async function api(ruta) {
  const sep = ruta.includes("?") ? "&" : "?";
  const url = ruta + (estado.demo ? sep + "demo=1" : "");
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) {
    let msg = "El servidor respondió " + r.status;
    try { const j = await r.json(); if (j.error) msg = j.error; } catch (_) {}
    const e = new Error(msg); e.codigo = r.status; throw e;
  }
  return r.json();
}

/* ---------- Estados de pantalla ---------- */
function bloqueEstado({ icono, titulo, texto, tipo = "" }) {
  return `<div class="estado ${tipo}"><div class="estado__icono">${icono}</div>
    <h2 class="estado__titulo">${esc(titulo)}</h2><p class="estado__texto">${texto}</p></div>`;
}
const CARGANDO = `<div class="estado"><div class="puntos" aria-hidden="true"><span></span><span></span><span></span></div>
  <h2 class="estado__titulo">Cargando información…</h2>
  <p class="estado__texto">Leyendo los resultados guardados por el sistema. No se recalcula nada.</p></div>`;

function bloqueError(e) {
  if (e.codigo === 503) return bloqueEstado({ tipo: "estado--error", icono: SVG.carpeta, titulo: "Datos no disponibles",
    texto: esc(e.message) + " Verifica que el sistema de ingesta haya generado los resultados." });
  if (e.codigo === 404) return bloqueEstado({ icono: SVG.carpeta, titulo: "No encontrado", texto: esc(e.message) });
  return bloqueEstado({ tipo: "estado--error", icono: SVG.enchufe, titulo: "Error de conexión",
    texto: "No se pudo contactar al servidor. Revisa que el servidor de MobiAire esté en ejecución e inténtalo de nuevo." });
}

/* ---------- Avisos ---------- */
function avisoContexto(d) {
  if (d.modo === "demo") return `<div class="aviso aviso--demo">${SVG.frasco}
    <span><strong>DEMO — DATOS SIMULADOS.</strong> Valores sintéticos para probar la interfaz; <strong>no son mediciones reales</strong>.</span></div>`;
  if (d.datos_historicos) return `<div class="aviso aviso--historico">${SVG.reloj}
    <span><strong>Datos históricos.</strong> ${esc(d.aviso || "La fuente no es en tiempo real.")} Lo mostrado <strong>no refleja la calidad del aire actual</strong>.</span></div>`;
  return "";
}
const AVISO_MEDICO = `<div class="aviso aviso--info">${SVG.info}
  <span>Información orientativa sobre la calidad del aire. <strong>No es un diagnóstico médico</strong>; ante dudas de salud consulta a tu profesional.</span></div>`;

/* ---------- SEMÁFORO (principal) ---------- */
function vistaSemaforo(d, id, e) {
  const n = nivelDe(e);
  const insuf = e.estado !== "ok";
  const pm = (k, v, ica) => {
    const na = v == null;
    return `<div class="pm ${na ? "pm--na" : ""}"><p class="pm__k">${k} · prom. 24 h</p>
      <p class="pm__v">${na ? "No disponible" : esc(v) + ' <small>µg/m³</small>'}</p>
      <p class="pm__ica">${na ? "Sin medición suficiente" : (ica != null ? "ICA " + esc(ica) : "")}</p></div>`;
  };
  const luces = ["verde", "naranja", "rojo"].map((k) =>
    `<span class="luces__p ${(!insuf && e.nivel === k) ? "on " + k[0] : ""}"></span>`).join("");

  const indicador = insuf
    ? `<div class="disco nivel-gris"><div><div class="disco__ica">—</div><div class="disco__escala">SIN ICA</div></div></div>
       <div class="sem__clasif"><span class="etiqueta-nivel nivel-gris">⚪ Datos insuficientes</span>
       <p class="sem__explica">No hay mediciones horarias suficientes para calcular el ICA de esta estación, así que no se muestra un valor para no confundir.</p></div>`
    : `<div class="disco nivel-${n.clase}"><div><div class="disco__ica">${esc(e.ica)}</div><div class="disco__escala">ICA 0–500</div></div></div>
       <div class="sem__clasif">
         <span class="etiqueta-nivel nivel-${n.clase}">${n.etq} · ${esc(n.titulo)}</span>
         <p class="sem__explica">${esc(n.desc)}</p>
         <div class="luces" role="img" aria-label="Semáforo en nivel ${esc(e.nivel)}">${luces}<span class="luces__t">Nivel ${esc(e.nivel)}</span></div>
       </div>`;

  const insufAviso = insuf
    ? `<div class="aviso aviso--insuf">${SVG.alerta}<span><strong>Datos insuficientes.</strong>
       Esta estación no reunió el mínimo de mediciones horarias (PM2.5: ${esc(e.datos_pm25)} · PM10: ${esc(e.datos_pm10)} datos).</span></div>`
    : "";

  const volver = estado.seleccion ? `<button class="sem__volver" id="btn-volver">← Ver otra estación</button>` : "";

  return `<article class="sem">
    <div class="sem__cabe">${volver}
      <h2 class="sem__estacion">${esc(e.estacion)}</h2>
      <p class="sem__ubic">${esc(e.municipio || "")}${e.autoridad ? " · " + esc(e.autoridad) : ""}</p>
    </div>
    <div class="sem__indicador">${indicador}</div>
    <div class="sem__pm">${pm("PM2.5", e.pm25_24h, e.ica_pm25)}${pm("PM10", e.pm10_24h, e.ica_pm10)}</div>
    <div class="sem__fechas">
      <div><p class="fecha__k">Fecha de las mediciones</p><p class="fecha__v">${fmtFecha(e.ultima_medicion)}${e.desactualizado ? " · ⚠️ desactualizado" : ""}</p></div>
      <div><p class="fecha__k">Última sincronización</p><p class="fecha__v">${fmtFecha(d.generado_en)}</p></div>
      <div><p class="fecha__k">Consulta actual</p><p class="fecha__v">${fmtFecha(d.consultado_en)}</p></div>
    </div>
    <div class="avisos">${insufAviso}${avisoContexto(d)}${AVISO_MEDICO}</div>
  </article>`;
}

function idDestacado(d) {
  if (estado.seleccion && d.estaciones[estado.seleccion]) return estado.seleccion;
  const ids = Object.keys(d.estaciones);
  const cb = ids.find((k) => k.includes("ciudad_bolivar"));
  if (cb) return cb;
  return ids.find((k) => d.estaciones[k].estado === "ok") || ids[0];
}

async function renderSemaforo() {
  const dest = $("#semaforo-destino");
  dest.innerHTML = CARGANDO;
  try {
    const d = await api("/api/estaciones");
    const ids = Object.keys(d.estaciones || {});
    if (!ids.length) { dest.innerHTML = bloqueEstado({ icono: SVG.carpeta, titulo: "Información no disponible", texto: "El sistema no tiene estaciones para mostrar en este momento." }); return; }
    const id = idDestacado(d);
    dest.innerHTML = vistaSemaforo(d, id, d.estaciones[id]);
    const bv = $("#btn-volver");
    if (bv) bv.onclick = () => { estado.seleccion = null; cambiarVista("estaciones"); };
  } catch (e) { dest.innerHTML = bloqueError(e); }
}

/* ---------- ESTACIONES ---------- */
async function renderEstaciones() {
  const dest = $("#lista-estaciones");
  dest.innerHTML = CARGANDO;
  try {
    const d = await api("/api/estaciones");
    const ids = Object.keys(d.estaciones || {});
    if (!ids.length) { dest.innerHTML = bloqueEstado({ icono: SVG.carpeta, titulo: "Sin estaciones", texto: "No hay estaciones para mostrar." }); return; }
    ids.sort((a, b) => (d.estaciones[b].ica ?? -1) - (d.estaciones[a].ica ?? -1));
    dest.innerHTML = ids.map((id) => {
      const e = d.estaciones[id], n = nivelDe(e), insuf = e.estado !== "ok";
      return `<button class="est" data-id="${esc(id)}">
        <span class="est__punto nivel-${insuf ? "gris" : n.clase}" aria-hidden="true"></span>
        <span><span class="est__nombre">${esc(e.estacion)}</span>
          <span class="est__meta">PM2.5 ${e.pm25_24h == null ? "N/D" : esc(e.pm25_24h)} · PM10 ${e.pm10_24h == null ? "N/D" : esc(e.pm10_24h)} µg/m³ · ${fmtFecha(e.ultima_medicion)}</span></span>
        <span class="est__der"><span class="est__ica nivel-${insuf ? "gris" : n.clase}">${insuf ? "—" : esc(e.ica)}</span>
          <span class="est__nivel">${insuf ? "sin ICA" : n.etq}</span></span>
      </button>`;
    }).join("");
    dest.querySelectorAll(".est").forEach((b) => { b.onclick = () => { estado.seleccion = b.getAttribute("data-id"); cambiarVista("estacion"); }; });
  } catch (e) { dest.innerHTML = bloqueError(e); }
}

/* ---------- ZONAS (Sprint 2) ---------- */
let ZONAS_CACHE = null;

async function renderZonas() {
  const dest = $("#zonas-destino");
  dest.innerHTML = CARGANDO;
  try {
    const z = await api("/api/zonas");
    ZONAS_CACHE = z;
    const lista = z.zonas || [];
    const chips = lista.map((zo) => `<button class="zona-chip" data-id="${esc(zo.id)}" aria-pressed="false">
      <span class="zona-chip__n">${esc(zo.nombre)}</span>
      <span class="zona-chip__c">${esc(zo.caracter || "UPZ")}</span></button>`).join("");

    dest.innerHTML = `
      <p class="seccion-intro" style="margin-bottom:14px">${esc(z.descripcion || "")}</p>
      <div class="zonas-grid" role="group" aria-label="Selecciona una zona">${chips}</div>
      <div id="zona-panel"></div>
      <div class="pendiente">${SVG.alerta}
        <div><strong>Asociación zona ↔ estación: pendiente</strong>
        ${esc(z.nota_pendiente || "La vinculación geográfica verificable aún no está disponible.")}</div></div>`;

    dest.querySelectorAll(".zona-chip").forEach((c) => { c.onclick = () => seleccionarZona(c.getAttribute("data-id")); });
    if (estado.zonaSel) seleccionarZona(estado.zonaSel, true);
  } catch (e) { dest.innerHTML = bloqueError(e); }
}

function seleccionarZona(id, silencioso) {
  estado.zonaSel = id;
  document.querySelectorAll(".zona-chip").forEach((c) =>
    c.setAttribute("aria-pressed", c.getAttribute("data-id") === id ? "true" : "false"));
  const zona = (ZONAS_CACHE.zonas || []).find((z) => z.id === id);
  const panel = $("#zona-panel");
  if (!zona || !panel) return;
  panel.innerHTML = `<div class="zona-panel">
    <span class="zona-panel__etq">UPZ ${zona.codigo_sdp ? "· Cód. " + esc(zona.codigo_sdp) : ""} · ${esc(zona.caracter || "zona")}</span>
    <h3 class="zona-panel__n" style="margin-top:8px">${esc(zona.nombre)}</h3>
    <p class="zona-panel__txt">${esc(zona.resumen || "")}</p>
    <div class="aviso aviso--info" style="margin-top:14px">${SVG.mapa}
      <span>Todavía no podemos indicar cuál es la estación de monitoreo correspondiente a <strong>${esc(zona.nombre)}</strong>,
      porque falta información geográfica verificable. Mientras tanto, puedes
      <button class="enlace-interno" id="ir-estaciones">consultar las estaciones disponibles</button>.</span></div>
  </div>`;
  const b = $("#ir-estaciones");
  if (b) b.onclick = () => cambiarVista("estaciones");
  if (!silencioso) panel.scrollIntoView({ block: "nearest" });
}

/* ---------- Navegación ---------- */
function cambiarVista(v) {
  estado.vista = v;
  const map = { estacion: "#vista-estacion", estaciones: "#vista-estaciones", zonas: "#vista-zonas" };
  Object.entries(map).forEach(([k, s]) => { $(s).hidden = k !== v; });
  document.querySelectorAll(".nav__btn").forEach((t) => t.setAttribute("aria-selected", t.dataset.vista === v ? "true" : "false"));
  if (v === "estacion") renderSemaforo();
  else if (v === "estaciones") renderEstaciones();
  else if (v === "zonas") renderZonas();
}

/* ---------- Arranque ---------- */
function init() {
  document.querySelectorAll(".nav__btn").forEach((t) => { t.onclick = () => cambiarVista(t.dataset.vista); });
  $("#chk-demo").onchange = (ev) => {
    estado.demo = ev.target.checked; estado.seleccion = null;
    $("#banda-demo").hidden = !estado.demo;
    cambiarVista(estado.vista);
  };
  $("#btn-recargar").onclick = () => cambiarVista(estado.vista);
  cambiarVista("estacion");
}
document.addEventListener("DOMContentLoaded", init);
