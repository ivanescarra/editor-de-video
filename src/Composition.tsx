import { loadFont as cargarSerif } from "@remotion/google-fonts/InstrumentSerif";
import { loadFont as cargarMontserrat } from "@remotion/google-fonts/Montserrat";
import React from "react";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  Composition,
  Easing,
  interpolate,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const { fontFamily: SANS } = cargarMontserrat("normal", { weights: ["500", "600", "700", "800"], subsets: ["latin", "latin-ext"] });
const { fontFamily: SERIF } = cargarSerif("italic", { subsets: ["latin", "latin-ext"] });

// Todos los tiempos llegan ya en segundos del vídeo final (montar.py los convierte)
type Palabra = { texto: string; inicio: number; fin: number; resaltar?: boolean };
type Bloque = { inicio: number; fin: number; palabras: Palabra[] };
type Tarjeta = { texto: string; subtexto?: string; inicio: number; fin: number; posicion?: "arriba" | "pecho" | "centro"; y?: number };
type Sticker = { contenido: string; inicio: number; fin: number; x?: number; y?: number; giro?: number };
type Item = { texto: string; en: number; sub?: string; columna?: number };
type Escena = {
  tipo: "embudo" | "comparativa" | "flujo" | "ciclo" | "lista";
  inicio: number;
  fin: number;
  titulo?: string;
  items: Item[];
  columnas?: { texto: string; en: number; sub?: string }[]; // comparativa
  foco?: { en: number; indice: number }[]; // qué elemento se resalta a partir de cuándo
  centro?: { texto: string; en: number }; // ciclo: lo que crece en medio
};
type Estilo = {
  acento: string;
  subtitulosY: number; // 0-1 desde arriba
  subtitulosYEscena: number; // durante una escena el vídeo va abajo
  tamanoSubtitulos: number;
  mayusculas: boolean;
};

export type PropsEdicion = {
  video: string;
  duracion: number;
  ancho: number;
  alto: number;
  fps: number;
  titular?: { linea1: string; linea2?: string; inicio: number; fin: number };
  subtitulos: Bloque[];
  tarjetas: Tarjeta[];
  stickers: Sticker[];
  escenas: Escena[];
  estilo: Estilo;
};

const defecto: PropsEdicion = {
  video: "",
  duracion: 5,
  ancho: 1080,
  alto: 1920,
  fps: 30,
  subtitulos: [],
  tarjetas: [],
  stickers: [],
  escenas: [],
  estilo: { acento: "#F5C542", subtitulosY: 0.68, subtitulosYEscena: 0.88, tamanoSubtitulos: 70, mayusculas: false },
};

const calcular: CalculateMetadataFunction<PropsEdicion> = ({ props }) => ({
  durationInFrames: Math.max(1, Math.round(props.duracion * props.fps)),
  fps: props.fps,
  width: props.ancho,
  height: props.alto,
});

const sombra = "0 4px 18px rgba(0,0,0,0.55), 0 2px 4px rgba(0,0,0,0.6)";
const suave = Easing.bezier(0.22, 1, 0.36, 1); // salida suave, sin rebote
const PANEL = 0.4; // fracción de alto que ocupa el gráfico durante una escena
const FONDO = "#101113";

