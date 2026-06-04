/* DëvSec primitives — carried verbatim from the design-system kit, with the
   Lucide icon set extended for dashboard navigation.
   Shared globally (no ES modules under Babel-standalone): see app.jsx load order. */

function FocusLogo({ size = 24, color = "currentColor" }) {
  const dots = [
    { x: 50, y: 15 }, { x: 85, y: 50 }, { x: 50, y: 85 }, { x: 15, y: 50 },
  ];
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className="inline-block">
      <g fill={color}>
        {dots.map((d, i) => (
          <rect key={i} x={d.x - 12} y={d.y - 12} width={24} height={24} fill={color} />
        ))}
      </g>
    </svg>
  );
}

function TrademarkMark({ period = false }) {
  return (
    <React.Fragment>
      Sëcure By Design
      <sup className="ml-0.5 align-super text-[0.8em] font-medium leading-none tracking-normal">™</sup>
      {period && "."}
    </React.Fragment>
  );
}

/* Client-side QR using qrcodejs (window.QRCode constructor, loaded in index.html) */
function DynamicQR({ text, size = 200, color = "#ffffff", className = "" }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const el = ref.current;
    if (!el || !window.QRCode) return;
    el.innerHTML = "";
    /* eslint-disable no-new */
    new window.QRCode(el, {
      text: text || "https://github.com/Christian-Katzmann/dev-security",
      width: size, height: size,
      colorDark: color, colorLight: "rgba(0,0,0,0)",
      correctLevel: window.QRCode.CorrectLevel.M,
    });
    const img = el.querySelector("img");
    if (img) img.style.background = "transparent";
    const tbl = el.querySelector("table");
    if (tbl) tbl.style.display = "none";
  }, [text, size, color]);
  return <div ref={ref} className={className} style={{ width: size, height: size }} aria-label="QR Code" />;
}

/* Minimal Lucide-matched icons (thin stroke). The base set ships with the kit;
   the dashboard nav icons below it are added for the lab. */
function Icon({ name, size = 24, strokeWidth = 1.8, className = "", fill = "none", style }) {
  const common = {
    width: size, height: size, viewBox: "0 0 24 24", fill,
    stroke: fill === "none" ? "currentColor" : "none",
    strokeWidth, strokeLinecap: "round", strokeLinejoin: "round", className, style,
  };
  const paths = {
    /* --- kit base set --- */
    "arrow-right": <React.Fragment><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></React.Fragment>,
    "check": <path d="M20 6 9 17l-5-5" />,
    "key-round": <React.Fragment><path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z" /><circle cx="16.5" cy="7.5" r=".5" fill="currentColor" /></React.Fragment>,
    "menu": <React.Fragment><line x1="4" x2="20" y1="6" y2="6" /><line x1="4" x2="20" y1="12" y2="12" /><line x1="4" x2="20" y1="18" y2="18" /></React.Fragment>,
    "x": <React.Fragment><path d="M18 6 6 18" /><path d="m6 6 12 12" /></React.Fragment>,
    "shield-check": <React.Fragment><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" /><path d="m9 12 2 2 4-4" /></React.Fragment>,
    "terminal": <React.Fragment><polyline points="4 17 10 11 4 5" /><line x1="12" x2="20" y1="19" y2="19" /></React.Fragment>,
    /* --- dashboard nav set (Lucide) --- */
    "palette": <React.Fragment><circle cx="13.5" cy="6.5" r=".5" fill="currentColor" /><circle cx="17.5" cy="10.5" r=".5" fill="currentColor" /><circle cx="8.5" cy="7.5" r=".5" fill="currentColor" /><circle cx="6.5" cy="12.5" r=".5" fill="currentColor" /><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2Z" /></React.Fragment>,
    "layout-dashboard": <React.Fragment><rect width="7" height="9" x="3" y="3" rx="1" /><rect width="7" height="5" x="14" y="3" rx="1" /><rect width="7" height="9" x="14" y="12" rx="1" /><rect width="7" height="5" x="3" y="16" rx="1" /></React.Fragment>,
    "activity": <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />,
    "inbox": <React.Fragment><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" /><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" /></React.Fragment>,
    "package": <React.Fragment><path d="m7.5 4.27 9 5.15" /><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" /></React.Fragment>,
    "flask": <React.Fragment><path d="M10 2v7.31" /><path d="M14 9.3V1.99" /><path d="M8.5 2h7" /><path d="M14 9.3a6.5 6.5 0 1 1-4 0" /><path d="M5.58 16.5h12.85" /></React.Fragment>,
    "wrench": <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />,
    "book-open": <React.Fragment><path d="M12 7v14" /><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" /></React.Fragment>,
    "circle-check": <React.Fragment><circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" /></React.Fragment>,
    "file-text": <React.Fragment><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M16 13H8" /><path d="M16 17H8" /><path d="M10 9H8" /></React.Fragment>,
    "settings": <React.Fragment><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /><circle cx="12" cy="12" r="3" /></React.Fragment>,
    "chevron-right": <path d="m9 18 6-6-6-6" />,
    "target": <React.Fragment><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></React.Fragment>,
  };
  return <svg {...common} aria-hidden="true">{paths[name]}</svg>;
}

function GithubIcon({ size = 24, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 .5C5.37.5 0 5.78 0 12.29c0 5.21 3.44 9.63 8.2 11.19.6.11.82-.25.82-.57 0-.28-.01-1.02-.02-2.01-3.34.71-4.04-1.58-4.04-1.58-.55-1.37-1.34-1.74-1.34-1.74-1.09-.73.08-.72.08-.72 1.2.08 1.84 1.21 1.84 1.21 1.07 1.8 2.81 1.28 3.49.98.11-.76.42-1.28.76-1.57-2.67-.3-5.47-1.31-5.47-5.81 0-1.28.47-2.33 1.24-3.15-.13-.3-.54-1.5.11-3.13 0 0 1.01-.32 3.3 1.2a11.6 11.6 0 0 1 3-.39c1.02 0 2.05.13 3 .39 2.28-1.52 3.29-1.2 3.29-1.2.65 1.63.24 2.83.12 3.13.77.82 1.23 1.87 1.23 3.15 0 4.51-2.81 5.5-5.49 5.79.43.36.81 1.08.81 2.18 0 1.58-.01 2.85-.01 3.24 0 .32.21.69.83.57A12.02 12.02 0 0 0 24 12.29C24 5.78 18.63.5 12 .5z" />
    </svg>
  );
}

Object.assign(window, { FocusLogo, TrademarkMark, DynamicQR, Icon, GithubIcon });
