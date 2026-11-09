/* MobiAire Materno — app móvil (rediseño).
   Reutiliza los MISMOS endpoints del backend (no se cambian):
     /api/waqi/estaciones?semaforo=1 · /api/zona/<id> · /api/zonas/asociacion · /api/zonas
   Privacidad: sin localStorage ni cookies; la zona vive en el hash de la URL;
   el GPS se calcula en el navegador y no se envía ni se guarda. */
"use strict";

var DATOS = [];          // estaciones (mapa/lista)
var ZONAS_ASOC = null;   // tabla de asociación zona->estación
var RECOS = null;        // textos editables del PO
var mapa = null, marcadores = {}, mapaDibujado = false;

function $(id){ return document.getElementById(id); }
function esc(t){ var d=document.createElement("div"); d.textContent=(t==null?"":""+t); return d.innerHTML; }
function nivelClase(n){ return (n==="verde"||n==="naranja"||n==="rojo")?n:"gris"; }
function colorNivel(n){ return n==="verde"?"#2f8f54":n==="naranja"?"#c9780f":n==="rojo"?"#b3362f":"#6b7280"; }
function haversine(a,b,c,d){var R=6371,r=Math.PI/180,dla=(c-a)*r,dlo=(d-b)*r,
  s=Math.sin(dla/2)**2+Math.cos(a*r)*Math.cos(c*r)*Math.sin(dlo/2)**2;return 2*R*Math.asin(Math.sqrt(s));}

/* Texto "Actualizado hace X min" a partir de un ISO con hora de Bogotá */
function haceCuanto(iso){
  if(!iso) return "";
  var t=new Date(iso); if(isNaN(t)) return "";
  var min=Math.round((Date.now()-t.getTime())/60000);
  if(min<0) min=0;
  if(min<60) return "Actualizado hace "+min+" min";
  var h=Math.round(min/60);
  return "Actualizado hace "+h+" h";
}

/* Iconos de chip por nivel (color + icono + texto; nunca solo color) */
var ICONO_NIVEL = {
  verde:'<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3 8.5l3.2 3.2L13 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  naranja:'<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M8 2l6.5 11.5H1.5z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 6.5v3.2M8 11.6v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  rojo:'<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 4.6v4M8 10.6v.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  gris:'<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5.5 8h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
};
var ETIQUETA_NIVEL = { verde:"Aire aceptable", naranja:"Precaución", rojo:"Aire dañino hoy", gris:"Sin dato reciente" };

/* ============ Cargar textos editables del PO ============ */
function cargarRecos(){
  return fetch("/recomendaciones.json").then(function(r){return r.ok?r.json():null;})
    .then(function(j){ RECOS=j; }).catch(function(){ RECOS=null; });
}
function recoDe(nivel){
  var n = nivelClase(nivel);
  if(RECOS && RECOS.niveles && RECOS.niveles[n]) return RECOS.niveles[n].recomendacion;
  // Respaldo mínimo si el archivo no cargó
  return n==="gris" ? "Sin dato reciente, no podemos orientarte ahora."
    : "Consulta la guía para saber qué hacer con este nivel de aire.";
}

