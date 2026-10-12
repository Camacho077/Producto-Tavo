export default function Card({ titulo, descripcion, acciones, children, className = "", ...props }) {
  return (
    <section className={`card ${className}`} {...props}>
      {(titulo || acciones) && (
        <header className="card__encabezado">
          <div>
            {titulo && <h2 className="card__titulo">{titulo}</h2>}
            {descripcion && <p className="card__descripcion">{descripcion}</p>}
          </div>
          {acciones && <div className="flex items-center gap-2 shrink-0">{acciones}</div>}
        </header>
      )}
      <div className="card__cuerpo">{children}</div>
    </section>
  );
}
