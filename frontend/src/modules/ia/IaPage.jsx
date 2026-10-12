import { RefreshCw, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Button, Card, PageHeader, PantallaCarga } from "@/components/ui";
import { useApiResource } from "@/hooks/useApiResource";
import { enlaceDeAviso } from "@/modules/dashboard/avisos";

import "./ia.css";

/**
 * SUGERENCIAS IA (add-on de pago, plan Pro + IA o contratado aparte).
 *
 * El backend calcula todo con estadística sobre los datos reales de la
 * empresa (backend/app/modules/ia/analisis.py) y aquí solo se pinta. Cada
 * sugerencia muestra POR QUÉ se generó y las cifras que usó; una sección sin
 * sugerencias dice el motivo (datos insuficientes, nada que reportar o el rol
 * no ve costos), nunca queda muda. Nada sale del sistema.
 */

const NIVELES = {
  critico: "Urgente",
  advertencia: "Atención",
  oportunidad: "Oportunidad",
  informativo: "Dato",
};

const fmtGenerado = new Intl.DateTimeFormat("es-CO", { dateStyle: "long", timeStyle: "short" });

function Sugerencia({ s }) {
  const enlace = s.enlace?.recurso ? enlaceDeAviso(s.enlace) : null;
  return (
    <li className={`ia-sugerencia ia-sugerencia--${s.nivel}`}>
      <div className="ia-sugerencia__cabeza">
        <span className="ia-sugerencia__nivel">
          <span className="ia-sugerencia__punto" aria-hidden="true" />
          {NIVELES[s.nivel] ?? s.nivel}
        </span>
        <h3 className="ia-sugerencia__titulo">{s.titulo}</h3>
      </div>
      <p className="ia-sugerencia__porque">
        <strong>Por qué: </strong>
        {s.por_que}
      </p>
      {s.datos.length > 0 && (
        <dl className="ia-sugerencia__datos" aria-label="Datos usados">
          {s.datos.map((d) => (
            <div key={d.etiqueta}>
              <dt>{d.etiqueta}</dt>
              <dd className="cifra">{d.valor}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="ia-sugerencia__pie">
        <p className="ia-sugerencia__accion">{s.accion}</p>
        {enlace && (
          <Link className="enlace ia-sugerencia__enlace" to={enlace.a}>
            {enlace.texto}
          </Link>
        )}
      </div>
    </li>
  );
}

function Seccion({ seccion }) {
  const idTitulo = `ia-seccion-${seccion.clave}`;
  return (
    <Card className="ia-seccion" aria-labelledby={idTitulo}>
      <header className="ia-seccion__cabeza">
        <h2 id={idTitulo} className="ia-seccion__titulo">
          {seccion.titulo}
          {seccion.sugerencias.length > 0 && <span className="ia-seccion__cuenta">{seccion.sugerencias.length}</span>}
        </h2>
        <p className="ia-seccion__descripcion">{seccion.descripcion}</p>
      </header>
      {seccion.sugerencias.length > 0 ? (
        <ul className="ia-sugerencias">
          {seccion.sugerencias.map((s) => (
            <Sugerencia key={s.clave} s={s} />
          ))}
        </ul>
      ) : (
        <p className="ia-seccion__vacia">{seccion.sin_datos}</p>
      )}
    </Card>
  );
}

export default function IaPage() {
  const { data, error, cargando, recargar } = useApiResource("/ia/sugerencias");

  return (
    <div className="ia">
      <PageHeader
        titulo="Sugerencias IA"
        descripcion="Calculadas con los datos reales de tu negocio. Cada una explica por qué se generó y con qué cifras."
        acciones={
          <Button variante="secundario" onClick={recargar} cargando={cargando && Boolean(data)}>
            <RefreshCw size={14} aria-hidden="true" />
            Recalcular
          </Button>
        }
      />

      {error && (
        <Card>
          <p className="estado estado--error" role="alert">
            No se pudieron calcular las sugerencias. {error}
          </p>
        </Card>
      )}

      {!data && !error && <PantallaCarga lineas={8} />}

      {data && (
        <>
          <div className="ia-base">
            <p className="ia-base__privacidad">
              <ShieldCheck size={16} aria-hidden="true" />
              <span>{data.privacidad}</span>
            </p>
            <p className="ia-base__meta">
              {data.motor} · base: {data.base.ventas} ventas en {data.base.dias_con_venta} días de los últimos{" "}
              {data.base.dias} · calculado el {fmtGenerado.format(new Date(`${data.generado_en}Z`))}
            </p>
            {!data.base.suficiente && (
              <p className="ia-base__insuficiente" role="status">
                {data.base.mensaje}
              </p>
            )}
          </div>

          <div className="ia-rejilla">
            {data.secciones.map((s) => (
              <Seccion key={s.clave} seccion={s} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