/* ============ TARJETA PRINCIPAL (semáforo de la zona) ============ */
function pintarZona(d){
  var card=$("tarjeta-zona");
  var zonaNombre = (d && d.zona && d.zona.nombre) || "tu zona";
  $("zona-nombre").textContent = zonaNombre;
  $("franja-zona-nombre").textContent = zonaNombre;

  // Estados honestos
  if(d && d.estado==="pendiente"){
    card.className="tarjeta principal nivel-gris";
    $("zona-estacion").textContent = (d.zona&&d.zona.motivo) || "Asociación de zona pendiente.";
    setChip("gris");
    $("zona-medidas").hidden=true; $("zona-pie").hidden=true; $("zona-fuente").hidden=true;
    $("reco-txt").textContent = recoDe("gris");
    return;
  }
  if(!d || !d.semaforo || d.estado==="sin_dato_reciente"){
    card.className="tarjeta principal nivel-gris";
    $("zona-estacion").textContent = "Estación: " + ((d&&d.estacion&&d.estacion.nombre)||"—") + " · sin dato de las últimas horas.";
    setChip("gris");
    $("zona-medidas").hidden=true; $("zona-pie").hidden=true; $("zona-fuente").hidden=true;
    $("reco-txt").textContent = recoDe("gris");
    return;
  }

  var s=d.semaforo, n=nivelClase(s.nivel);
  card.className="tarjeta principal nivel-"+n;
  $("zona-estacion").textContent = "Estación: " + ((d.estacion&&d.estacion.nombre)||"—")
      + (d.zona&&d.zona.distancia_km!=null ? " · "+d.zona.distancia_km+" km" : "");
  setChip(n);

  // PM2.5 y PM10: usamos lo que la app ya expone (sub-índices del semáforo).
  // Rotulamos claramente "ICA estimado a partir de WAQI".
  var pm25 = s.pm25_estimado_ugm3!=null ? s.pm25_estimado_ugm3 : (s.aqi_pm25!=null?s.aqi_pm25:null);
  var pm10 = s.pm10_estimado_ugm3!=null ? s.pm10_estimado_ugm3 : (s.aqi_pm10!=null?s.aqi_pm10:null);
  pintarMedida("md-pm25", "PM2.5", pm25, s.pm25_estimado_ugm3!=null);
  pintarMedida("md-pm10", "PM10", pm10, s.pm10_estimado_ugm3!=null);
  $("zona-medidas").hidden=false;

  $("zona-ica").innerHTML = 'ICA <b>'+esc(s.ica)+'</b><small>estimado</small>';
  var iso = d.estacion && (d.estacion.medido_iso || d.estacion.medido_bogota);
  $("zona-actualizado").textContent = haceCuanto(iso) || (d.estacion&&d.estacion.medido_texto) || "";
  $("zona-pie").hidden=false;

  $("zona-fuente").hidden=false;
  $("zona-fuente").innerHTML = "ICA estimado a partir de WAQI (escala US-EPA → Res. 2254). "
      + "Índice WAQI de origen: "+esc(d.indice_waqi)+". Fuente: WAQI · "+esc((d.atribucion||[]).join(" · "));

  $("reco-txt").textContent = recoDe(n);
}
function setChip(n){
  var chip=$("zona-chip");
  chip.className="chip-estado nivel-"+n;
  chip.innerHTML = (ICONO_NIVEL[n]||"") + '<span id="zona-chip-txt">'+esc(ETIQUETA_NIVEL[n])+'</span>';
}
function pintarMedida(id, k, v, esUgm3){
  var el=$(id);
  if(v==null){ el.className="medida medida--na"; el.innerHTML='<div class="medida__k">'+k+'</div><div class="medida__v">N/D</div>'; return; }
  el.className="medida";
  var unidad = esUgm3 ? ' <small>µg/m³ est.</small>' : ' <small>sub-índice AQI</small>';
  el.innerHTML='<div class="medida__k">'+k+'</div><div class="medida__v">'+esc(v)+unidad+'</div>';
}