// 0→1 entre dos fotogramas con curva suave
const progreso = (frame: number, desde: number, dur: number) =>
  interpolate(frame, [desde, desde + dur], [0, 1], { easing: suave, extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// Entrada y salida con fundido y un pequeño desplazamiento, en fotogramas locales
const useAparicion = (dur: number, entrada = 10, salida = 8) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = progreso(frame, 0, entrada);
  const sale = 1 - progreso(frame, dur - salida, salida);
  return { entra, sale, frame, fps };
};

const Titular: React.FC<{ t: NonNullable<PropsEdicion["titular"]>; acento: string; dur: number }> = ({ t, acento, dur }) => {
  const { entra, sale, frame } = useAparicion(dur, 14, 10);
  const entra2 = progreso(frame, 6, 14);
  return (
    <AbsoluteFill style={{ padding: "150px 70px 0", opacity: sale }}>
      <div
        style={{
          fontFamily: SANS,
          fontWeight: 800,
          fontSize: 88,
          lineHeight: 1.04,
          color: "white",
          letterSpacing: -2,
          textShadow: sombra,
          transform: `translateY(${(1 - entra) * 30}px)`,
          opacity: entra,
        }}
      >
        {t.linea1}
      </div>
      {t.linea2 ? (
        <div
          style={{
            fontFamily: SERIF,
            fontStyle: "italic",
            fontSize: 100,
            lineHeight: 1.05,
            color: acento,
            textShadow: sombra,
            transform: `translateY(${(1 - entra2) * 30}px)`,
            opacity: entra2,
          }}
        >
          {t.linea2}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// Subtítulos fluidos: la frase entra con un fundido suave y cada palabra se ilumina al decirla. Sin «pop»
const Subtitulo: React.FC<{ b: Bloque; estilo: Estilo; dur: number; y: number }> = ({ b, estilo, dur, y }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const entra = progreso(frame, 0, 5);
  const sale = 1 - progreso(frame, dur - 4, 4);
  return (
    <AbsoluteFill style={{ opacity: Math.min(entra, sale) }}>
      <div
        style={{
          position: "absolute",
          top: y * height,
          left: "7%",
          width: "86%",
          textAlign: "center",
          fontFamily: SANS,
          fontWeight: 800,
          fontSize: estilo.tamanoSubtitulos,
          lineHeight: 1.12,
          letterSpacing: -1,
          textTransform: estilo.mayusculas ? "uppercase" : "none",
          transform: `translateY(${(1 - entra) * 12}px)`,
        }}
      >
        {b.palabras.map((p, i) => {
          const local = (p.inicio - b.inicio) * fps;
          const luz = progreso(frame, local - 2, 4);
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                margin: "0 0.13em",
                color: p.resaltar && luz > 0.5 ? estilo.acento : "white",
                opacity: 0.42 + 0.58 * luz,
                textShadow: sombra,
              }}
            >
              {p.texto}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const TarjetaVista: React.FC<{ t: Tarjeta; acento: string; dur: number }> = ({ t, acento, dur }) => {
  const { entra, sale } = useAparicion(dur);
  const { height } = useVideoConfig();
  const centro = t.posicion === "centro";
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: centro ? "center" : "flex-start", opacity: sale }}>
      <div
        style={{
          marginTop: centro ? 0 : height * (t.y ?? (t.posicion === "arriba" ? 0.1 : 0.46)),
          width: "78%",
          padding: "30px 38px",
          borderRadius: 30,
          background: "rgba(16,16,18,0.8)",
          border: `2px solid ${acento}`,
          boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
          transform: `translateY(${(1 - entra) * 40}px)`,
          opacity: entra,
        }}
      >
        <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 58, color: "white", lineHeight: 1.08, letterSpacing: -1 }}>{t.texto}</div>
        {t.subtexto ? (
          <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 34, color: "rgba(255,255,255,0.75)", marginTop: 10 }}>{t.subtexto}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

const StickerVista: React.FC<{ s: Sticker; acento: string; dur: number }> = ({ s, acento, dur }) => {
  const { entra, sale } = useAparicion(dur);
  const { width, height } = useVideoConfig();
  const esEmoji = [...s.contenido].length <= 2;
  return (
    <div
      style={{
        position: "absolute",
        left: (s.x ?? 0.75) * width,
        top: (s.y ?? 0.4) * height,
        transform: `translate(-50%,-50%) translateY(${(1 - entra) * 24}px) rotate(${s.giro ?? -4}deg)`,
        opacity: Math.min(entra, sale),
        fontSize: esEmoji ? 140 : 48,
        fontFamily: SANS,
        fontWeight: 800,
        color: "#111",
        background: esEmoji ? "transparent" : acento,
        padding: esEmoji ? 0 : "14px 30px",
        borderRadius: 999,
        boxShadow: esEmoji ? "none" : "0 10px 30px rgba(0,0,0,0.35)",
        whiteSpace: "nowrap",
      }}
    >
      {s.contenido}
    </div>
  );
};

// ---------- escenas explicativas ----------

type VistaEscena = { e: Escena; acento: string; frame: number; fps: number; ancho: number; alto: number };

// Aparición de un elemento a partir de su segundo (relativo al inicio de la escena)
const ap = (v: VistaEscena, en: number, dur = 12) => progreso(v.frame, (en - v.e.inicio) * v.fps, dur);

// Índice resaltado en este momento (o -1)
const enFoco = (v: VistaEscena) => {
  const t = v.e.inicio + v.frame / v.fps;
  let i = -1;
  for (const f of v.e.foco ?? []) if (t >= f.en) i = f.indice;
  return i;
};

const Caja: React.FC<{ texto: string; sub?: string; a: number; activo?: boolean; apagado?: boolean; acento: string; style?: React.CSSProperties; grande?: boolean; pequena?: boolean }> = ({
  texto,
  sub,
  a,
  activo,
  apagado,
  acento,
  style,
  grande,
  pequena,
}) => (
  <div
    style={{
      opacity: a * (apagado ? 0.4 : 1),
      transform: `translateY(${(1 - a) * 22}px)`,
      background: activo ? acento : "rgba(255,255,255,0.07)",
      border: `2px solid ${activo ? acento : "rgba(255,255,255,0.16)"}`,
      borderRadius: 26,
      padding: grande ? "26px 34px" : pequena ? "9px 18px" : "18px 26px",
      color: activo ? "#111" : "white",
      fontFamily: SANS,
      textAlign: "center",
      ...style,
    }}
  >
    <div style={{ fontWeight: pequena ? 700 : 800, fontSize: grande ? 50 : pequena ? 32 : 40, letterSpacing: -0.5, lineHeight: 1.1 }}>{texto}</div>
    {sub ? <div style={{ fontWeight: 600, fontSize: 28, opacity: 0.75, marginTop: 6 }}>{sub}</div> : null}
  </div>
);

const Flecha: React.FC<{ a: number; vertical?: boolean; largo?: number; acento: string }> = ({ a, vertical, largo = 60, acento }) => (
  <svg width={vertical ? 40 : largo} height={vertical ? largo : 40} style={{ overflow: "visible", opacity: a > 0 ? 1 : 0 }}>
    {vertical ? (
      <>
        <line x1={20} y1={0} x2={20} y2={(largo - 14) * a} stroke={acento} strokeWidth={5} strokeLinecap="round" />
        <path d={`M8 ${largo - 18} L20 ${largo - 2} L32 ${largo - 18}`} stroke={acento} strokeWidth={5} fill="none" strokeLinecap="round" opacity={a} />
      </>
    ) : (
      <>
        <line x1={0} y1={20} x2={(largo - 14) * a} y2={20} stroke={acento} strokeWidth={5} strokeLinecap="round" />
        <path d={`M${largo - 18} 8 L${largo - 2} 20 L${largo - 18} 32`} stroke={acento} strokeWidth={5} fill="none" strokeLinecap="round" opacity={a} />
      </>
    )}
  </svg>
);

const Embudo: React.FC<{ v: VistaEscena }> = ({ v }) => {
  const foco = enFoco(v);
  const n = v.e.items.length;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
      {v.e.items.map((it, i) => {
        const a = ap(v, it.en, 16);
        const ancho = 900 - i * (420 / Math.max(1, n - 1));
        const activo = foco === i;
        return (
          <div
            key={i}
            style={{
              width: ancho * (0.6 + 0.4 * a),
              height: 150,
              opacity: a * (foco >= 0 && !activo ? 0.45 : 1),
              clipPath: "polygon(0 0, 100% 0, 93% 100%, 7% 100%)",
              background: activo ? v.acento : i === 0 ? "rgba(245,197,66,0.9)" : `rgba(255,255,255,${0.16 - i * 0.03})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: SANS,
              fontWeight: 800,
              fontSize: 50,
              color: activo || (i === 0 && foco < 0) ? "#111" : "white",
              letterSpacing: -0.5,
            }}
          >
            <span style={{ opacity: 0.55, marginRight: 18, fontSize: 38 }}>{i + 1}</span>
            {it.texto}
          </div>
        );
      })}
    </div>
  );
};

const Comparativa: React.FC<{ v: VistaEscena }> = ({ v }) => {
  const cols = v.e.columnas ?? [];
  const foco = enFoco(v);
  return (
    <div style={{ display: "flex", gap: 28, width: "100%", justifyContent: "center", alignItems: "flex-start" }}>
      {cols.map((c, ci) => {
        const a = ap(v, c.en, 14);
        const ancho = Math.min(460, (1000 - 28 * (cols.length - 1)) / cols.length);
        return (
          <div key={ci} style={{ width: ancho, display: "flex", flexDirection: "column", gap: 10, opacity: foco >= 0 && foco !== ci ? 0.45 : 1 }}>
            <Caja texto={c.texto} sub={c.sub} a={a} activo={foco === ci || foco < 0} acento={v.acento} grande />
            {v.e.items
              .filter((it) => (it.columna ?? 0) === ci)
              .map((it, k) => (
                <Caja key={k} texto={it.texto} sub={it.sub} a={ap(v, it.en, 10)} acento={v.acento} pequena />
              ))}
          </div>
        );
      })}
    </div>
  );
};

// Origen → opciones → destino, de arriba abajo
const Flujo: React.FC<{ v: VistaEscena }> = ({ v }) => {
  const [origen, ...resto] = v.e.items;
  const destino = resto[resto.length - 1];
  const opciones = resto.slice(0, -1);
  const primeraOpcion = opciones.length ? opciones[0].en : destino.en;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <Caja texto={origen.texto} sub={origen.sub} a={ap(v, origen.en)} acento={v.acento} grande />
      <Flecha vertical a={ap(v, primeraOpcion - 0.3, 10)} largo={56} acento={v.acento} />
      <div style={{ display: "flex", gap: 16 }}>
        {opciones.map((o, i) => (
          <Caja key={i} texto={o.texto} sub={o.sub} a={ap(v, o.en)} acento={v.acento} />
        ))}
      </div>
      <Flecha vertical a={ap(v, destino.en - 0.3, 10)} largo={56} acento={v.acento} />
      <Caja texto={destino.texto} sub={destino.sub} a={ap(v, destino.en)} activo acento={v.acento} grande />
    </div>
  );
};

// Nodos en círculo con flechas que giran; en el centro algo que crece
const Ciclo: React.FC<{ v: VistaEscena }> = ({ v }) => {
  const n = v.e.items.length;
  const R = 255;
  const cx = 540;
  const cy = 330;
  const foco = enFoco(v);
  const ultimo = Math.max(...v.e.items.map((i) => i.en));
  const vuelta = ap(v, ultimo + 0.4, 24);
  const giro = (v.frame / v.fps) * 6 * vuelta; // las flechas empiezan a girar cuando el ciclo está completo
  const centro = v.e.centro;
  const crece = centro ? ap(v, centro.en, 30) : 0;
  return (
    <div style={{ position: "relative", width: 1080, height: 660 }}>
      <svg width={1080} height={660} style={{ position: "absolute", inset: 0 }}>
        {v.e.items.map((it, i) => {
          const a0 = ((i / n) * 360 - 90 + 16 + giro) * (Math.PI / 180);
          const a1 = (((i + 1) / n) * 360 - 90 - 16 + giro) * (Math.PI / 180);
          const p = ap(v, v.e.items[(i + 1) % n].en - 0.2, 14) * (i === n - 1 ? vuelta : 1);
          const fin = a0 + (a1 - a0) * p;
          const x0 = cx + R * Math.cos(a0);
          const y0 = cy + R * Math.sin(a0);
          const x1 = cx + R * Math.cos(fin);
          const y1 = cy + R * Math.sin(fin);
          return p > 0.01 ? (
            <path key={i} d={`M${x0} ${y0} A${R} ${R} 0 0 1 ${x1} ${y1}`} stroke={v.acento} strokeWidth={6} fill="none" strokeLinecap="round" opacity={0.85} />
          ) : null;
        })}
      </svg>
      {centro ? (
        <div
          style={{
            position: "absolute",
            left: cx,
            top: cy,
            width: 60 + 170 * crece,
            height: 60 + 170 * crece,
            transform: "translate(-50%,-50%)",
            borderRadius: "50%",
            background: "radial-gradient(circle at 35% 30%, #ffffff, #dfe7f0 60%, #b9c6d6)",
            boxShadow: "0 10px 40px rgba(255,255,255,0.18)",
            opacity: crece,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: SANS,
            fontWeight: 800,
            fontSize: 30,
            color: "#1b2330",
            textAlign: "center",
            lineHeight: 1.05,
          }}
        >
          {crece > 0.6 ? centro.texto : ""}
        </div>
      ) : null}
      {v.e.items.map((it, i) => {
        const ang = ((i / n) * 360 - 90) * (Math.PI / 180);
        return (
          <div key={i} style={{ position: "absolute", left: cx + R * Math.cos(ang), top: cy + R * Math.sin(ang), transform: "translate(-50%,-50%)" }}>
            <Caja texto={it.texto} sub={it.sub} a={ap(v, it.en)} activo={foco === i} acento={v.acento} style={{ whiteSpace: "nowrap" }} />
          </div>
        );
      })}
    </div>
  );
};

const Lista: React.FC<{ v: VistaEscena }> = ({ v }) => (
  <div style={{ display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "center", width: 960 }}>
    {v.e.items.map((it, i) => (
      <Caja key={i} texto={it.texto} sub={it.sub} a={ap(v, it.en)} acento={v.acento} />
    ))}
  </div>
);

// Cuánto se agranda cada tipo dentro del panel, y el hueco que eso ocupa por debajo
const ESCALA = { embudo: 1.15, comparativa: 1.05, flujo: 1.2, ciclo: 0.92, lista: 1.25 } as const;
const ALTO_EXTRA = { embudo: 70, comparativa: 20, flujo: 70, ciclo: -50, lista: 50 } as const;

const PanelEscena: React.FC<{ e: Escena; acento: string; dur: number }> = ({ e, acento, dur }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const sale = 1 - progreso(frame, dur - 8, 8);
  const v: VistaEscena = { e, acento, frame, fps, ancho: width, alto: height };
  const tit = progreso(frame, 4, 12);
  const Cuerpo = { embudo: Embudo, comparativa: Comparativa, flujo: Flujo, ciclo: Ciclo, lista: Lista }[e.tipo];
  return (
    <AbsoluteFill style={{ height: height * PANEL, opacity: sale, alignItems: "center", justifyContent: "center", paddingTop: 50 }}>
      {e.titulo ? (
        <div
          style={{
            fontFamily: SANS,
            fontWeight: 700,
            fontSize: 34,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: acento,
            marginBottom: 30,
            opacity: tit,
            transform: `translateY(${(1 - tit) * 12}px)`,
          }}
        >
          {e.titulo}
        </div>
      ) : null}
      <div style={{ transform: `scale(${ESCALA[e.tipo]})`, transformOrigin: "top center", marginBottom: ALTO_EXTRA[e.tipo] }}>
        <Cuerpo v={v} />
      </div>
    </AbsoluteFill>
  );
};

export const Edicion: React.FC<PropsEdicion> = (p) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;
  const f = (s: number) => Math.round(s * fps);
  const tramo = (ini: number, fin: number) => ({ from: f(ini), durationInFrames: Math.max(1, f(fin) - f(ini)) });
  const escenas = p.escenas ?? [];

  // Cuánto está el vídeo «abajo» (0 = pantalla completa, 1 = pantalla partida). Escenas seguidas no vuelven arriba
  const T = 0.5; // segundos de transición
  let partido = 0;
  for (const e of escenas) {
    const unidaAntes = escenas.some((o) => o !== e && Math.abs(o.fin - e.inicio) < 0.25);
    const unidaDespues = escenas.some((o) => o !== e && Math.abs(o.inicio - e.fin) < 0.25);
    const entra = unidaAntes ? 1 : interpolate(t, [e.inicio - T * 0.3, e.inicio + T * 0.7], [0, 1], { easing: suave, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    // Al salir, primero se desvanece el esquema (últimos 8 fotogramas) y después sube el vídeo
    const sale = unidaDespues ? 1 : interpolate(t, [e.fin - 0.05, e.fin + T * 0.9], [1, 0], { easing: suave, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    if (t >= e.inicio - T && t <= e.fin + T) partido = Math.max(partido, Math.min(entra, sale));
  }
  const arriba = partido * PANEL * height;
  const radio = 44 * partido;

  return (
    <AbsoluteFill style={{ backgroundColor: FONDO }}>
      {/* Fondo del panel: degradado oscuro con un brillo cálido */}
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 0%, rgba(245,197,66,0.10), transparent 60%), ${FONDO}` }} />
      {p.video ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: arriba,
            bottom: 0,
            overflow: "hidden",
            borderTopLeftRadius: radio,
            borderTopRightRadius: radio,
            boxShadow: partido > 0 ? `0 -20px 60px rgba(0,0,0,${0.5 * partido})` : undefined,
          }}
        >
          <OffthreadVideo src={staticFile(p.video)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 30%" }} />
        </div>
      ) : null}
      {escenas.map((e, i) => {
        const tr = tramo(e.inicio, e.fin);
        return (
          <Sequence key={`e${i}`} {...tr} name={`Escena ${i + 1} · ${e.tipo}`}>
            <PanelEscena e={e} acento={p.estilo.acento} dur={tr.durationInFrames} />
          </Sequence>
        );
      })}
      {p.subtitulos.map((b, i) => {
        const tr = tramo(b.inicio, b.fin);
        const y = p.estilo.subtitulosY + (p.estilo.subtitulosYEscena - p.estilo.subtitulosY) * partido;
        return (
          <Sequence key={`s${i}`} {...tr} name={`Subtítulo ${i + 1}`} layout="none">
            <Subtitulo b={b} estilo={p.estilo} dur={tr.durationInFrames} y={y} />
          </Sequence>
        );
      })}
      {p.tarjetas.map((c, i) => {
        const tr = tramo(c.inicio, c.fin);
        return (
          <Sequence key={`t${i}`} {...tr} name={`Tarjeta ${i + 1}`}>
            <TarjetaVista t={c} acento={p.estilo.acento} dur={tr.durationInFrames} />
          </Sequence>
        );
      })}
      {p.stickers.map((s, i) => {
        const tr = tramo(s.inicio, s.fin);
        return (
          <Sequence key={`k${i}`} {...tr} name={`Sticker ${i + 1}`}>
            <StickerVista s={s} acento={p.estilo.acento} dur={tr.durationInFrames} />
          </Sequence>
        );
      })}
      {p.titular ? (
        <Sequence {...tramo(p.titular.inicio, p.titular.fin)} name="Titular">
          <Titular t={p.titular} acento={p.estilo.acento} dur={tramo(p.titular.inicio, p.titular.fin).durationInFrames} />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};

export const MyComposition = () => (
  <Composition
    id="Edicion"
    component={Edicion}
    durationInFrames={150}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={defecto}
    calculateMetadata={calcular}
  />
);