/* ============ ZONAS ============ */
function cargarZonas(){
  var sel=$("sel-zona");
  return fetch("/api/zonas/asociacion").then(function(r){return r.ok?r.json():null;}).then(function(d){
    ZONAS_ASOC=d;
    var zonas=(d&&d.zonas)||[];
    if(!zonas.length){
      return fetch("/api/zonas").then(function(r){return r.json();}).then(function(z){
        (z.zonas||[]).forEach(function(zo){ sel.add(new Option(zo.nombre, zo.id)); });
      });
    }
    zonas.forEach(function(zo){ sel.add(new Option(zo.nombre, zo.id)); });
  }).catch(function(){
    return fetch("/api/zonas").then(function(r){return r.json();}).then(function(z){
      (z.zonas||[]).forEach(function(zo){ sel.add(new Option(zo.nombre, zo.id)); });
    }).catch(function(){});
  }).finally(function(){
    var h=(location.hash||"").replace(/^#zona=/,"");
    if(h){ sel.value=h; verZona(h); }
  });
}

function verZona(id){
  $("zona-estacion").textContent = "Consultando…";
  fetch("/api/zona/"+encodeURIComponent(id)).then(function(r){
    if(r.status===503) throw {pend:true};
    if(!r.ok) throw {codigo:r.status};
    return r.json();
  }).then(function(d){ pintarZona(d); })
  .catch(function(err){
    var card=$("tarjeta-zona"); card.className="tarjeta principal nivel-gris";
    setChip("gris"); $("zona-medidas").hidden=true; $("zona-pie").hidden=true; $("zona-fuente").hidden=true;
    $("zona-estacion").textContent = err&&err.pend
      ? "No disponible ahora (falta configurar WAQI en el servidor)."
      : "No se pudo consultar la zona ahora.";
    $("reco-txt").textContent = recoDe("gris");
  });
}

/* ============ ESTACIONES (mapa + lista) ============ */
function cargarEstaciones(){
  return fetch("/api/waqi/estaciones?semaforo=1").then(function(r){
    if(!r.ok) throw new Error("waqi "+r.status); return r.json();
  }).then(function(d){
    var lista=(d.estaciones||[]).filter(function(e){return e.reciente;});
    if(!lista.length) throw new Error("vacío");
    DATOS = lista.map(function(e){
      return {uid:e.uid, nombre:e.nombre, lat:e.lat, lon:e.lon, aqi:e.aqi_waqi,
              hora:e.medido_texto||e.medido_bogota||"",
              nivel:(e.semaforo&&e.semaforo.nivel)||null, icaEst:(e.semaforo&&e.semaforo.ica), demo:false};
    });
    aplicarDemoCinta(false);
    pintarLista();
  }).catch(function(){
    DATOS=[
      {uid:"d1",nombre:"Kennedy (ej.)",lat:4.6249,lon:-74.16135,aqi:92,nivel:"verde",icaEst:88,hora:"ejemplo",demo:true},
      {uid:"d2",nombre:"Tunal (ej.)",lat:4.57619,lon:-74.13093,aqi:42,nivel:"verde",icaEst:40,hora:"ejemplo",demo:true},
      {uid:"d3",nombre:"Carvajal (ej.)",lat:4.5958,lon:-74.14855,aqi:130,nivel:"naranja",icaEst:120,hora:"ejemplo",demo:true},
      {uid:"d4",nombre:"Ejemplo Rojo",lat:4.60,lon:-74.10,aqi:165,nivel:"rojo",icaEst:170,hora:"ejemplo",demo:true}
    ];
    aplicarDemoCinta(true);
    pintarLista();
  });
}
function aplicarDemoCinta(esDemo){ var c=$("demo-cinta"); if(c) c.hidden=!esDemo; }

function pintarLista(){
  var cont=$("listado"); cont.innerHTML="";
  DATOS.forEach(function(e){
    var color = e.demo ? "#6b7280" : colorNivel(e.nivel);
    var nivelTxt = e.nivel ? (ETIQUETA_NIVEL[nivelClase(e.nivel)]+(e.icaEst!=null?" · ICA est. "+e.icaEst:"")) : "sin ICA estimado";
    var b=document.createElement("button");
    b.className="est"; b.setAttribute("aria-pressed","false"); b.dataset.uid=e.uid;
    b.innerHTML='<span class="est__p" style="background:'+color+'"></span>'+
      '<span><span class="est__n">'+esc(e.nombre)+'</span>'+
      '<span class="est__m">'+esc(nivelTxt)+' · índice WAQI '+esc(e.aqi==null?"—":e.aqi)+(e.demo?' · DATOS SIMULADOS':' · '+esc(e.hora))+'</span></span>'+
      '<span class="est__i" style="color:'+color+'">'+esc(e.aqi==null?"—":e.aqi)+'</span>';
    b.onclick=function(){ seleccionarEst(e.uid); };
    cont.appendChild(b);
  });
}
function seleccionarEst(uid){
  document.querySelectorAll(".est").forEach(function(x){ x.setAttribute("aria-pressed", x.dataset.uid==uid?"true":"false"); });
  var e=DATOS.find(function(x){return ""+x.uid===""+uid;});
  if(e && marcadores[uid] && mapa){ mapa.setView([e.lat,e.lon],12); marcadores[uid].openPopup(); }
}
function dibujarMapa(){
  if(mapaDibujado || !window.L) return;
  try{
    mapa=L.map("mapa").setView([4.63,-74.11],11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(mapa);
    DATOS.forEach(function(e){
      if(e.lat==null||e.lon==null) return;
      var color=e.demo?"#6b7280":colorNivel(e.nivel);
      var m=L.circleMarker([e.lat,e.lon],{radius:10,color:"#fff",weight:2,fillColor:color,fillOpacity:1}).addTo(mapa);
      var sem=e.nivel?('Semáforo: <b>'+esc(ETIQUETA_NIVEL[nivelClase(e.nivel)])+'</b>'+(e.icaEst!=null?' (ICA est. '+esc(e.icaEst)+')':'')):'Sin ICA estimado';
      m.bindPopup('<b>'+esc(e.nombre)+'</b><br>'+sem+'<br>índice WAQI '+esc(e.aqi)+' <em>(US-EPA, no es el ICA)</em>'+(e.demo?'<br><em>DATOS SIMULADOS</em>':''));
      m.on("click",function(){ seleccionarEst(e.uid); });
      marcadores[e.uid]=m;
    });
    mapaDibujado=true;
  }catch(err){}
}

/* ============ GUÍA ============ */
function pintarGuia(){
  var cont=$("guia-cont");
  var items=(RECOS&&RECOS.guia)||[];
  if(!items.length){ cont.innerHTML='<div class="aviso-estado">No se pudo cargar la guía.</div>'; return; }
  cont.innerHTML = items.map(function(g){
    var n=nivelClase(g.nivel);
    return '<div class="guia-item"><span class="guia-punto" style="background:'+colorNivel(n)+'"></span>'+
      '<div><h3>'+esc(g.nivel)+' <span class="rango">· '+esc(g.rango)+'</span></h3>'+
      '<p>'+esc(g.que_significa)+'</p><p><b>Qué hacer:</b> '+esc(g.que_hacer)+'</p></div></div>';
  }).join("");
}

/* ============ NAVEGACIÓN ============ */
function cambiarVista(v){
  var map={inicio:"vista-inicio",estaciones:"vista-estaciones",guia:"vista-guia",acerca:"vista-acerca"};
  Object.keys(map).forEach(function(k){ $(map[k]).hidden = (k!==v); });
  document.querySelectorAll(".nav__b").forEach(function(b){ b.setAttribute("aria-current", b.dataset.vista===v?"true":"false"); });
  if(v==="estaciones"){ setTimeout(function(){ dibujarMapa(); if(mapa) mapa.invalidateSize(); }, 60); }
  if(v==="guia"){ pintarGuia(); }
  window.scrollTo(0,0);
}

/* ============ HOJA selector de zona ============ */
function abrirHoja(){ $("hoja-fondo").hidden=false; $("hoja-zona").hidden=false; $("sel-zona").focus(); }
function cerrarHoja(){ $("hoja-fondo").hidden=true; $("hoja-zona").hidden=true; }

function usarMiUbicacion(){
  var aviso=$("zona-ubic-aviso");
  if(!navigator.geolocation){ aviso.textContent="Tu navegador no permite geolocalización; elige la zona manualmente."; return; }
  aviso.textContent="Pidiendo ubicación… (si la niegas, elige la zona manualmente).";
  navigator.geolocation.getCurrentPosition(function(pos){
    var la=pos.coords.latitude, lo=pos.coords.longitude;
    if(!ZONAS_ASOC||!ZONAS_ASOC.zonas){ aviso.textContent="Aún no hay asociación de zonas; elige manualmente."; return; }
    var mejor=null,dmin=1e9;
    ZONAS_ASOC.zonas.forEach(function(z){ if(z.estado!=="ok"||!z.estacion)return; var d=haversine(la,lo,z.estacion.lat,z.estacion.lon); if(d<dmin){dmin=d;mejor=z;} });
    if(mejor){
      $("sel-zona").value=mejor.id; location.hash="zona="+mejor.id; verZona(mejor.id);
      aviso.textContent="Zona sugerida por cercanía: "+mejor.nombre+". Tu ubicación no se envió ni se guardó.";
    } else { aviso.textContent="No hay zonas asociadas todavía. Elige manualmente."; }
  }, function(){ aviso.textContent="Permiso denegado. Elige la zona manualmente (la app sigue funcionando)."; });
}

/* ============ ARRANQUE ============ */
function init(){
  document.querySelectorAll(".nav__b").forEach(function(b){ b.onclick=function(){ cambiarVista(b.dataset.vista); }; });
  $("btn-busca-zona").onclick=abrirHoja;
  $("btn-otra-zona").onclick=abrirHoja;
  $("btn-cerrar-hoja").onclick=cerrarHoja;
  $("hoja-fondo").onclick=cerrarHoja;
  $("btn-mi-ubic").onclick=usarMiUbicacion;
  $("btn-ver-mapa").onclick=function(){ cambiarVista("estaciones"); };
  $("btn-expandir").onclick=function(){
    var m=$("mapa"); m.classList.toggle("expandido");
    $("btn-expandir").textContent = m.classList.contains("expandido")?"Reducir mapa":"Expandir mapa";
    if(mapa) setTimeout(function(){ mapa.invalidateSize(); },60);
  };
  $("sel-zona").onchange=function(){
    var id=this.value;
    if(id){ location.hash="zona="+id; verZona(id); }
    else { location.hash=""; }
  };
  window.addEventListener("hashchange", function(){
    var h=(location.hash||"").replace(/^#zona=/,"");
    if(h){ $("sel-zona").value=h; verZona(h); }
  });

  cargarRecos().then(function(){
    cargarZonas();
    cargarEstaciones();
  });
  iniciarPWA();
}
document.addEventListener("DOMContentLoaded", init);

/* ============ PWA ============ */
function iniciarPWA(){
  if("serviceWorker" in navigator){
    window.addEventListener("load",function(){ navigator.serviceWorker.register("/service-worker.js").catch(function(){}); });
  }
  var prompt=null;
  var btn=document.createElement("button");  // botón instalar flotante discreto
  btn.textContent="⤓ Instalar"; btn.className="btn-sec"; btn.hidden=true;
  btn.style.cssText="position:fixed;right:12px;bottom:78px;z-index:45;min-height:40px;box-shadow:var(--sombra)";
  document.body.appendChild(btn);
  window.addEventListener("beforeinstallprompt",function(e){ e.preventDefault(); prompt=e; btn.hidden=false; });
  btn.onclick=async function(){ if(!prompt)return; prompt.prompt(); try{await prompt.userChoice;}catch(_){ } prompt=null; btn.hidden=true; };
  window.addEventListener("appinstalled",function(){ btn.hidden=true; });
}
